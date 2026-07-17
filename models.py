"""Core data models for PartFinder.

The :class:`Job` dataclass is the single normalized representation of a job used
throughout the pipeline (providers -> search -> filters -> ranking -> view).
Every provider is responsible for producing ``Job`` instances so downstream code
never has to care where a listing came from.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional


@dataclass
class Job:
    """A single normalized job listing.

    The first block of fields matches the public specification exactly. The
    remaining fields are internal helpers used for filtering and ranking; they
    are optional so providers can supply as much as they know.
    """

    title: str
    company: str
    location: str
    pay: str  # Human-readable pay string, e.g. "£11.44/hour".
    employment_type: str  # e.g. "Part-time", "Casual", "Zero-hour".
    posted: date  # Date the listing was posted.
    source: str  # Provider/board name, e.g. "Adzuna", "Indeed".
    url: str  # Link to the original listing (Apply button target).
    description: str = ""

    # --- Internal helpers (not part of the display contract) ---
    distance: Optional[float] = None  # Miles from the search origin.
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    category: Optional[str] = None  # Category key this job was matched under.
    salary_min: Optional[float] = None  # Numeric annual salary, if known.
    salary_max: Optional[float] = None
    source_reliability: float = 0.5  # 0..1 confidence in the source.

    @property
    def distance_display(self) -> str:
        """Distance formatted for the results table."""
        if self.distance is None:
            return "—"
        return f"{self.distance:.1f} mi"

    @property
    def dedup_key(self) -> str:
        """Key used to detect the same listing appearing on multiple boards."""
        from utils import normalize_text  # Local import avoids a cycle.

        return f"{normalize_text(self.title)}|{normalize_text(self.company)}"


@dataclass
class SearchCriteria:
    """User-supplied search parameters gathered from the home page form."""

    category: str  # Category key (see config.CATEGORIES).
    days: List[str] = field(default_factory=list)  # Selected availability days.
    radius: int = 5  # Search radius in miles.

    @property
    def wants_weekend(self) -> bool:
        """True if the student is available on Saturday or Sunday."""
        from config import WEEKEND_DAYS

        return bool(set(self.days) & WEEKEND_DAYS)
