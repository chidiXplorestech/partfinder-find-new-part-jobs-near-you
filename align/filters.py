"""Hard filtering rules applied to normalised jobs.

Design note on robustness
--------------------------
Adzuna frequently omits per-job ``latitude``/``longitude`` and salary. A naive
implementation that *drops* any job missing those fields empties the deck on
almost every search. We therefore follow one rule consistently:

    **Unknown data is never grounds for rejection.**

* Distance: Adzuna already geo-filters via ``where`` + ``distance``. We only
  drop a job for distance when we *have* coordinates and they clearly exceed
  the radius (plus a small tolerance). Missing coordinates are kept.
* Pay: roles with unknown pay are kept (per spec). Only *known* pay below the
  floor or above the senior ceiling is rejected.
* Employment type: rejected only on an explicit senior/full-time signal.
"""

from __future__ import annotations

import math
from typing import List, Optional

from . import config
from .models import Job

#: Tolerance added to the radius before dropping a job on distance (miles).
DISTANCE_TOLERANCE_MILES: float = 1.5


# --------------------------------------------------------------------------- #
# Geometry
# --------------------------------------------------------------------------- #
def haversine_miles(
    lat1: float, lng1: float, lat2: float, lng2: float
) -> float:
    """Great-circle distance between two lat/lng points, in miles."""
    radius_miles = 3958.7613
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return 2 * radius_miles * math.asin(min(1.0, math.sqrt(a)))


def compute_distance(
    job: Job, origin: Optional[tuple] = None
) -> Optional[float]:
    """Return the job's distance from the search origin, or ``None``.

    ``origin`` is an optional ``(lat, lng)`` pair; when omitted the app's
    default origin (NG7 1NZ) is used, preserving backward compatibility.
    """
    if job.latitude is None or job.longitude is None:
        return None
    lat0, lng0 = origin if origin else (config.ORIGIN_LAT, config.ORIGIN_LNG)
    return haversine_miles(lat0, lng0, job.latitude, job.longitude)


# --------------------------------------------------------------------------- #
# Individual predicates
# --------------------------------------------------------------------------- #
def _haystack(job: Job) -> str:
    """Lower-cased blob of the fields we scan for keywords."""
    return " ".join(
        [job.title, job.description, job.contract_time or ""]
    ).lower()


def is_seniority_rejected(job: Job, employment: str = "part_time") -> bool:
    """True when the role should be dropped for the given employment preference.

    Senior/leadership roles are always rejected. Full-time roles are rejected
    only when the user asked for part-time work (the default); the ``full_time``
    and ``both`` preferences keep them.
    """
    text = _haystack(job)
    if any(token in text for token in config.SENIORITY_KEYWORDS):
        return True
    if employment == "part_time" and any(
        token in text for token in config.FULLTIME_KEYWORDS
    ):
        return True
    return False


def passes_pay_floor(job: Job) -> bool:
    """True when pay is unknown, or known and within the acceptable band."""
    hourly = job.hourly_pay(config.ASSUMED_WEEKLY_HOURS, config.WEEKS_PER_YEAR)
    if hourly is None:
        return True  # unknown pay is kept
    if hourly < config.MIN_HOURLY_PAY:
        return False
    annual = job.salary_avg
    if annual is not None and annual > config.MAX_ANNUAL_SALARY:
        return False  # senior-level compensation
    return True


def passes_freshness(job: Job) -> bool:
    """True when the posting is within the freshness window (or undated)."""
    age = job.age_days
    if age is None:
        return True
    return age <= config.MAX_DAYS_OLD


def passes_distance(job: Job, radius_miles: int) -> bool:
    """True when within radius, or when coordinates are unknown.

    Adzuna already constrains results geographically via the request; this is a
    secondary guard that only fires when we actually have coordinates.
    """
    distance = job.distance_miles
    if distance is None:
        return True  # trust Adzuna's server-side geo filter
    return distance <= radius_miles + DISTANCE_TOLERANCE_MILES


def has_valid_apply_link(job: Job) -> bool:
    """True when the job carries a usable Adzuna redirect (Apply) URL."""
    return job.redirect_url.startswith("http")


# --------------------------------------------------------------------------- #
# Pipeline entry point
# --------------------------------------------------------------------------- #
def filter_jobs(
    jobs: List[Job],
    radius_miles: int,
    origin: Optional[tuple] = None,
    employment: str = "part_time",
) -> List[Job]:
    """Apply all hard rules and return the surviving jobs.

    Distance is computed and cached on each job as a side effect so downstream
    ranking can reuse it. ``origin`` is an optional ``(lat, lng)`` pair.
    ``employment`` is the user's preference: ``part_time`` (default),
    ``full_time`` or ``both``.
    """
    survivors: List[Job] = []
    seen_urls = set()

    for job in jobs:
        # Cache distance for ranking regardless of the outcome.
        job.distance_miles = compute_distance(job, origin)

        if not has_valid_apply_link(job):
            continue
        if job.redirect_url in seen_urls:
            continue  # de-duplicate identical listings
        if is_seniority_rejected(job, employment):
            continue
        if not passes_pay_floor(job):
            continue
        if not passes_freshness(job):
            continue
        if not passes_distance(job, radius_miles):
            continue

        seen_urls.add(job.redirect_url)
        survivors.append(job)

    return survivors
