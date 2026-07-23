"""Application configuration and static reference data.

All tunable constants live here so the rest of the code base reads
declaratively. Secrets are loaded from the environment (``.env`` via
python-dotenv) and are never hard-coded.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, List

from dotenv import load_dotenv

# Load .env once at import time. In production the variables are already
# present in the environment and load_dotenv is a no-op.
load_dotenv()


# --------------------------------------------------------------------------- #
# Search origin: 57 Albert Grove, Nottingham, NG7 1NZ
# --------------------------------------------------------------------------- #
ORIGIN_LAT: float = 52.9515
ORIGIN_LNG: float = -1.1789
ORIGIN_POSTCODE: str = "NG7 1NZ"


# --------------------------------------------------------------------------- #
# Filtering thresholds
# --------------------------------------------------------------------------- #
#: UK National Living Wage floor the app enforces (£/hour).
MIN_HOURLY_PAY: float = 12.71
#: Roles paying above this annual figure are treated as senior and dropped.
MAX_ANNUAL_SALARY: float = 45_000.0
#: Assumed working hours per week when converting annual -> hourly pay.
ASSUMED_WEEKLY_HOURS: float = 37.5
WEEKS_PER_YEAR: int = 52
#: Never surface a listing older than this many days.
MAX_DAYS_OLD: int = 14
#: Allowed search radii (miles) offered on the home page.
ALLOWED_RADII: List[int] = [3, 5, 10, 15]

#: Tokens that mark a role as too senior — always rejected, whatever the
#: user's part-time/full-time preference.
SENIORITY_KEYWORDS: List[str] = [
    "senior",
    "manager",
    "management",
    "graduate",
    "director",
    "head of",
    "lead ",
    "principal",
    "supervisor",
]

#: Tokens that mark a role as full-time. Rejected only when the user asked for
#: part-time work; allowed for the "full-time" and "both" preferences.
FULLTIME_KEYWORDS: List[str] = [
    "full-time",
    "full time",
    "fulltime",
]

#: Combined reject list (senior + full-time). Kept for backward compatibility;
#: :func:`filters.is_seniority_rejected` now consults the two lists above so it
#: can honour the user's employment preference.
REJECT_KEYWORDS: List[str] = FULLTIME_KEYWORDS + SENIORITY_KEYWORDS

#: Tokens that positively signal a part-time / student-friendly role.
KEEP_KEYWORDS: List[str] = [
    "part-time",
    "part time",
    "casual",
    "student",
    "weekend",
    "temporary",
    "temp ",
    "zero-hour",
    "zero hour",
    "flexible",
    "evening",
    "seasonal",
]

#: Availability keywords used by the ranking availability-match component.
AVAILABILITY_KEYWORDS: List[str] = [
    "weekend",
    "flexible",
    "evening",
    "part-time",
    "part time",
    "casual",
    "shift",
]


# --------------------------------------------------------------------------- #
# Category mapping (home-page category -> Adzuna query parameters)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class CategoryMapping:
    """Maps a user-facing category onto Adzuna query parameters.

    Attributes:
        label: Human-readable category name shown in the UI.
        keywords: Free-text ``what`` search terms.
        adzuna_tag: Adzuna ``category`` tag, or ``None`` when no clean mapping
            exists (remote / contract are keyword-driven).
    """

    label: str
    keywords: str
    adzuna_tag: str | None = None


CATEGORY_MAP: Dict[str, CategoryMapping] = {
    "sales": CategoryMapping("Sales", "sales assistant", "sales-jobs"),
    "customer_service": CategoryMapping(
        "Customer Service", "customer service advisor", "customer-services-jobs"
    ),
    "office": CategoryMapping("Office Jobs", "office admin assistant", "admin-jobs"),
    "remote": CategoryMapping("Reliable Remote Jobs", "remote work from home", None),
    "retail": CategoryMapping("Retail", "retail assistant", "retail-catering-jobs"),
    "housing": CategoryMapping("Housing", "housing lettings property", "property-jobs"),
    "contract": CategoryMapping("Contract", "contract temporary", None),
}

#: Ordered list for rendering the category selector.
CATEGORY_ORDER: List[str] = [
    "sales",
    "customer_service",
    "office",
    "remote",
    "retail",
    "housing",
    "contract",
]

DAYS_OF_WEEK: List[str] = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]


# --------------------------------------------------------------------------- #
# Ranking weights (documented in ranking.py)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class RankingWeights:
    """Relative importance of each ranking component (higher == matters more)."""

    distance: float = 0.35
    freshness: float = 0.25
    availability: float = 0.20
    pay: float = 0.12
    source: float = 0.08


RANKING_WEIGHTS = RankingWeights()


# --------------------------------------------------------------------------- #
# Environment helpers (tolerant of blank / malformed values)
# --------------------------------------------------------------------------- #
def _env_int(name: str, default: int) -> int:
    """Read an int env var, falling back to ``default`` when unset OR blank/invalid.

    ``os.getenv(name, default)`` only uses the default when the variable is
    *unset*; a variable set to an empty string (e.g. ``PORT=`` in a .env, or an
    unresolved ``$PORT``) would otherwise crash ``int("")``. This never does.
    """
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(str(raw).strip())
    except (TypeError, ValueError):
        return default


def _env_bool(name: str, default: bool = False) -> bool:
    """Read a boolean env var; blank/unset -> ``default``."""
    raw = os.getenv(name)
    if raw is None or str(raw).strip() == "":
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


# --------------------------------------------------------------------------- #
# Runtime settings container
# --------------------------------------------------------------------------- #
@dataclass
class Settings:
    """Runtime settings sourced from the environment."""

    adzuna_app_id: str = field(default_factory=lambda: os.getenv("ADZUNA_APP_ID", ""))
    adzuna_app_key: str = field(default_factory=lambda: os.getenv("ADZUNA_APP_KEY", ""))
    secret_key: str = field(
        default_factory=lambda: os.getenv("SECRET_KEY", "dev-insecure-secret")
    )
    host: str = field(default_factory=lambda: os.getenv("HOST") or "127.0.0.1")
    port: int = field(default_factory=lambda: _env_int("PORT", 5000))
    debug: bool = field(default_factory=lambda: _env_bool("FLASK_DEBUG", False))

    # --- Paywall --- #
    paywall_enabled: bool = field(
        default_factory=lambda: _env_bool("PAYWALL_ENABLED", False)
    )
    #: GoCardless hosted payment link (https://pay.gocardless.com/...). When set,
    #: this is the primary payment method and the CTA links straight to it.
    #: Defaults to the project's hosted £1 link so the paywall is functional as
    #: soon as PAYWALL_ENABLED=1 — override in .env to use your own link.
    gocardless_payment_link: str = field(
        default_factory=lambda: os.getenv(
            "GOCARDLESS_PAYMENT_LINK",
            "https://pay.gocardless.com/BRT01KY3S2V89HC5QBH5WG89ZHBE8",
        ).strip()
    )
    #: Shared secret appended to the GoCardless success-redirect URL so that
    #: only a genuine post-payment return can unlock access. Optional but
    #: recommended (see README). Only used in hosted-link mode.
    payment_return_token: str = field(
        default_factory=lambda: os.getenv("PAYMENT_RETURN_TOKEN", "").strip()
    )
    #: GoCardless API access token (live_... or sandbox_...). When set, the app
    #: verifies payments server-side via the GoCardless API instead of trusting
    #: the redirect. This is a SECRET — env only, never a URL or tracked file.
    gocardless_access_token: str = field(
        default_factory=lambda: os.getenv("GOCARDLESS_ACCESS_TOKEN", "").strip()
    )
    #: Which GoCardless environment the access token belongs to.
    gocardless_environment: str = field(
        default_factory=lambda: (os.getenv("GOCARDLESS_ENVIRONMENT", "live").strip().lower() or "live")
    )
    #: Webhook endpoint secret (from the GoCardless dashboard) used to verify the
    #: signature on incoming webhook events. Required for the webhook endpoint.
    gocardless_webhook_secret: str = field(
        default_factory=lambda: os.getenv("GOCARDLESS_WEBHOOK_SECRET", "").strip()
    )
    #: Access price in the smallest currency unit (pence). 100 = £1.00.
    price_pence: int = field(default_factory=lambda: _env_int("PRICE_PENCE", 100))
    currency: str = field(default_factory=lambda: os.getenv("CURRENCY") or "gbp")
    #: Public base URL of the deployed app (used for payment redirect URLs).
    public_base_url: str = field(
        default_factory=lambda: os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
    )

    @property
    def adzuna_configured(self) -> bool:
        """True when both Adzuna credentials are present."""
        return bool(self.adzuna_app_id and self.adzuna_app_key)

    @property
    def payment_provider(self) -> str:
        """Which payment method is active.

        Priority: a GoCardless API access token (verified server-side) beats a
        bare hosted link (trust/token gated).
        Returns one of: 'gocardless_api', 'gocardless', 'none'.
        """
        if self.gocardless_access_token:
            return "gocardless_api"
        if self.gocardless_payment_link:
            return "gocardless"
        return "none"

    @property
    def gocardless_api_base(self) -> str:
        """GoCardless REST API base URL for the configured environment."""
        return (
            "https://api-sandbox.gocardless.com"
            if self.gocardless_environment == "sandbox"
            else "https://api.gocardless.com"
        )

    @property
    def payment_provider_label(self) -> str:
        """Human-friendly provider name for the UI."""
        return {
            "gocardless_api": "GoCardless",
            "gocardless": "GoCardless",
        }.get(self.payment_provider, "")

    @property
    def paywall_active(self) -> bool:
        """True only when the paywall is on AND a payment method is configured."""
        return bool(self.paywall_enabled and self.payment_provider != "none")

    @property
    def price_display(self) -> str:
        """Human-friendly price, e.g. '£1.00'."""
        symbol = {"gbp": "£", "usd": "$", "eur": "€"}.get(self.currency.lower(), "")
        return f"{symbol}{self.price_pence / 100:.2f}"


def get_settings() -> Settings:
    """Return a fresh :class:`Settings` snapshot from the environment."""
    return Settings()
