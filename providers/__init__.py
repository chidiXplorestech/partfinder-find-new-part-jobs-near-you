"""Job providers for PartFinder.

Each provider knows how to query one source and return normalized
:class:`~models.Job` objects. New providers only need to subclass
:class:`~providers.base.JobProvider` (or :class:`~providers.base.SeedBackedProvider`)
and be registered in :func:`build_default_providers`.
"""

from __future__ import annotations

from typing import List

from config import Config
from providers.adzuna import AdzunaProvider
from providers.base import JobProvider
from providers.glassdoor import GlassdoorProvider
from providers.indeed import IndeedProvider
from providers.linkedin import LinkedInProvider
from providers.totaljobs import TotalJobsProvider


def build_default_providers(config: Config) -> List[JobProvider]:
    """Return the providers PartFinder queries, in registration order.

    The live Adzuna provider is queried first; the board-specific adapters
    supply the bundled seed data (and are where real per-board integrations
    would slot in later).
    """
    return [
        AdzunaProvider(config),
        IndeedProvider(config),
        LinkedInProvider(config),
        GlassdoorProvider(config),
        TotalJobsProvider(config),
    ]


__all__ = [
    "JobProvider",
    "AdzunaProvider",
    "IndeedProvider",
    "LinkedInProvider",
    "GlassdoorProvider",
    "TotalJobsProvider",
    "build_default_providers",
]
