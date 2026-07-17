"""Filtering stage of the PartFinder pipeline.

Every function here is pure: it takes a list of jobs (plus context) and returns
a new filtered list, never mutating its input beyond well-defined enrichment
(distance is computed once and stored on the job). Filters enforce the hard
rules from the specification; ranking handles soft preferences.
"""

from __future__ import annotations

from typing import List, Optional

from config import Config
from models import Job, SearchCriteria
from utils import contains_any, days_since, haversine_miles, hourly_rate


def apply_distance(jobs: List[Job], config: Config) -> None:
    """Populate ``job.distance`` (miles from origin) where coordinates exist."""
    for job in jobs:
        if job.distance is not None:
            continue
        if job.latitude is None or job.longitude is None:
            continue
        job.distance = haversine_miles(
            config.origin_lat, config.origin_lng, job.latitude, job.longitude
        )


def filter_by_distance(jobs: List[Job], radius_miles: int) -> List[Job]:
    """Keep jobs within ``radius_miles``.

    Jobs with an unknown distance are kept (they may still be relevant and are
    ranked conservatively later), matching the app's bias toward showing more
    legitimate local options rather than fewer.
    """
    return [j for j in jobs if j.distance is None or j.distance <= radius_miles]


def filter_by_date(jobs: List[Job], max_age_days: int) -> List[Job]:
    """Drop anything older than ``max_age_days`` (never older than two weeks)."""
    return [j for j in jobs if 0 <= days_since(j.posted) <= max_age_days]


def filter_by_salary(jobs: List[Job], config: Config) -> List[Job]:
    """Enforce the pay floor and exclude clearly-senior pay.

    Only roles paying at least ``config.minimum_hourly_pay`` (£12.71/hour) are
    kept when a rate is known. Roles advertising a salary well above the
    entry-level cap are treated as senior and removed. Listings with no stated
    pay are kept (they cannot be judged against the floor and are common for
    casual roles) and are ranked conservatively.
    """
    kept: List[Job] = []
    for job in jobs:
        rate = hourly_rate(job.salary_min)
        if rate is not None and rate < config.minimum_hourly_pay:
            continue
        if job.salary_min and job.salary_min > config.entry_level_salary_cap:
            continue
        kept.append(job)
    return kept


def filter_by_employment(jobs: List[Job], config: Config) -> List[Job]:
    """Keep student-friendly roles and reject full-time/senior roles.

    A job is rejected if its title/type/description contains any reject keyword.
    Among the remainder, a job is accepted if it either matches an accept keyword
    or carries no disqualifying signal (unknown types are given the benefit of
    the doubt, since many casual roles omit an explicit label).
    """
    kept: List[Job] = []
    for job in jobs:
        haystack = f"{job.title} {job.employment_type} {job.description}"
        if contains_any(haystack, config.reject_keywords):
            continue
        kept.append(job)
    return kept


def apply_all(
    jobs: List[Job],
    criteria: SearchCriteria,
    config: Config,
) -> List[Job]:
    """Run the full filter chain in order and return the surviving jobs."""
    apply_distance(jobs, config)
    jobs = filter_by_employment(jobs, config)
    jobs = filter_by_date(jobs, config.max_job_age_days)
    jobs = filter_by_salary(jobs, config)
    jobs = filter_by_distance(jobs, criteria.radius)
    return jobs
