"""Adzuna live job provider.

Adzuna (https://developer.adzuna.com/) offers a free jobs API that aggregates
listings from many boards (Indeed, Totaljobs, Reed, LinkedIn, CV-Library and
more). It maps cleanly onto PartFinder's needs: postcode location, radius in
miles, part-time filter, minimum salary, sort-by-date and a max-age window.

When credentials are absent or the request fails, ``search`` logs and returns an
empty list so the app gracefully falls back to the seed-backed providers.
"""

from __future__ import annotations

import logging
from typing import List, Optional

import requests

from config import CATEGORY_BY_KEY
from models import Job, SearchCriteria
from providers.base import JobProvider
from utils import format_pay, parse_iso_date

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.adzuna.com/v1/api/jobs/{country}/search/1"


class AdzunaProvider(JobProvider):
    """Query the Adzuna API and normalize results into :class:`Job` objects."""

    name = "Adzuna"
    reliability = 0.92  # Aggregator with structured, reasonably clean data.

    def search(self, criteria: SearchCriteria) -> List[Job]:
        if not self.config.adzuna_configured:
            logger.info("Adzuna credentials not set; skipping live provider.")
            return []

        params = self._build_params(criteria)
        url = _BASE_URL.format(country=self.config.adzuna_country)
        try:
            response = requests.get(
                url,
                params=params,
                headers={"Accept": "application/json"},
                timeout=self.config.provider_timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as exc:
            logger.warning("Adzuna request failed: %s", exc)
            return []

        jobs = [self._to_job(item, criteria) for item in payload.get("results", [])]
        return self._stamp([job for job in jobs if job is not None])

    def _build_params(self, criteria: SearchCriteria) -> dict:
        """Translate search criteria into Adzuna query parameters."""
        category = CATEGORY_BY_KEY.get(criteria.category)
        what = " ".join(category.keywords) if category else criteria.category

        params = {
            "app_id": self.config.adzuna_app_id,
            "app_key": self.config.adzuna_app_key,
            "results_per_page": self.config.results_per_provider,
            "what": what,
            "where": self.config.origin_postcode,
            "distance": criteria.radius,  # miles
            "max_days_old": self.config.max_job_age_days,
            "sort_by": "date",
            "part_time": 1,  # Prefer part-time roles.
        }
        if category and category.adzuna_category:
            params["category"] = category.adzuna_category
        if category and category.contract:
            params["contract"] = 1
        return params

    def _to_job(self, item: dict, criteria: SearchCriteria) -> Optional[Job]:
        """Normalize one Adzuna result item into a :class:`Job`."""
        title = item.get("title")
        url = item.get("redirect_url")
        if not title or not url:
            return None

        posted = parse_iso_date(item.get("created", ""))
        if posted is None:
            return None

        salary_min = item.get("salary_min")
        salary_max = item.get("salary_max")
        location = item.get("location", {}) or {}
        contract_time = (item.get("contract_time") or "").replace("_", "-")

        return Job(
            title=title,
            company=(item.get("company", {}) or {}).get("display_name", "Unknown"),
            location=location.get("display_name", self.config.origin_postcode),
            pay=format_pay(salary_min, salary_max),
            employment_type=contract_time.title() or "Part-time",
            posted=posted,
            source=self.name,
            url=url,
            description=item.get("description", ""),
            latitude=item.get("latitude"),
            longitude=item.get("longitude"),
            category=criteria.category,
            salary_min=salary_min,
            salary_max=salary_max,
        )
