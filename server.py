"""Flask web layer for PartFinder.

Thin controller: it validates the home-page form, builds a
:class:`~models.SearchCriteria`, delegates to :class:`~partfinder.PartFinder`,
and renders the results table. All business logic lives in the pipeline modules.

Run locally with:  ``python server.py``
"""

from __future__ import annotations

import logging

from flask import Flask, render_template, request

from config import CATEGORIES, CATEGORY_BY_KEY, DAYS, Config
from database import init_db
from models import SearchCriteria
from partfinder import PartFinder
from utils import relative_date

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


def create_app(config: Config | None = None) -> Flask:
    """Application factory. Builds the DB, wires routes, returns the app."""
    config = config or Config.from_env()

    app = Flask(__name__)
    app.config["SECRET_KEY"] = config.secret_key
    app.config["PARTFINDER"] = config
    app.jinja_env.filters["relative_date"] = relative_date

    # Ensure the seed database exists (no-op if already populated).
    init_db(config.db_path, config.seed_path)

    finder = PartFinder(config)

    @app.route("/")
    def index():
        """Render the search form."""
        return render_template(
            "index.html",
            categories=CATEGORIES,
            days=DAYS,
            radius_options=config.radius_options,
            default_radius=config.default_radius,
            origin=config.origin_address,
            live=config.adzuna_configured,
        )

    @app.route("/results", methods=["GET", "POST"])
    def results():
        """Parse the form, run a search, and render the ranked table."""
        source = request.form if request.method == "POST" else request.args
        category = (source.get("category") or "").strip()
        selected_days = [d for d in source.getlist("days") if d in DAYS]
        try:
            radius = int(source.get("radius", config.default_radius))
        except (TypeError, ValueError):
            radius = config.default_radius
        if radius not in config.radius_options:
            radius = config.default_radius

        error = None
        if category not in CATEGORY_BY_KEY:
            error = "Please choose a job category."

        jobs = []
        criteria = None
        if error is None:
            criteria = SearchCriteria(category=category, days=selected_days, radius=radius)
            jobs = finder.run_search(criteria)

        return render_template(
            "results.html",
            jobs=jobs,
            error=error,
            criteria=criteria,
            category_label=CATEGORY_BY_KEY[category].label if category in CATEGORY_BY_KEY else "",
            origin=config.origin_address,
            live=config.adzuna_configured,
        )

    return app


app = create_app()


if __name__ == "__main__":
    import os
    import threading
    import webbrowser

    conf = app.config["PARTFINDER"]
    # Port 5000 is taken by AirPlay Receiver on macOS, so default to 5050.
    port = int(os.environ.get("PORT", "5050"))
    url = f"http://127.0.0.1:{port}"

    mode = "LIVE (Adzuna)" if conf.adzuna_configured else "DEMO (sample data — add Adzuna keys to .env for live jobs)"
    print("\n" + "=" * 52)
    print("  PartFinder is starting…")
    print(f"  Mode:  {mode}")
    print(f"  Open:  {url}")
    print("  Stop:  press CTRL+C")
    print("=" * 52 + "\n")

    # Auto-open the browser once (skip the reloader's second process).
    if not conf.debug and os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        threading.Timer(1.3, lambda: webbrowser.open(url)).start()

    app.run(host="127.0.0.1", port=port, debug=conf.debug)
