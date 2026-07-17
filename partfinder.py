"""PartFinder orchestrator.

``PartFinder`` ties the pipeline together: it coordinates the provider search,
applies the filter chain, ranks the survivors, and returns the final list of
jobs to display. It is the single entry point the web layer talks to.
"""

from __future__ import annotations

import logging
from typing import List, Optional

import filters
import ranking
from config import Config
from models import Job, SearchCriteria
from search import SearchService

logger = logging.getLogger(__name__)


class PartFinder:
    """Coordinate searching, filtering, and ranking of part-time jobs."""

    def __init__(self, config: Config, search_service: Optional[SearchService] = None) -> None:
        self.config = config
        self.search_service = search_service or SearchService(config)

    def run_search(self, criteria: SearchCriteria) -> List[Job]:
        """Return the ranked, filtered jobs for the given criteria.

        Pipeline: gather (providers) -> filter (hard rules) -> rank (preferences)
        -> truncate to the configured results limit.
        """
        raw = self.search_service.search(criteria)
        logger.info("Gathered %d jobs before filtering", len(raw))

        filtered = filters.apply_all(raw, criteria, self.config)
        logger.info("%d jobs remain after filtering", len(filtered))

        ranked = ranking.rank(filtered, criteria, self.config)
        return ranked[: self.config.results_limit]
