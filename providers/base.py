"""Provider base classes.

``JobProvider`` defines the minimal contract every source must implement.
``SeedBackedProvider`` is a convenience base for board adapters (Indeed,
LinkedIn, ...) that currently serve the bundled seed dataset and mark a clear
extension point for a real API/scraper integration.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import List

from config import CATEGORY_BY_KEY, Config
from database import fetch_seed_jobs
from models import Job, SearchCriteria

logger = logging.getLogger(__name__)


class JobProvider(ABC):
    """Abstract job source.

    Subclasses set :attr:`name` and :attr:`reliability` and implement
    :meth:`search`. Providers must never raise on network/credential problems;
    they should log and return an empty list so one failing source cannot break
    the whole search.
    """

    name: str = "Provider"
    reliability: float = 0.5  # 0..1, feeds the ranking's source factor.

    def __init__(self, config: Config) -> None:
        self.config = config

    @abstractmethod
    def search(self, criteria: SearchCriteria) -> List[Job]:
        """Return normalized jobs matching ``criteria`` (may be empty)."""
        raise NotImplementedError

    def _stamp(self, jobs: List[Job]) -> List[Job]:
        """Attach this provider's identity/reliability to each job."""
        for job in jobs:
            job.source = self.name
            job.source_reliability = self.reliability
        return jobs


class SeedBackedProvider(JobProvider):
    """A provider that serves listings from the bundled seed dataset.

    Board-specific adapters subclass this and set :attr:`name`/:attr:`reliability`.
    To integrate a real API or scraper for a board, override :meth:`search` to
    call the live source and normalize its response into :class:`Job` objects;
    the rest of the pipeline requires no changes.
    """

    def search(self, criteria: SearchCriteria) -> List[Job]:
        category = CATEGORY_BY_KEY.get(criteria.category)
        jobs = fetch_seed_jobs(
            self.config.db_path,
            source=self.name,
            category=criteria.category if category else None,
        )
        logger.debug("%s: %d seed jobs for category=%s", self.name, len(jobs), criteria.category)
        return self._stamp(jobs)
