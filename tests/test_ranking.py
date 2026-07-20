"""Unit tests for the ranking / match-scoring functions."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from partfinder import config
from partfinder.models import Job, SearchQuery
from partfinder.ranking import rank_jobs, score_job


def make_job(**overrides) -> Job:
    base = dict(
        title="Part-time Weekend Sales Assistant",
        company="Acme Ltd",
        location="Nottingham",
        latitude=config.ORIGIN_LAT,
        longitude=config.ORIGIN_LNG,
        salary_min=26_000,
        salary_max=28_000,
        contract_time="part_time",
        created=datetime.now(timezone.utc) - timedelta(days=1),
        redirect_url="https://adzuna.example/job/1",
        description="Flexible weekend shifts, ideal for students.",
    )
    base.update(overrides)
    job = Job(**base)
    # Emulate the filter step caching distance.
    from partfinder.filters import compute_distance

    job.distance_miles = compute_distance(job)
    return job


def default_query() -> SearchQuery:
    return SearchQuery(category="sales", days=["Saturday", "Sunday"], radius=5)


# --------------------------------------------------------------------------- #
# score_job
# --------------------------------------------------------------------------- #
def test_score_in_unit_range():
    job = score_job(make_job(), default_query())
    assert 0.0 <= job.score <= 1.0
    assert set(job.score_breakdown) == {
        "distance",
        "freshness",
        "availability",
        "pay",
        "source",
    }


def test_match_percent_band():
    job = score_job(make_job(), default_query())
    assert 60 <= job.match_percent <= 99


def test_reasons_capped_and_present():
    job = score_job(make_job(), default_query())
    assert 1 <= len(job.match_reasons) <= 3


def test_weekend_availability_boost():
    weekend = score_job(
        make_job(description="Weekend shifts available"), default_query()
    )
    plain = score_job(
        make_job(description="Weekday only office cover"), default_query()
    )
    assert weekend.score_breakdown["availability"] > plain.score_breakdown["availability"]


def test_closer_job_scores_higher_on_distance():
    near = make_job()
    far = make_job(latitude=52.99, longitude=-1.05)  # a few miles out
    q = default_query()
    score_job(near, q)
    score_job(far, q)
    assert near.score_breakdown["distance"] > far.score_breakdown["distance"]


# --------------------------------------------------------------------------- #
# rank_jobs ordering
# --------------------------------------------------------------------------- #
def test_rank_orders_best_first():
    strong = make_job(
        redirect_url="https://adzuna.example/strong",
        description="Flexible weekend part-time shifts for students",
        created=datetime.now(timezone.utc),
    )
    weak = make_job(
        redirect_url="https://adzuna.example/weak",
        latitude=52.99,
        longitude=-1.05,
        salary_min=None,
        salary_max=None,
        description="Weekday cover",
        created=datetime.now(timezone.utc) - timedelta(days=10),
    )
    ranked = rank_jobs([weak, strong], default_query())
    assert ranked[0].redirect_url == "https://adzuna.example/strong"
    # Scores are sorted descending.
    assert ranked[0].score >= ranked[1].score


def test_unknown_distance_gets_neutral_score():
    job = make_job(latitude=None, longitude=None)
    job.distance_miles = None
    score_job(job, default_query())
    assert job.score_breakdown["distance"] == 0.6
