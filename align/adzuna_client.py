"""Server-side Adzuna GB Jobs API client.

The client is intentionally thin: it builds a request, calls Adzuna, and
normalises the raw payload into :class:`~align.models.Job` objects. All
calls happen on the server so the API key never reaches the browser and CORS
is never an issue.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests

from .config import CATEGORY_MAP, ORIGIN_POSTCODE, Settings
from .models import Job

logger = logging.getLogger(__name__)

ADZUNA_BASE_URL = "https://api.adzuna.com/v1/api/jobs/gb/search/1"
REQUEST_TIMEOUT = 12  # seconds


class AdzunaError(RuntimeError):
    """Raised when the Adzuna API cannot be reached or returns an error."""


class AdzunaClient:
    """Small wrapper around the Adzuna GB job-search endpoint."""

    def __init__(self, settings: Settings, session: Optional[requests.Session] = None):
        """Create a client.

        Args:
            settings: Runtime settings carrying the Adzuna credentials.
            session: Optional pre-built :class:`requests.Session` (useful in tests).
        """
        self._settings = settings
        self._session = session or requests.Session()

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def search(
        self,
        category: str,
        radius_miles: int,
        *,
        results_per_page: int = 50,
        max_days_old: int = 14,
        part_time: bool = True,
        use_category_tag: bool = True,
        where: Optional[str] = None,
    ) -> List[Job]:
        """Query Adzuna and return normalised jobs.

        Args:
            category: Internal category key (see :data:`config.CATEGORY_MAP`).
            radius_miles: Search radius passed to Adzuna's ``distance`` param.
            results_per_page: Page size (Adzuna caps this at 50).
            max_days_old: Only return listings newer than this many days.
            part_time: When True, request Adzuna's ``part_time`` filter.
            use_category_tag: When True, include the mapped Adzuna category tag.

        Returns:
            A list of :class:`Job` instances (possibly empty).

        Raises:
            AdzunaError: On network failure or a non-2xx response.
        """
        if not self._settings.adzuna_configured:
            raise AdzunaError(
                "Adzuna credentials are missing. Set ADZUNA_APP_ID and "
                "ADZUNA_APP_KEY in your .env file."
            )

        mapping = CATEGORY_MAP.get(category)
        if mapping is None:
            raise AdzunaError(f"Unknown category: {category!r}")

        params: Dict[str, Any] = {
            "app_id": self._settings.adzuna_app_id,
            "app_key": self._settings.adzuna_app_key,
            "results_per_page": results_per_page,
            "what": mapping.keywords,
            "where": where or ORIGIN_POSTCODE,
            "distance": _miles_to_metres(radius_miles),
            "max_days_old": max_days_old,
            "sort_by": "date",
            "content-type": "application/json",
        }
        if part_time:
            params["part_time"] = 1
        if use_category_tag and mapping.adzuna_tag:
            params["category"] = mapping.adzuna_tag

        logger.info(
            "Adzuna search: category=%s radius=%smi part_time=%s tag=%s",
            category,
            radius_miles,
            part_time,
            mapping.adzuna_tag if use_category_tag else None,
        )

        try:
            response = self._session.get(
                ADZUNA_BASE_URL, params=params, timeout=REQUEST_TIMEOUT
            )
        except requests.RequestException as exc:  # pragma: no cover - network
            raise AdzunaError(f"Could not reach Adzuna: {exc}") from exc

        if response.status_code != 200:
            snippet = response.text[:200]
            raise AdzunaError(
                f"Adzuna returned HTTP {response.status_code}: {snippet}"
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise AdzunaError("Adzuna returned malformed JSON.") from exc

        results = payload.get("results", []) or []
        return [self._normalise(raw) for raw in results]

    # ------------------------------------------------------------------ #
    # Normalisation
    # ------------------------------------------------------------------ #
    @staticmethod
    def _normalise(raw: Dict[str, Any]) -> Job:
        """Convert a raw Adzuna result dict into a :class:`Job`."""
        company = (raw.get("company") or {}).get("display_name") or "Unknown employer"
        location_obj = raw.get("location") or {}
        location = location_obj.get("display_name") or "Nottingham area"

        return Job(
            title=(raw.get("title") or "Untitled role").strip(),
            company=company.strip(),
            location=location.strip(),
            latitude=_as_float(raw.get("latitude")),
            longitude=_as_float(raw.get("longitude")),
            salary_min=_as_float(raw.get("salary_min")),
            salary_max=_as_float(raw.get("salary_max")),
            contract_time=raw.get("contract_time"),
            created=_parse_date(raw.get("created")),
            redirect_url=raw.get("redirect_url") or "",
            description=(raw.get("description") or "").strip(),
            source="Adzuna",
        )


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _miles_to_metres(miles: int) -> int:
    """Adzuna's ``distance`` param is expressed in kilometres... as an integer.

    Adzuna documents ``distance`` in km. We convert miles -> km and round up so
    the whole requested radius is covered.
    """
    return max(1, round(miles * 1.60934))


def _as_float(value: Any) -> Optional[float]:
    """Best-effort float conversion returning ``None`` on failure."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_date(value: Any) -> Optional[datetime]:
    """Parse Adzuna's ISO-8601 ``created`` timestamp."""
    if not value or not isinstance(value, str):
        return None
    text = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None
