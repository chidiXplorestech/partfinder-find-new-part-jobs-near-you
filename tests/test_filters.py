"""Unit tests for the hard filtering rules."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from align import config
from align.filters import (
    compute_distance,
    filter_jobs,
    haversine_miles,
    is_seniority_rejected,
    passes_distance,
    passes_freshness,
    passes_pay_floor,
)
from align.models import Job


def make_job(**overrides) -> Job:
    """Build a Job with sensible defaults, overridable per-test."""
    base = dict(
        title="Part-time Sales Assistant",
        company="Acme Ltd",
        location="Nottingham",
        latitude=config.ORIGIN_LAT,
        longitude=config.ORIGIN_LNG,
        salary_min=25_000,
        salary_max=27_000,
        contract_time="part_time",
        created=datetime.now(timezone.utc) - timedelta(days=2),
        redirect_url="https://adzuna.example/job/1",
        description="A flexible weekend role for students.",
    )
    base.update(overrides)
    return Job(**base)


# --------------------------------------------------------------------------- #
# Geometry
# --------------------------------------------------------------------------- #
def test_haversine_zero_distance():
    assert haversine_miles(52.95, -1.17, 52.95, -1.17) == pytest.approx(0.0, abs=1e-6)


def test_haversine_known_distance():
    # Nottingham origin to roughly Nottingham station (~1 mile-ish).
    d = haversine_miles(config.ORIGIN_LAT, config.ORIGIN_LNG, 52.9476, -1.1460)
    assert 1.0 < d < 2.0


def test_compute_distance_none_when_missing_coords():
    job = make_job(latitude=None, longitude=None)
    assert compute_distance(job) is None


# --------------------------------------------------------------------------- #
# Seniority / employment type
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "title",
    [
        "Senior Sales Manager",
        "Head of Retail",
        "Full-time Store Director",
        "Graduate Scheme 2025",
        "Team Lead Wanted",
    ],
)
def test_seniority_rejected(title):
    assert is_seniority_rejected(make_job(title=title)) is True


@pytest.mark.parametrize(
    "title",
    [
        "Part-time Barista",
        "Weekend Retail Assistant",
        "Casual Waiter",
        "Student Ambassador",
    ],
)
def test_seniority_kept(title):
    assert is_seniority_rejected(make_job(title=title)) is False


# --------------------------------------------------------------------------- #
# Pay floor
# --------------------------------------------------------------------------- #
def test_pay_floor_rejects_low_pay():
    # £18k / (37.5*52) ≈ £9.23/hr -> below floor.
    job = make_job(salary_min=18_000, salary_max=18_000)
    assert passes_pay_floor(job) is False


def test_pay_floor_accepts_living_wage():
    # £26k ≈ £13.33/hr -> above floor.
    job = make_job(salary_min=26_000, salary_max=26_000)
    assert passes_pay_floor(job) is True


def test_pay_floor_rejects_senior_salary():
    job = make_job(salary_min=60_000, salary_max=60_000)
    assert passes_pay_floor(job) is False


def test_pay_floor_keeps_unknown_pay():
    job = make_job(salary_min=None, salary_max=None)
    assert passes_pay_floor(job) is True


# --------------------------------------------------------------------------- #
# Freshness
# --------------------------------------------------------------------------- #
def test_freshness_rejects_old():
    job = make_job(created=datetime.now(timezone.utc) - timedelta(days=20))
    assert passes_freshness(job) is False


def test_freshness_accepts_recent():
    job = make_job(created=datetime.now(timezone.utc) - timedelta(days=5))
    assert passes_freshness(job) is True


def test_freshness_keeps_undated():
    job = make_job(created=None)
    assert passes_freshness(job) is True


# --------------------------------------------------------------------------- #
# Distance (never drops on missing coords)
# --------------------------------------------------------------------------- #
def test_distance_keeps_missing_coords():
    job = make_job(latitude=None, longitude=None)
    job.distance_miles = compute_distance(job)
    assert passes_distance(job, radius_miles=3) is True


def test_distance_drops_far_job():
    # A point well outside the radius (London-ish).
    job = make_job(latitude=51.5074, longitude=-0.1278)
    job.distance_miles = compute_distance(job)
    assert passes_distance(job, radius_miles=5) is False


# --------------------------------------------------------------------------- #
# End-to-end filter pipeline
# --------------------------------------------------------------------------- #
def test_filter_pipeline_dedupes_and_filters():
    good = make_job()
    duplicate = make_job()  # same redirect_url
    senior = make_job(title="Senior Manager", redirect_url="https://adzuna.example/2")
    no_link = make_job(redirect_url="", latitude=None, longitude=None)

    survivors = filter_jobs([good, duplicate, senior, no_link], radius_miles=5)
    assert len(survivors) == 1
    assert survivors[0].redirect_url == "https://adzuna.example/job/1"
    # Distance was cached on the survivor.
    assert survivors[0].distance_miles is not None
