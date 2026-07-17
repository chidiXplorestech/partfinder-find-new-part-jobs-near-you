"""Totaljobs provider.

Totaljobs has no free public API, so this adapter serves the bundled seed
dataset for Totaljobs listings. Override :meth:`search` with a licensed feed to
go live; normalize the response into :class:`~models.Job` objects and the rest
of the pipeline is unaffected.
"""

from __future__ import annotations

from providers.base import SeedBackedProvider


class TotalJobsProvider(SeedBackedProvider):
    """Serves Totaljobs listings from the seed dataset."""

    name = "Totaljobs"
    reliability = 0.82
