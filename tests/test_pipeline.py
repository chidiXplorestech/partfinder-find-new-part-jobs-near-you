"""Unit tests for the PartFinder pipeline's pure logic.

These cover the rules most likely to regress: the two-week freshness cutoff,
the reject-keyword employment gate, distance filtering, and ranking order.
Run with:  ``python -m pytest tests/``
"""

from __future__ import annotations

import os
import sys
from datetime import date, timedelta

# Make the project root importable when pytest is run from anywhere.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import filters  # noqa: E402
import ranking  # noqa: E402
from config import Config  # noqa: E402
from models import Job, SearchCriteria  # noqa: E402

CONFIG = Config()


def _job(**overrides) -> Job:
    """Build a Job with sensible defaults, overriding fields per test."""
    defaults = dict(
        title="Weekend Sales Assistant",
        company="Acme",
        location="Lenton, Nottingham",
        pay="£11.44/hour",
        employment_type="Part-time",
        posted=date.today(),
        source="Indeed",
        url="https://example.com/job",
        description="Part-time weekend role, student-friendly.",
        latitude=CONFIG.origin_lat,
        longitude=CONFIG.origin_lng,
        salary_min=12.71,
        salary_max=12.71,
        source_reliability=0.85,
    )
    defaults.update(overrides)
    return Job(**defaults)


def test_filter_by_date_rejects_older_than_two_weeks():
    fresh = _job(posted=date.today() - timedelta(days=3))
    stale = _job(posted=date.today() - timedelta(days=20))
    result = filters.filter_by_date([fresh, stale], CONFIG.max_job_age_days)
    assert fresh in result
    assert stale not in result


def test_filter_by_employment_rejects_disqualifying_keywords():
    good = _job(title="Weekend Sales Assistant")
    manager = _job(title="Sales Manager")
    fulltime = _job(title="Sales Assistant", employment_type="Full-time")
    result = filters.filter_by_employment([good, manager, fulltime], CONFIG)
    assert good in result
    assert manager not in result
    assert fulltime not in result


def test_filter_by_distance_respects_radius():
    near = _job()  # At the origin.
    # ~0.3 degrees latitude is well over 15 miles away.
    far = _job(latitude=CONFIG.origin_lat + 0.5, longitude=CONFIG.origin_lng)
    jobs = [near, far]
    filters.apply_distance(jobs, CONFIG)
    result = filters.filter_by_distance(jobs, radius_miles=5)
    assert near in result
    assert far not in result


def test_filter_by_salary_excludes_senior_pay():
    entry = _job(salary_min=25000)  # ~£12.82/hour: above floor, below cap.
    senior = _job(salary_min=90000)
    result = filters.filter_by_salary([entry, senior], CONFIG)
    assert entry in result
    assert senior not in result


def test_filter_by_salary_enforces_pay_floor():
    at_floor = _job(salary_min=12.71)
    below_floor = _job(salary_min=11.44)
    unknown = _job(salary_min=None)  # Unknown pay is kept.
    result = filters.filter_by_salary([at_floor, below_floor, unknown], CONFIG)
    assert at_floor in result
    assert unknown in result
    assert below_floor not in result


def test_ranking_prefers_closer_and_more_recent():
    criteria = SearchCriteria(category="sales", days=["Saturday"], radius=10)
    close_recent = _job(posted=date.today())
    far_old = _job(
        posted=date.today() - timedelta(days=12),
        latitude=CONFIG.origin_lat + 0.1,
        longitude=CONFIG.origin_lng,
    )
    jobs = [far_old, close_recent]
    filters.apply_distance(jobs, CONFIG)
    ranked = ranking.rank(jobs, criteria, CONFIG)
    assert ranked[0] is close_recent


def test_apply_all_pipeline_runs_end_to_end():
    criteria = SearchCriteria(category="sales", days=["Saturday", "Sunday"], radius=10)
    jobs = [
        _job(title="Weekend Sales Assistant"),
        _job(title="Senior Sales Manager"),  # rejected
        _job(posted=date.today() - timedelta(days=30)),  # too old
    ]
    result = filters.apply_all(jobs, criteria, CONFIG)
    assert len(result) == 1
    assert result[0].title == "Weekend Sales Assistant"
