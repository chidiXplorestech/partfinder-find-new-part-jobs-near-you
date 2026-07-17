"""Ranking stage of the PartFinder pipeline.

Each job is scored on five factors and the results are sorted best-first. The
factor weights encode the required priority order:

    1. Distance          (closest first)
    2. Posting date       (most recent first)
    3. Availability match  (matches selected days)
    4. Pay                (entry-level / minimum-wage friendly first)
    5. Source reliability (more trustworthy boards first)

Every factor is normalized to 0..1 (higher is better) and combined with the
weights below, so the composite score is comparable across jobs.
"""

from __future__ import annotations

from typing import List

from config import Config
from models import Job, SearchCriteria
from utils import contains_any, days_since, hourly_rate

# Weights in strict priority order; they sum to 1.0 for an interpretable score.
WEIGHTS = {
    "distance": 0.35,
    "recency": 0.25,
    "availability": 0.18,
    "pay": 0.12,
    "reliability": 0.10,
}

_WEEKEND_KEYWORDS = ("weekend", "saturday", "sunday")
_FLEXIBLE_KEYWORDS = ("flexible", "part-time", "part time", "casual", "shifts")


def _distance_score(job: Job, criteria: SearchCriteria) -> float:
    """1.0 at the origin, decaying to 0.0 at the search radius."""
    if job.distance is None:
        return 0.5  # Unknown distance: neutral.
    radius = max(criteria.radius, 1)
    return max(0.0, 1.0 - (job.distance / radius))


def _recency_score(job: Job, config: Config) -> float:
    """1.0 for today, tapering to 0.0 at the max age, with fresh-window boosts."""
    age = days_since(job.posted)
    if age <= 1:  # Last 24 hours: highest priority.
        return 1.0
    if age <= 7:  # Last 7 days.
        return 0.75
    span = max(config.max_job_age_days, 1)
    return max(0.0, 1.0 - (age / span)) * 0.6  # Older but within two weeks.


def _availability_score(job: Job, criteria: SearchCriteria) -> float:
    """Reward jobs that fit the student's selected availability."""
    if not criteria.days:
        return 0.5
    haystack = f"{job.title} {job.employment_type} {job.description}"
    score = 0.4  # Baseline: part-time roles are generally flexible.
    if criteria.wants_weekend and contains_any(haystack, _WEEKEND_KEYWORDS):
        score += 0.4
    if contains_any(haystack, _FLEXIBLE_KEYWORDS):
        score += 0.2
    return min(1.0, score)


def _pay_score(job: Job, config: Config) -> float:
    """Reward entry-level / living-wage-friendly pay; neutral if unknown."""
    hourly = hourly_rate(job.salary_min)
    if hourly is None:
        return 0.5
    if hourly < config.minimum_hourly_pay:
        return 0.3  # Below the pay floor (also filtered out earlier).
    if hourly <= config.national_living_wage_hourly * 1.5:
        return 1.0  # Squarely in the entry-level sweet spot.
    return 0.6  # Higher pay usually signals a more senior role.


def score_job(job: Job, criteria: SearchCriteria, config: Config) -> float:
    """Return the weighted composite score for a single job (0..1)."""
    factors = {
        "distance": _distance_score(job, criteria),
        "recency": _recency_score(job, config),
        "availability": _availability_score(job, criteria),
        "pay": _pay_score(job, config),
        "reliability": min(max(job.source_reliability, 0.0), 1.0),
    }
    return sum(WEIGHTS[name] * value for name, value in factors.items())


def rank(jobs: List[Job], criteria: SearchCriteria, config: Config) -> List[Job]:
    """Return ``jobs`` sorted by descending relevance score.

    Ties fall back to the raw priority order (distance, then recency) so results
    are stable and predictable.
    """
    return sorted(
        jobs,
        key=lambda j: (
            score_job(j, criteria, config),
            -(j.distance if j.distance is not None else 9_999),
            -days_since(j.posted),
        ),
        reverse=True,
    )
