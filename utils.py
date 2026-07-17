"""Shared, dependency-light helpers used across PartFinder.

Keeping these pure and centralized avoids duplicated logic in the providers,
filters, and ranking modules.
"""

from __future__ import annotations

import math
import re
from datetime import date, datetime
from typing import Optional

# Rough UK full-time hours used to convert annual salaries to an hourly rate.
_FULL_TIME_HOURS_PER_YEAR = 37.5 * 52

_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_NUMBER = re.compile(r"[\d,]+(?:\.\d+)?")


def haversine_miles(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Return the great-circle distance between two points, in miles."""
    radius_miles = 3958.8
    d_lat = math.radians(lat2 - lat1)
    d_lng = math.radians(lng2 - lng1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lng / 2) ** 2
    )
    return radius_miles * 2 * math.asin(math.sqrt(a))


def normalize_text(value: Optional[str]) -> str:
    """Lower-case and strip punctuation/whitespace for matching and dedup."""
    if not value:
        return ""
    return _NON_ALNUM.sub(" ", value.lower()).strip()


def contains_any(haystack: str, needles) -> bool:
    """True if any needle appears (case-insensitively) in ``haystack``."""
    text = (haystack or "").lower()
    return any(n.lower() in text for n in needles)


def days_since(posted: date, reference: Optional[date] = None) -> int:
    """Whole days between ``posted`` and ``reference`` (today by default)."""
    reference = reference or date.today()
    return (reference - posted).days


def relative_date(posted: date, reference: Optional[date] = None) -> str:
    """Human-friendly 'posted' label, e.g. 'Today', '3 days ago'."""
    delta = days_since(posted, reference)
    if delta <= 0:
        return "Today"
    if delta == 1:
        return "Yesterday"
    return f"{delta} days ago"


def parse_iso_date(value: str) -> Optional[date]:
    """Parse an ISO-8601 date or datetime string into a ``date``.

    Adzuna returns timestamps like ``2026-07-15T09:00:00Z``; we only need the
    date component. Returns ``None`` if the value cannot be parsed.
    """
    if not value:
        return None
    text = value.strip().replace("Z", "+00:00")
    for candidate in (text, text[:10]):
        try:
            return datetime.fromisoformat(candidate).date()
        except ValueError:
            try:
                return datetime.strptime(candidate, "%Y-%m-%d").date()
            except ValueError:
                continue
    return None


def annual_to_hourly(annual: Optional[float]) -> Optional[float]:
    """Convert an annual salary to an approximate hourly rate."""
    if not annual:
        return None
    return annual / _FULL_TIME_HOURS_PER_YEAR


def hourly_rate(salary: Optional[float]) -> Optional[float]:
    """Return an hourly rate from a salary figure.

    Small numbers (< 100) are assumed to already be hourly; larger numbers are
    treated as an annual salary and converted. Returns ``None`` when unknown.
    """
    if not salary:
        return None
    if salary < 100:
        return salary
    return annual_to_hourly(salary)


def format_pay(
    salary_min: Optional[float],
    salary_max: Optional[float] = None,
    fallback: str = "Not specified",
) -> str:
    """Build a readable pay string from numeric annual salary bounds.

    Small numbers (< 100) are treated as an hourly rate; larger numbers as an
    annual salary that we also express per hour to help students compare roles.
    """
    values = [v for v in (salary_min, salary_max) if v]
    if not values:
        return fallback

    low = min(values)
    high = max(values)

    if high < 100:  # Already an hourly figure.
        if low == high:
            return f"£{low:.2f}/hour"
        return f"£{low:.2f}–£{high:.2f}/hour"

    hourly = annual_to_hourly(high)
    if low == high:
        base = f"£{low:,.0f}/year"
    else:
        base = f"£{low:,.0f}–£{high:,.0f}/year"
    if hourly:
        base += f" (≈£{hourly:.2f}/hour)"
    return base
