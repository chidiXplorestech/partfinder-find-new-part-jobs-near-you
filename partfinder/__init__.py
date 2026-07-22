"""PartFinder: local part-time job search for University of Nottingham students.

The package is organised into clear layers:

* :mod:`partfinder.config`       - configuration and category mapping
* :mod:`partfinder.models`       - typed data structures
* :mod:`partfinder.adzuna_client`- server-side Adzuna API client
* :mod:`partfinder.filters`      - hard filtering rules
* :mod:`partfinder.ranking`      - weighted best-first ranking
* :mod:`partfinder.orchestrator`- ties the pipeline together
"""

__all__ = ["config", "models", "adzuna_client", "filters", "ranking", "orchestrator"]

__version__ = "1.0.0"
