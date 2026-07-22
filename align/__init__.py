"""Align: local part-time job search for University of Nottingham students.

The package is organised into clear layers:

* :mod:`align.config`       - configuration and category mapping
* :mod:`align.models`       - typed data structures
* :mod:`align.adzuna_client`- server-side Adzuna API client
* :mod:`align.filters`      - hard filtering rules
* :mod:`align.ranking`      - weighted best-first ranking
* :mod:`align.orchestrator`- ties the pipeline together
"""

__all__ = ["config", "models", "adzuna_client", "filters", "ranking", "orchestrator"]

__version__ = "1.0.0"
