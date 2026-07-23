"""Stripe Checkout gateway for the £1 access paywall.

We use Stripe Checkout (a Stripe-hosted payment page) rather than collecting
card details ourselves. The app never sees a card number, which keeps it out of
PCI-compliance scope. The flow is:

    1. Frontend asks the server to create a Checkout Session (:meth:`create_checkout`).
    2. The browser is redirected to Stripe's hosted page to pay.
    3. Stripe redirects back to ``/pay/success?session_id=...``; the server
       confirms the payment with :meth:`is_paid` before unlocking access.

The gateway is intentionally defensive: if the ``stripe`` package or the API key
is missing it raises :class:`PaymentError`, which the routes translate into a
clean error state instead of a crash.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import uuid
from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple

import requests

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .config import Settings

logger = logging.getLogger(__name__)

#: GoCardless API version this integration is written against.
GC_API_VERSION = "2015-07-06"
GC_TIMEOUT = 12  # seconds


class PaymentError(RuntimeError):
    """Raised when a payment operation cannot be completed."""


class StripeGateway:
    """Thin wrapper around the Stripe Checkout API."""

    def __init__(self, settings: "Settings"):
        self._settings = settings

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _client(self):
        """Return the configured ``stripe`` module, or raise PaymentError."""
        if not self._settings.stripe_secret_key:
            raise PaymentError("Stripe is not configured (missing STRIPE_SECRET_KEY).")
        try:
            import stripe  # imported lazily so the app runs without the package
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise PaymentError(
                "The 'stripe' package is not installed. Run "
                "`pip install -r requirements.txt`."
            ) from exc
        stripe.api_key = self._settings.stripe_secret_key
        return stripe

    def _base_url(self, fallback: str) -> str:
        """Prefer the configured public base URL, else the request's own origin."""
        return self._settings.public_base_url or fallback.rstrip("/")

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def create_checkout(self, origin: str) -> str:
        """Create a one-time Checkout Session and return its redirect URL.

        Args:
            origin: The request origin (e.g. ``https://align.onrender.com``),
                used to build the success/cancel URLs when no PUBLIC_BASE_URL
                is set.

        Returns:
            The Stripe-hosted Checkout URL to redirect the browser to.

        Raises:
            PaymentError: If Stripe is misconfigured or the API call fails.
        """
        stripe = self._client()
        base = self._base_url(origin)
        try:
            checkout = stripe.checkout.Session.create(
                mode="payment",
                line_items=[
                    {
                        "price_data": {
                            "currency": self._settings.currency,
                            "product_data": {
                                "name": "Align — full job-match access",
                                "description": "Unlock unlimited swiping and Apply links.",
                            },
                            "unit_amount": self._settings.price_pence,
                        },
                        "quantity": 1,
                    }
                ],
                success_url=f"{base}/pay/success?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{base}/pay/cancel",
            )
        except Exception as exc:  # pragma: no cover - network/stripe errors
            logger.warning("Stripe checkout creation failed: %s", exc)
            raise PaymentError(f"Could not start checkout: {exc}") from exc

        if not checkout.url:
            raise PaymentError("Stripe did not return a checkout URL.")
        return checkout.url

    def is_paid(self, session_id: str) -> bool:
        """Return True when the given Checkout Session was actually paid.

        This is verified server-side against Stripe so a user cannot unlock
        access by forging the redirect URL.
        """
        if not session_id:
            return False
        stripe = self._client()
        try:
            checkout = stripe.checkout.Session.retrieve(session_id)
        except Exception as exc:  # pragma: no cover - network/stripe errors
            logger.warning("Stripe session retrieval failed: %s", exc)
            return False
        return getattr(checkout, "payment_status", None) == "paid"


# --------------------------------------------------------------------------- #
# GoCardless — verified server-side via the Billing Requests API
# --------------------------------------------------------------------------- #
#: Billing-request statuses that mean the money is in (Instant Bank Pay -> the
#: request is fulfilled once the payment is collected).
_GC_PAID_STATUSES = frozenset({"fulfilled"})


