"""Typed data models used across the PartFinder pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class SearchQuery:
    """A validated search request coming from the home-page form.

    Attributes:
        category: Internal category key (see :data:`config.CATEGORY_MAP`).
        days: Selected availability days (e.g. ``["Saturday", "Sunday"]``).
        radius: Search radius in miles.
    """

    category: str
    days: List[str] = field(default_factory=list)
    radius: int = 5


@dataclass
class Job:
    """A normalised job listing.

    All monetary values are annual figures as returned by Adzuna; the
    :attr:`hourly_pay` helper converts them for the pay floor check.
    """

    title: str
    company: str
    location: str
    latitude: Optional[float]
    longitude: Optional[float]
    salary_min: Optional[float]
    salary_max: Optional[float]
    contract_time: Optional[str]
    created: Optional[datetime]
    redirect_url: str
    description: str = ""
    source: str = "Adzuna"

    # Fields populated later by the pipeline.
    distance_miles: Optional[float] = None
    score: float = 0.0
    score_breakdown: Dict[str, float] = field(default_factory=dict)
    match_percent: int = 0
    match_reasons: List[str] = field(default_factory=list)

    # ------------------------------------------------------------------ #
    # Derived helpers
    # ------------------------------------------------------------------ #
    @property
    def salary_avg(self) -> Optional[float]:
        """Mean annual salary when any figure is known, else ``None``."""
        values = [v for v in (self.salary_min, self.salary_max) if v]
        return sum(values) / len(values) if values else None

    def hourly_pay(self, weekly_hours: float, weeks_per_year: int) -> Optional[float]:
        """Return the estimated hourly pay, or ``None`` when salary is unknown."""
        annual = self.salary_avg
        if annual is None:
            return None
        return annual / (weekly_hours * weeks_per_year)

    @property
    def age_days(self) -> Optional[float]:
        """Age of the posting in days, or ``None`` when the date is unknown."""
        if self.created is None:
            return None
        now = datetime.now(timezone.utc)
        created = self.created
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        return (now - created).total_seconds() / 86_400.0

    # ------------------------------------------------------------------ #
    # Serialisation for the JSON API / templates
    # ------------------------------------------------------------------ #
    def to_dict(self, weekly_hours: float, weeks_per_year: int) -> Dict[str, Any]:
        """Return a JSON-serialisable representation for the frontend."""
        hourly = self.hourly_pay(weekly_hours, weeks_per_year)
        return {
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "salary_min": self.salary_min,
            "salary_max": self.salary_max,
            "hourly_pay": round(hourly, 2) if hourly is not None else None,
            "contract_time": self.contract_time,
            "created": self.created.isoformat() if self.created else None,
            "created_display": self._created_display(),
            "redirect_url": self.redirect_url,
            "source": self.source,
            "distance_miles": (
                round(self.distance_miles, 1)
                if self.distance_miles is not None
                else None
            ),
            "score": round(self.score, 3),
            "score_breakdown": {k: round(v, 3) for k, v in self.score_breakdown.items()},
            "match_percent": self.match_percent,
            "match_reasons": self.match_reasons,
            "initials": self._initials(),
            "salary_display": self._salary_display(hourly),
            "type_display": (self.contract_time or "flexible").replace("_", "-").title(),
        }

    # ------------------------------------------------------------------ #
    # Display helpers
    # ------------------------------------------------------------------ #
    def _initials(self) -> str:
        parts = [p for p in self.company.split() if p]
        if not parts:
            return "?"
        if len(parts) == 1:
            return parts[0][:2].upper()
        return (parts[0][0] + parts[1][0]).upper()

    def _created_display(self) -> str:
        age = self.age_days
        if age is None:
            return "Recently"
        days = int(age)
        if days <= 0:
            return "Today"
        if days == 1:
            return "Yesterday"
        return f"{days} days ago"

    def _salary_display(self, hourly: Optional[float]) -> str:
        if hourly is not None:
            return f"≈ £{hourly:.2f}/hr"
        return "Pay on application"
