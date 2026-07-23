"""Align Flask application entry point.

Run locally with::

    pip install -r requirements.txt
    python server.py

then open http://127.0.0.1:5000. This is a Flask app, not static files, so it
will NOT work under VS Code Live Server.
"""

from __future__ import annotations

import logging

from flask import (
    Flask,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from align import config
from align.adzuna_client import AdzunaClient
from align.config import (
    CATEGORY_MAP,
    CATEGORY_ORDER,
    DAYS_OF_WEEK,
    MIN_HOURLY_PAY,
    ASSUMED_WEEKLY_HOURS,
    WEEKS_PER_YEAR,
    get_settings,
)
from align.models import SearchQuery
from align.orchestrator import SearchOrchestrator
from align.payments import GoCardlessGateway, PaymentError
from align import accounts
from align.geocode import lookup_postcode, reverse_geocode

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
logger = logging.getLogger("align")


def create_app() -> Flask:
    """Application factory."""
    settings = get_settings()
    app = Flask(__name__)
    app.config["SECRET_KEY"] = settings.secret_key

    client = AdzunaClient(settings)
    orchestrator = SearchOrchestrator(client)
    gocardless = GoCardlessGateway(settings)

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
            paywall_active=settings.paywall_active,
            price_display=settings.price_display,
            payment_provider_label=settings.payment_provider_label,
            is_paid=bool(session.get("paid")),
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

        # Paywall gate: block matches until the user has paid (when enabled).
        if settings.paywall_active and not session.get("paid"):
            return (
                jsonify(
                    {
                        "ok": False,
                        "needs_payment": True,
                        "price": settings.price_display,
                        "error": "Unlock Align to see your matches.",
                    }
                ),
                402,
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

        origin = data.get("origin") or {}
        try:
            olat = float(origin["lat"]) if origin.get("lat") is not None else None
            olng = float(origin["lng"]) if origin.get("lng") is not None else None
        except (TypeError, ValueError, KeyError):
            olat = olng = None
        postcode = str(data.get("postcode") or "").strip() or None

        employment = str(data.get("employment", "part_time")).strip()
        if employment not in {"part_time", "full_time", "both"}:
            employment = "part_time"

        query = SearchQuery(
            category=category, days=days, radius=radius,
            origin_lat=olat, origin_lng=olng, postcode=postcode,
            employment=employment,
        )
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

    # -------------------------------------------------------------- #
    # Paywall (GoCardless: verified Billing Requests API, or hosted link)
    # -------------------------------------------------------------- #
    @app.route("/api/checkout", methods=["POST"])
    def api_checkout():
        """Return the URL the browser should be sent to in order to pay."""
        if not settings.paywall_active:
            # Paywall off -> treat everyone as already unlocked.
            session["paid"] = True
            return jsonify({"ok": True, "unlocked": True})

        if settings.payment_provider == "gocardless_api":
            # Verified mode: create a billing request + hosted flow via the API,
            # remember its id on the session so we can verify the return trip.
            base = settings.public_base_url or request.host_url.rstrip("/")
            try:
                auth_url, br_id = gocardless.create_billing_request_flow(
                    success_url=f"{base}/pay/success",
                    exit_url=f"{base}/pay/cancel",
                )
            except PaymentError as exc:
                logger.warning("GoCardless checkout failed: %s", exc)
                return jsonify({"ok": False, "error": str(exc)}), 502
            session["gc_br"] = br_id
            return jsonify({"ok": True, "checkout_url": auth_url})

        # Hosted GoCardless link — just hand the browser straight to it.
        return jsonify(
            {"ok": True, "checkout_url": settings.gocardless_payment_link}
        )

    @app.route("/api/payment-status")
    def api_payment_status():
        """Report whether this session has paid — used by the client to poll.

        Lets any tab detect completion (including the original tab when payment
        finishes in a new one, since the session cookie is shared). In verified
        GoCardless mode it re-checks the billing request and flips the session to
        paid the moment GoCardless confirms.
        """
        if session.get("paid"):
            return jsonify({"ok": True, "paid": True})
        if settings.payment_provider == "gocardless_api":
            br_id = session.get("gc_br", "")
            if br_id and (
                accounts.is_billing_request_paid(br_id) or gocardless.is_fulfilled(br_id)
            ):
                accounts.mark_billing_request_paid(br_id)
                session["paid"] = True
                session.pop("gc_br", None)
                return jsonify({"ok": True, "paid": True})
            return jsonify({"ok": True, "paid": False, "pending": bool(br_id)})
        return jsonify({"ok": True, "paid": False})

    @app.route("/pay/success")
    def pay_success():
        """Confirm payment, then unlock access for this browser session.

        * gocardless_api: the billing request is verified server-side against the
          GoCardless API (and/or a signed webhook) before unlocking.
        * gocardless (hosted link): can't be verified from a static redirect, so
          the unlock is gated on a shared ``token`` configured on the success
          redirect URL (trust-based when no token is set).
        """
        provider = settings.payment_provider

        if provider == "gocardless_api":
            # Verify against GoCardless: the billing request tied to this session
            # must actually be fulfilled (or already confirmed by a webhook).
            br_id = session.get("gc_br") or request.args.get("billing_request_id", "")
            if not br_id:
                return redirect(url_for("index", pay="failed"))
            if accounts.is_billing_request_paid(br_id) or gocardless.is_fulfilled(br_id):
                accounts.mark_billing_request_paid(br_id)
                session["paid"] = True
                session.pop("gc_br", None)
                return redirect(url_for("index", paid="1"))
            # Confirmation isn't in yet (the webhook may still be arriving). Don't
            # fail — show a "verifying…" state and let the client poll. Keep
            # gc_br on the session so the poll can re-check it.
            return redirect(url_for("index", verifying="1"))

        # Hosted-link mode: gate the unlock on the shared return token.
        expected = settings.payment_return_token
        supplied = request.args.get("token", "")
        if expected and supplied != expected:
            return redirect(url_for("index", pay="failed"))
        session["paid"] = True
        return redirect(url_for("index", paid="1"))

    @app.route("/pay/cancel")
    def pay_cancel():
        """User backed out of the payment page."""
        return redirect(url_for("index", pay="cancelled"))

    @app.route("/webhooks/gocardless", methods=["POST"])
    def gocardless_webhook():
        """Receive and verify GoCardless webhook events.

        The signature is checked against GOCARDLESS_WEBHOOK_SECRET before any
        event is trusted; fulfilled billing requests are persisted so a payment
        counts even if the customer never returns to the browser tab. Always
        returns 2xx quickly on a valid signature (GoCardless retries otherwise).
        """
        secret = settings.gocardless_webhook_secret
        signature = request.headers.get("Webhook-Signature", "")
        raw = request.get_data()  # exact bytes, required for the HMAC
        if not GoCardlessGateway.verify_webhook_signature(raw, signature, secret):
            return jsonify({"ok": False, "error": "Invalid signature."}), 498

        payload = request.get_json(silent=True) or {}
        events = payload.get("events") or []
        for br_id in GoCardlessGateway.fulfilled_billing_request_ids(events):
            accounts.mark_billing_request_paid(br_id)
            logger.info("GoCardless webhook: billing request %s fulfilled", br_id)
        return ("", 204)

    # -------------------------------------------------------------- #
    # Onboarding: postcode lookup + account creation
    # -------------------------------------------------------------- #
    @app.route("/api/geocode")
    def api_geocode():
        """Resolve a UK postcode -> coords, or coords -> nearest postcode.

        Pass ``?postcode=`` for a forward lookup, or ``?lat=&lng=`` for the
        reverse lookup used by 'use my location'. Both go server-side to
        postcodes.io.
        """
        lat, lng = request.args.get("lat"), request.args.get("lng")
        if lat is not None and lng is not None:
            result = reverse_geocode(lat, lng)
        else:
            result = lookup_postcode(request.args.get("postcode", ""))
        return jsonify(result), (200 if result.get("ok") else 400)

    @app.route("/api/signup", methods=["POST"])
    def api_signup():
        """Create an account (email + strong password, validated server-side)."""
        data = request.get_json(silent=True) or {}
        result = accounts.create_user(
            email=str(data.get("email", "")),
            password=str(data.get("password", "")),
            name=str(data.get("name", "")),
            postcode=str(data.get("postcode", "")),
        )
        if not result.get("ok"):
            return jsonify(result), 400
        session["uid"] = result["id"]
        session["name"] = str(data.get("name", ""))
        return jsonify({"ok": True})

    @app.route("/api/login", methods=["POST"])
    def api_login():
        """Sign an existing user in."""
        data = request.get_json(silent=True) or {}
        result = accounts.authenticate(
            str(data.get("email", "")), str(data.get("password", ""))
        )
        if not result.get("ok"):
            return jsonify(result), 401
        session["uid"] = result["id"]
        session["name"] = result.get("name", "")
        return jsonify({"ok": True, "name": result.get("name", "")})

    @app.route("/api/logout", methods=["POST"])
    def api_logout():
        """Fully sign the browser out: clear the whole server session.

        Drops the account (``uid``/``name``) and the paywall ``paid`` flag so the
        next visit starts clean. The client clears its own localStorage too.
        """
        session.clear()
        return jsonify({"ok": True})

    @app.route("/healthz")
    def healthz():
        """Simple health probe for deploys."""
        s = get_settings()
        return jsonify(
            {"status": "ok", "adzuna": s.adzuna_configured, "paywall": s.paywall_active}
        )

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
