"""Central configuration for PartFinder.

All tunable values live here so the rest of the application never hard-codes
locations, thresholds, keyword lists, or credentials. Values that are secret or
environment-specific are read from the process environment (optionally loaded
from a local ``.env`` file via python-dotenv).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

try:  # Load .env if python-dotenv is installed; harmless if it is not.
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover - dotenv is a declared dependency.
    pass


@dataclass(frozen=True)
class Category:
    """A user-selectable job category.

    Attributes:
        key: Stable identifier used in form values and URLs.
        label: Human-readable name shown in the UI.
        keywords: Free-text search terms sent to live providers.
        adzuna_category: Adzuna category tag, if one maps cleanly.
        contract: Whether to request contract roles from providers.
        remote: Whether this category targets remote work.
    """

    key: str
    label: str
    keywords: List[str]
    adzuna_category: Optional[str] = None
    contract: bool = False
    remote: bool = False


# The seven categories offered on the home page, in display order.
CATEGORIES: List[Category] = [
    Category("sales", "Sales", ["sales assistant", "sales"], "sales-jobs"),
    Category(
        "customer-service",
        "Customer Service",
        ["customer service", "customer assistant"],
        "customer-services-jobs",
    ),
    Category("office", "Office Jobs", ["office", "admin", "receptionist"], "admin-jobs"),
    Category(
        "remote",
        "Reliable Remote Jobs",
        ["remote", "work from home"],
        remote=True,
    ),
    Category("retail", "Retail", ["retail", "shop assistant", "store"], "retail-catering-jobs"),
    Category("housing", "Housing", ["housing", "property", "lettings"], "property-jobs"),
    Category("contract", "Contract", ["contract", "temporary"], contract=True),
]

CATEGORY_BY_KEY: Dict[str, Category] = {c.key: c for c in CATEGORIES}

# The seven days offered for availability selection, in display order.
DAYS: List[str] = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]

WEEKEND_DAYS = {"Saturday", "Sunday"}


@dataclass(frozen=True)
class Config:
    """Application configuration snapshot.

    Instantiate with :meth:`from_env` to pull secrets from the environment.
    """

    # --- Search origin: 57 Albert Grove, Nottingham, NG7 1NZ ---
    origin_address: str = "57 Albert Grove, Nottingham, NG7 1NZ"
    origin_postcode: str = "NG7 1NZ"
    origin_lat: float = 52.9515
    origin_lng: float = -1.1789

    # --- Radius options (miles) offered in the UI ---
    radius_options: tuple = (3, 5, 10, 15)
    default_radius: int = 5

    # --- Freshness: never return jobs older than two weeks ---
    max_job_age_days: int = 14

    # --- Pay guidance (UK, approximate current rates) ---
    # Used to prioritise entry-level pay and to exclude clearly-senior salaries.
    national_minimum_wage_hourly: float = 8.60
    national_living_wage_hourly: float = 11.44
    # Annual salary above which a role is treated as senior (ranking/filtering).
    entry_level_salary_cap: float = 45000.0

    # --- Live provider (Adzuna) ---
    adzuna_app_id: Optional[str] = None
    adzuna_app_key: Optional[str] = None
    adzuna_country: str = "gb"
    provider_timeout_seconds: float = 8.0
    results_per_provider: int = 50

    # --- Output ---
    results_limit: int = 50

    # --- Flask / storage ---
    secret_key: str = "dev-secret-change-me"
    db_path: str = "partfinder.sqlite3"
    seed_path: str = os.path.join(os.path.dirname(__file__), "data", "seed_jobs.json")
    debug: bool = False

    # --- Employment keyword gates (case-insensitive substring match) ---
    accept_keywords: tuple = (
        "part-time",
        "part time",
        "weekend",
        "casual",
        "student",
        "temporary",
        "temp",
        "zero-hour",
        "zero hour",
        "flexible",
        "seasonal",
    )
    reject_keywords: tuple = (
        "full-time",
        "full time",
        "senior",
        "manager",
        "management",
        "graduate",
        "director",
        "head of",
        "lead ",
        "principal",
    )

    @property
    def adzuna_configured(self) -> bool:
        """True when live Adzuna credentials are available."""
        return bool(self.adzuna_app_id and self.adzuna_app_key)

    @classmethod
    def from_env(cls) -> "Config":
        """Build a :class:`Config` from environment variables with sane defaults."""

        def _get(name: str, default: str) -> str:
            value = os.environ.get(name)
            return value if value not in (None, "") else default

        return cls(
            adzuna_app_id=os.environ.get("ADZUNA_APP_ID") or None,
            adzuna_app_key=os.environ.get("ADZUNA_APP_KEY") or None,
            secret_key=_get("SECRET_KEY", "dev-secret-change-me"),
            db_path=_get("DB_PATH", "partfinder.sqlite3"),
            results_limit=int(_get("RESULTS_LIMIT", "50")),
            debug=os.environ.get("FLASK_DEBUG", "").lower() in ("1", "true", "yes"),
        )
