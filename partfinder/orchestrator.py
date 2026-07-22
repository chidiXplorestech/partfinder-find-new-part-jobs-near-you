"""Search orchestration: the pipeline that turns a query into ranked matches.

The orchestrator implements *graceful tiering*. Stacking every hard filter on
top of a strict Adzuna query routinely yields an empty deck, which reads as a
broken app. Instead we start strict and progressively relax when results are
thin, telling the user exactly what we widened. Distance never silently drops
jobs (see :mod:`partfinder.filters`).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Optional

from . import config
from .adzuna_client import AdzunaClient, AdzunaError
from .filters import filter_jobs
from .models import Job, SearchQuery
from .ranking import rank_jobs

logger = logging.getLogger(__name__)

#: We consider the deck "healthy" once at least this many matches survive.
_HEALTHY_DECK_SIZE = 5


@dataclass
class SearchResult:
    """Outcome of a search: ranked jobs plus UX metadata."""

    jobs: List[Job] = field(default_factory=list)
    notice: Optional[str] = None
    error: Optional[str] = None
    used_radius: int = 0
    total_fetched: int = 0

    @property
    def is_empty(self) -> bool:
        return not self.jobs


@dataclass
class _Tier:
    """A single search attempt configuration."""

    radius: int
    part_time: bool
    use_category_tag: bool
    notice: Optional[str] = None


class SearchOrchestrator:
    """Coordinates the Adzuna client, filters and ranking."""

    def __init__(self, client: AdzunaClient):
        self._client = client

    def search(self, query: SearchQuery) -> SearchResult:
        """Run the tiered search pipeline for ``query``."""
        radius = self._validate_radius(query.radius)
        wider = self._next_radius(radius)

        # Tiers from strict -> relaxed. Each later tier loosens one constraint.
        tiers: List[_Tier] = [
            _Tier(radius, part_time=True, use_category_tag=True),
            _Tier(radius, part_time=False, use_category_tag=True),
            _Tier(radius, part_time=False, use_category_tag=False),
        ]
        if wider != radius:
            tiers.append(
                _Tier(
                    wider,
                    part_time=False,
                    use_category_tag=False,
                    notice=f"Slim pickings nearby — widened the search to {wider} miles.",
                )
            )

        best: SearchResult = SearchResult(used_radius=radius)

        for tier in tiers:
            try:
                raw = self._client.search(
                    category=query.category,
                    radius_miles=tier.radius,
                    part_time=tier.part_time,
                    use_category_tag=tier.use_category_tag,
                )
            except AdzunaError as exc:
                logger.warning("Adzuna search failed: %s", exc)
                # Only report the error if we have nothing better to show.
                if best.is_empty:
                    best.error = str(exc)
                break

            effective_query = SearchQuery(
                category=query.category, days=query.days, radius=tier.radius
            )
            filtered = filter_jobs(raw, tier.radius)
            ranked = rank_jobs(filtered, effective_query)

            if len(ranked) > len(best.jobs):
                best = SearchResult(
                    jobs=ranked,
                    notice=tier.notice,
                    used_radius=tier.radius,
                    total_fetched=len(raw),
                )

            if len(ranked) >= _HEALTHY_DECK_SIZE:
                break  # deck is healthy, stop relaxing

        return best

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _validate_radius(radius: int) -> int:
        """Clamp the radius to an allowed value, defaulting to 5 miles."""
        return radius if radius in config.ALLOWED_RADII else 5

    @staticmethod
    def _next_radius(radius: int) -> int:
        """Return the next larger allowed radius (or the same if already max)."""
        larger = [r for r in config.ALLOWED_RADII if r > radius]
        return min(larger) if larger else radius
