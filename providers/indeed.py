"""Indeed provider.

Indeed has no free public jobs API and actively blocks scraping, so this
adapter serves the bundled seed dataset for Indeed listings. To go fully live,
override :meth:`search` here with a call to a licensed Indeed feed/partner API
and normalize the response into :class:`~models.Job` objects — no other module
needs to change.
"""

from __future__ import annotations

from providers.base import SeedBackedProvider


class IndeedProvider(SeedBackedProvider):
    """Serves Indeed listings from the seed dataset."""

    name = "Indeed"
    reliability = 0.85
