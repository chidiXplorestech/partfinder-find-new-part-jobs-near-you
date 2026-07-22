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

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .config import Settings

logger = logging.getLogger(__name__)


class PaymentError(RuntimeError):
    """Raised when a Stripe operation cannot be completed."""


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
