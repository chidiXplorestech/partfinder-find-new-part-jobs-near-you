"""PartFinder Flask application entry point.

Run locally with::

    pip install -r requirements.txt
    python server.py

then open http://127.0.0.1:5000. This is a Flask app, not static files, so it
will NOT work under VS Code Live Server.
"""

from __future__ import annotations

import logging

from flask import Flask, jsonify, render_template, request

from partfinder import config
from partfinder.adzuna_client import AdzunaClient
from partfinder.config import (
    CATEGORY_MAP,
    CATEGORY_ORDER,
    DAYS_OF_WEEK,
    MIN_HOURLY_PAY,
    ASSUMED_WEEKLY_HOURS,
    WEEKS_PER_YEAR,
    get_settings,
)
from partfinder.models import SearchQuery
from partfinder.orchestrator import SearchOrchestrator

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
logger = logging.getLogger("partfinder")


def create_app() -> Flask:
    """Application factory."""
    settings = get_settings()
    app = Flask(__name__)
    app.config["SECRET_KEY"] = settings.secret_key

    client = AdzunaClient(settings)
    orchestrator = SearchOrchestrator(client)

    # -------------------------------------------------------------- #
    # Pages
    # -------------------------------------------------------------- #
    @app.route("/")
    def index():
        """Render the home page with its form controls."""
        categories = [
            {"key": key, "label": CATEGORY_MAP[key].label} for key in CATEGORY_ORDER
        ]
        return render_template(
            "index.html",
            categories=categories,
            days=DAYS_OF_WEEK,
            radii=config.ALLOWED_RADII,
            min_pay=MIN_HOURLY_PAY,
            adzuna_configured=settings.adzuna_configured,
        )

    # -------------------------------------------------------------- #
    # JSON search API (called by the frontend via fetch)
    # -------------------------------------------------------------- #
    @app.route("/api/search", methods=["POST"])
    def api_search():
        """Run a search and return ranked matches as JSON."""
        data = request.get_json(silent=True) or {}
        category = str(data.get("category", "")).strip()
        days = [str(d) for d in data.get("days", []) if isinstance(d, str)]
        try:
            radius = int(data.get("radius", 5))
        except (TypeError, ValueError):
            radius = 5

        if category not in CATEGORY_MAP:
            return (
                jsonify({"ok": False, "error": "Please choose a valid category."}),
                400,
            )

        if not get_settings().adzuna_configured:
            return (
                jsonify(
                    {
                        "ok": False,
                        "error": (
                            "The Adzuna API is not configured. Add ADZUNA_APP_ID "
                            "and ADZUNA_APP_KEY to your .env file and restart."
                        ),
                    }
                ),
                503,
            )

        query = SearchQuery(category=category, days=days, radius=radius)
        result = orchestrator.search(query)

        if result.error and result.is_empty:
            return jsonify({"ok": False, "error": result.error}), 502

        jobs = [
            job.to_dict(ASSUMED_WEEKLY_HOURS, WEEKS_PER_YEAR) for job in result.jobs
        ]
        return jsonify(
            {
                "ok": True,
                "jobs": jobs,
                "count": len(jobs),
                "notice": result.notice,
                "used_radius": result.used_radius,
                "category_label": CATEGORY_MAP[category].label,
            }
        )

    @app.route("/healthz")
    def healthz():
        """Simple health probe for deploys."""
        return jsonify({"status": "ok", "adzuna": get_settings().adzuna_configured})

    return app


app = create_app()


if __name__ == "__main__":
    settings = get_settings()
    if not settings.adzuna_configured:
        logger.warning(
            "ADZUNA_APP_ID / ADZUNA_APP_KEY are not set. Copy .env.example to "
            ".env and add your Adzuna credentials."
        )
    app.run(host=settings.host, port=settings.port, debug=settings.debug)
