"""Weighted best-first ranking, plus the "Match %" and reason chips.

Scoring model
-------------
Each job earns five component scores in the range ``[0, 1]``; the weighted sum
(weights in :data:`config.RANKING_WEIGHTS`, which sum to 1.0) becomes the final
score. That score is surfaced to the user as a **Match %** — the Tinder/Hinge
"how compatible are we" number — and the strongest components are translated
into human-readable "why you two match" chips.

Components (priority order per the spec):
    1. distance      - closer is better
    2. freshness     - newer is better
    3. availability  - overlap between the seeker's free days / weekend &
                       flexible signals and the listing text
    4. pay           - living-wage-friendly entry-level pay scores highest
    5. source        - source reliability (Adzuna listings with a real
                       apply link are trustworthy)
"""

from __future__ import annotations

from typing import List, Tuple

from . import config
from .models import Job, SearchQuery

#: Distance (miles) at or beyond which the distance score bottoms out.
_MAX_SCORING_DISTANCE = 15.0
#: Pay (£/hr) at or above which the pay score saturates.
_PAY_SWEET_SPOT = 15.0

_WEEKEND_DAYS = {"Saturday", "Sunday"}


# --------------------------------------------------------------------------- #
# Component scores (each returns a float in [0, 1])
# --------------------------------------------------------------------------- #
def _distance_score(job: Job, radius_miles: int) -> float:
    """Closer jobs score higher; unknown distance gets a neutral score."""
    if job.distance_miles is None:
        return 0.6  # neutral-positive: Adzuna vouched it is within radius
    ceiling = max(radius_miles, 1.0)
    return max(0.0, 1.0 - (job.distance_miles / ceiling))


def _freshness_score(job: Job) -> float:
    """Newer postings score higher across the freshness window."""
    age = job.age_days
    if age is None:
        return 0.5
    return max(0.0, 1.0 - (age / config.MAX_DAYS_OLD))


def _availability_score(job: Job, days: List[str]) -> float:
    """Overlap between the seeker's availability and the listing's signals."""
    text = " ".join([job.title, job.description, job.contract_time or ""]).lower()
    score = 0.0

    # Generic flexibility / part-time signals.
    hits = sum(1 for kw in config.AVAILABILITY_KEYWORDS if kw in text)
    score += min(0.6, hits * 0.2)

    # Weekend availability specifically rewarded when the seeker picked a
    # weekend day and the listing mentions weekend work.
    if days and _WEEKEND_DAYS.intersection(days) and "weekend" in text:
        score += 0.4

    # A little credit just for having stated availability at all.
    if days:
        score += 0.1

    return min(1.0, score)


def _pay_score(job: Job) -> float:
    """Living-wage-friendly pay scores highest; unknown pay is neutral."""
    hourly = job.hourly_pay(config.ASSUMED_WEEKLY_HOURS, config.WEEKS_PER_YEAR)
    if hourly is None:
        return 0.5
    if hourly < config.MIN_HOURLY_PAY:
        return 0.0
    span = _PAY_SWEET_SPOT - config.MIN_HOURLY_PAY
    return min(1.0, (hourly - config.MIN_HOURLY_PAY) / span)


def _source_score(job: Job) -> float:
    """Source reliability. A real Adzuna redirect link is the gold standard."""
    return 1.0 if job.redirect_url.startswith("http") else 0.0


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def score_job(job: Job, query: SearchQuery) -> Job:
    """Compute and attach the weighted score, match percent and reasons."""
    weights = config.RANKING_WEIGHTS
    breakdown = {
        "distance": _distance_score(job, query.radius),
        "freshness": _freshness_score(job),
        "availability": _availability_score(job, query.days),
        "pay": _pay_score(job),
        "source": _source_score(job),
    }
    total = (
        breakdown["distance"] * weights.distance
        + breakdown["freshness"] * weights.freshness
        + breakdown["availability"] * weights.availability
        + breakdown["pay"] * weights.pay
        + breakdown["source"] * weights.source
    )

    job.score = total
    job.score_breakdown = breakdown
    # Present match as a friendly 60-99% band so nothing ever reads as a
    # "bad match" once it has already survived the hard filters.
    job.match_percent = int(round(60 + total * 39))
    job.match_reasons = _build_reasons(job, query, breakdown)
    return job


def rank_jobs(jobs: List[Job], query: SearchQuery) -> List[Job]:
    """Score every job then sort best-first.

    Primary key is the weighted score. Ties break on the spec's priority order:
    distance (closest), then freshness (newest).
    """
    for job in jobs:
        score_job(job, query)

    def sort_key(job: Job) -> Tuple[float, float, float]:
        distance = job.distance_miles if job.distance_miles is not None else 999.0
        age = job.age_days if job.age_days is not None else 999.0
        return (-job.score, distance, age)

    return sorted(jobs, key=sort_key)


# --------------------------------------------------------------------------- #
# Reason chips ("why you two match")
# --------------------------------------------------------------------------- #
def _build_reasons(job: Job, query: SearchQuery, breakdown: dict) -> List[str]:
    """Translate the strongest score components into short human chips."""
    reasons: List[str] = []

    if job.distance_miles is not None:
        if job.distance_miles < 1.0:
            reasons.append("Right on your doorstep")
        elif job.distance_miles <= 3.0:
            reasons.append(f"Just {job.distance_miles:.1f} mi away")
        else:
            reasons.append(f"{job.distance_miles:.0f} mi away")
    else:
        reasons.append(f"Within {query.radius} mi")

    if breakdown["freshness"] >= 0.8:
        reasons.append("Freshly posted")

    text = " ".join([job.title, job.description]).lower()
    if query.days and _WEEKEND_DAYS.intersection(query.days) and "weekend" in text:
        reasons.append("Weekend-friendly")
    elif "flexible" in text:
        reasons.append("Flexible hours")
    elif "part-time" in text or "part time" in text:
        reasons.append("Part-time role")

    hourly = job.hourly_pay(config.ASSUMED_WEEKLY_HOURS, config.WEEKS_PER_YEAR)
    if hourly is not None and hourly >= config.MIN_HOURLY_PAY:
        reasons.append(f"£{hourly:.2f}/hr")

    # Keep the card tidy: at most three chips.
    return reasons[:3]