class GoCardlessGateway:
    """GoCardless Billing Requests gateway with server-side verification.

    Unlike a bare hosted payment link (which can only be *trusted* on redirect),
    this drives the flow through the GoCardless API using an access token, so the
    server can verify each £1 actually cleared before unlocking:

        1. :meth:`create_billing_request_flow` creates a billing request + flow
           and returns the ``authorisation_url`` to send the browser to.
        2. On return, :meth:`is_fulfilled` fetches the billing request and only
           reports paid when GoCardless says it is ``fulfilled``.
        3. :meth:`verify_webhook_signature` authenticates async webhook events so
           payments are captured even if the customer never returns to the tab.

    The access token is a secret and lives only in the environment; it is never
    placed in a URL, the client, or a tracked file.
    """

    def __init__(self, settings: "Settings", session: Optional[requests.Session] = None):
        self._settings = settings
        self._session = session or requests.Session()

    # ------------------------------------------------------------------ #
    # Configuration
    # ------------------------------------------------------------------ #
    @property
    def configured(self) -> bool:
        """True when an API access token is present."""
        return bool(self._settings.gocardless_access_token)

    def _headers(self, idempotent: bool = False) -> Dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self._settings.gocardless_access_token}",
            "GoCardless-Version": GC_API_VERSION,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if idempotent:
            headers["Idempotency-Key"] = str(uuid.uuid4())
        return headers

    def _url(self, path: str) -> str:
        return f"{self._settings.gocardless_api_base}{path}"

    # ------------------------------------------------------------------ #
    # Checkout: create a billing request + hosted flow
    # ------------------------------------------------------------------ #
    def create_billing_request_flow(
        self, success_url: str, exit_url: str, metadata: Optional[Dict[str, str]] = None
    ) -> Tuple[str, str]:
        """Create a one-off billing request and its hosted flow.

        Returns ``(authorisation_url, billing_request_id)``. The caller should
        persist the billing-request id (e.g. in the session) so the return trip
        can be verified against it.

        Raises:
            PaymentError: If GoCardless is not configured or the API rejects us.
        """
        if not self.configured:
            raise PaymentError("GoCardless is not configured (missing GOCARDLESS_ACCESS_TOKEN).")

        currency = (self._settings.currency or "gbp").upper()
        br_body = {
            "billing_requests": {
                "payment_request": {
                    "description": "Align — full job-match access (£1 unlock)",
                    "amount": self._settings.price_pence,
                    "currency": currency,
                }
            }
        }
        if metadata:
            br_body["billing_requests"]["metadata"] = metadata

        br = self._post("/billing_requests", br_body)
        billing_request = (br.get("billing_requests") or {})
        br_id = billing_request.get("id")
        if not br_id:
            raise PaymentError("GoCardless did not return a billing request id.")

        flow_body = {
            "billing_request_flows": {
                "redirect_uri": success_url,
                "exit_uri": exit_url,
                "links": {"billing_request": br_id},
            }
        }
        flow = self._post("/billing_request_flows", flow_body)
        auth_url = (flow.get("billing_request_flows") or {}).get("authorisation_url")
        if not auth_url:
            raise PaymentError("GoCardless did not return an authorisation URL.")
        return auth_url, br_id

    # ------------------------------------------------------------------ #
    # Verification
    # ------------------------------------------------------------------ #
    def is_fulfilled(self, billing_request_id: str) -> bool:
        """Return True only when GoCardless reports the billing request paid."""
        if not billing_request_id or not self.configured:
            return False
        try:
            data = self._get(f"/billing_requests/{billing_request_id}")
        except PaymentError as exc:
            logger.warning("GoCardless verification failed: %s", exc)
            return False
        status = (data.get("billing_requests") or {}).get("status")
        return status in _GC_PAID_STATUSES

    @staticmethod
    def verify_webhook_signature(body: bytes, signature: str, secret: str) -> bool:
        """Constant-time check of a GoCardless ``Webhook-Signature`` header.

        GoCardless signs the raw request body with HMAC-SHA256 using the webhook
        endpoint secret and sends the hex digest in the ``Webhook-Signature``
        header. We recompute and compare in constant time.
        """
        if not secret or not signature or body is None:
            return False
        computed = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(computed, signature)

    @staticmethod
    def fulfilled_billing_request_ids(events: Any) -> list:
        """Pull billing-request ids from webhook events that mean 'paid'.

        Accepts the parsed webhook payload's ``events`` list and returns the ids
        of billing requests that have been fulfilled (so the caller can persist
        them). Defensive against missing/oddly-shaped fields.
        """
        ids = []
        for ev in events or []:
            if not isinstance(ev, dict):
                continue
            if ev.get("resource_type") != "billing_requests":
                continue
            if ev.get("action") != "fulfilled":
                continue
            br_id = (ev.get("links") or {}).get("billing_request")
            if br_id:
                ids.append(br_id)
        return ids

    # ------------------------------------------------------------------ #
    # Low-level HTTP
    # ------------------------------------------------------------------ #
    def _post(self, path: str, body: Dict[str, Any]) -> Dict[str, Any]:
        try:
            resp = self._session.post(
                self._url(path), json=body, headers=self._headers(idempotent=True), timeout=GC_TIMEOUT
            )
        except requests.RequestException as exc:  # pragma: no cover - network
            raise PaymentError(f"Could not reach GoCardless: {exc}") from exc
        return self._parse(resp)

    def _get(self, path: str) -> Dict[str, Any]:
        try:
            resp = self._session.get(
                self._url(path), headers=self._headers(), timeout=GC_TIMEOUT
            )
        except requests.RequestException as exc:  # pragma: no cover - network
            raise PaymentError(f"Could not reach GoCardless: {exc}") from exc
        return self._parse(resp)

    @staticmethod
    def _parse(resp: requests.Response) -> Dict[str, Any]:
        if resp.status_code >= 400:
            snippet = (resp.text or "")[:300]
            raise PaymentError(f"GoCardless API error HTTP {resp.status_code}: {snippet}")
        try:
            return resp.json() or {}
        except ValueError as exc:
            raise PaymentError("GoCardless returned malformed JSON.") from exc
