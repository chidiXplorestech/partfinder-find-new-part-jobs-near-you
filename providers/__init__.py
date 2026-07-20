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
    """Return the providers PartFinder queries.

    When Adzuna credentials are configured we return **only** the live Adzuna
    provider, so results are real, current listings with real Apply links. When
    no credentials are set we fall back to the bundled seed adapters so the app
    still runs offline for a demo (their Apply links point to real board
    searches, never dead placeholders).
    """
    if config.adzuna_configured:
        return [AdzunaProvider(config)]
    return [
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
