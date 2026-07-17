"""Glassdoor provider.

Glassdoor's job data is not available through a free public API, so this adapter
serves the bundled seed dataset for Glassdoor listings. Override :meth:`search`
with a licensed data source to go live; normalize the response into
:class:`~models.Job` objects and the rest of the pipeline is unaffected.
"""

from __future__ import annotations

from providers.base import SeedBackedProvider


class GlassdoorProvider(SeedBackedProvider):
    """Serves Glassdoor listings from the seed dataset."""

    name = "Glassdoor"
    reliability = 0.80
