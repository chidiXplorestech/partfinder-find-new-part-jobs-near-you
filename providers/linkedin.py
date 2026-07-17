"""LinkedIn Jobs provider.

LinkedIn does not offer a free jobs API for this use case, so this adapter
serves the bundled seed dataset for LinkedIn listings. A real integration could
plug in a licensed LinkedIn partner API or a hosted scraper (e.g. an Apify
actor) here: override :meth:`search`, fetch the listings, and normalize them
into :class:`~models.Job` objects. The rest of the pipeline is unaffected.
"""

from __future__ import annotations

from providers.base import SeedBackedProvider


class LinkedInProvider(SeedBackedProvider):
    """Serves LinkedIn Jobs listings from the seed dataset."""

    name = "LinkedIn"
    reliability = 0.90
