"""Search coordination: query providers, normalize, and deduplicate.

``SearchService`` fans a single :class:`~models.SearchCriteria` out to every
registered provider, gathers their :class:`~models.Job` results, and removes
duplicate listings that appear on more than one board. It deliberately does no
filtering or ranking — those are separate, testable stages.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from config import Config
from models import Job, SearchCriteria
from providers import build_default_providers
from providers.base import JobProvider

logger = logging.getLogger(__name__)


class SearchService:
    """Aggregate and deduplicate jobs across all configured providers."""

    def __init__(self, config: Config, providers: Optional[List[JobProvider]] = None) -> None:
        self.config = config
        self.providers = providers if providers is not None else build_default_providers(config)

    def search(self, criteria: SearchCriteria) -> List[Job]:
        """Query every provider and return a deduplicated list of jobs."""
        collected: List[Job] = []
        for provider in self.providers:
            try:
                jobs = provider.search(criteria)
            except Exception as exc:  # Defensive: one bad provider must not fail all.
                logger.warning("Provider %s failed: %s", provider.name, exc)
                continue
            logger.info("Provider %s returned %d jobs", provider.name, len(jobs))
            collected.extend(jobs)
        return self._deduplicate(collected)

    @staticmethod
    def _deduplicate(jobs: List[Job]) -> List[Job]:
        """Collapse the same listing seen on multiple boards.

        When duplicates are found, the one from the most reliable source is
        kept so the ranking's source factor reflects the best available link.
        """
        best: Dict[str, Job] = {}
        for job in jobs:
            key = job.dedup_key
            incumbent = best.get(key)
            if incumbent is None or job.source_reliability > incumbent.source_reliability:
                best[key] = job
        return list(best.values())
