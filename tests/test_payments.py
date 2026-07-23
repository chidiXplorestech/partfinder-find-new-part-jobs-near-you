"""Tests for the GoCardless verified-payment gateway and helpers.

Network is never touched: the gateway takes an injected ``requests.Session`` so
we can stub the GoCardless API responses, mirroring the Adzuna client tests.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import tempfile

import pytest

from align.config import Settings
from align.payments import GoCardlessGateway, PaymentError


# --------------------------------------------------------------------------- #
# Fakes
# --------------------------------------------------------------------------- #
class _FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = text or json.dumps(self._payload)

    def json(self):
        return self._payload


class _FakeSession:
    """Records requests and returns queued responses in order."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def post(self, url, json=None, headers=None, timeout=None):
        self.calls.append(("POST", url, json, headers))
        return self._responses.pop(0)

    def get(self, url, headers=None, timeout=None):
        self.calls.append(("GET", url, None, headers))
        return self._responses.pop(0)


def _settings(**over):
    base = dict(gocardless_access_token="sandbox_tok", gocardless_environment="sandbox",
                price_pence=100, currency="gbp", gocardless_webhook_secret="whsec")
    base.update(over)
    # Settings is a dataclass with env-driven defaults; construct then override.
    s = Settings()
    for k, v in base.items():
        setattr(s, k, v)
    return s


# --------------------------------------------------------------------------- #
# Configuration / provider selection
# --------------------------------------------------------------------------- #
def test_provider_prefers_api_token_over_link():
    s = _settings(gocardless_access_token="live_x",
                  gocardless_payment_link="https://pay.gocardless.com/BRT")
    assert s.payment_provider == "gocardless_api"


def test_api_base_switches_by_environment():
    assert _settings(gocardless_environment="sandbox").gocardless_api_base.endswith("api-sandbox.gocardless.com")
    assert _settings(gocardless_environment="live").gocardless_api_base == "https://api.gocardless.com"


# --------------------------------------------------------------------------- #
# Checkout: billing request + flow creation
# --------------------------------------------------------------------------- #
def test_create_billing_request_flow_happy_path():
    sess = _FakeSession([
        _FakeResponse(201, {"billing_requests": {"id": "BRQ123", "status": "pending"}}),
        _FakeResponse(201, {"billing_request_flows": {"authorisation_url": "https://pay.gocardless.com/flow/RE1"}}),
    ])
    gw = GoCardlessGateway(_settings(), session=sess)
    url, br_id = gw.create_billing_request_flow("https://app/pay/success", "https://app/pay/cancel")
    assert url == "https://pay.gocardless.com/flow/RE1"
    assert br_id == "BRQ123"
    # First call creates the billing request with the £1 amount in GBP.
    method, endpoint, body, headers = sess.calls[0]
    assert endpoint.endswith("/billing_requests")
    assert body["billing_requests"]["payment_request"] == {
        "description": "Align — full job-match access (£1 unlock)",
        "amount": 100,
        "currency": "GBP",
    }
    assert headers["Authorization"] == "Bearer sandbox_tok"
    assert "Idempotency-Key" in headers
    # Second call wires the flow to the billing request + redirect URIs.
    _, flow_endpoint, flow_body, _ = sess.calls[1]
    assert flow_endpoint.endswith("/billing_request_flows")
    assert flow_body["billing_request_flows"]["links"]["billing_request"] == "BRQ123"
    assert flow_body["billing_request_flows"]["redirect_uri"] == "https://app/pay/success"


def test_create_flow_raises_without_token():
    gw = GoCardlessGateway(_settings(gocardless_access_token=""))
    with pytest.raises(PaymentError):
        gw.create_billing_request_flow("s", "c")


def test_create_flow_raises_on_api_error():
    sess = _FakeSession([_FakeResponse(401, {"error": "unauthorized"}, text="unauthorized")])
    gw = GoCardlessGateway(_settings(), session=sess)
    with pytest.raises(PaymentError):
        gw.create_billing_request_flow("s", "c")


# --------------------------------------------------------------------------- #
# Verification
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("status,expected", [
    ("fulfilled", True),
    ("pending", False),
    ("cancelled", False),
    (None, False),
])
def test_is_fulfilled(status, expected):
    payload = {"billing_requests": {"id": "BRQ1", "status": status}}
    sess = _FakeSession([_FakeResponse(200, payload)])
    gw = GoCardlessGateway(_settings(), session=sess)
    assert gw.is_fulfilled("BRQ1") is expected


def test_is_fulfilled_false_on_network_error():
    sess = _FakeSession([_FakeResponse(500, {}, text="boom")])
    gw = GoCardlessGateway(_settings(), session=sess)
    assert gw.is_fulfilled("BRQ1") is False


def test_is_fulfilled_false_without_id():
    gw = GoCardlessGateway(_settings())
    assert gw.is_fulfilled("") is False


# --------------------------------------------------------------------------- #
# Webhook signature + event parsing
# --------------------------------------------------------------------------- #
def test_verify_webhook_signature_roundtrip():
    body = b'{"events":[]}'
    secret = "whsec"
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert GoCardlessGateway.verify_webhook_signature(body, sig, secret) is True
    assert GoCardlessGateway.verify_webhook_signature(body, sig, "wrong") is False
    assert GoCardlessGateway.verify_webhook_signature(body, "deadbeef", secret) is False
    assert GoCardlessGateway.verify_webhook_signature(body, "", secret) is False
    assert GoCardlessGateway.verify_webhook_signature(body, sig, "") is False


def test_fulfilled_ids_extraction():
    events = [
        {"resource_type": "billing_requests", "action": "fulfilled",
         "links": {"billing_request": "BRQ_A"}},
        {"resource_type": "billing_requests", "action": "created",
         "links": {"billing_request": "BRQ_B"}},
        {"resource_type": "payments", "action": "confirmed",
         "links": {"payment": "PM1"}},
        "junk",
    ]
    assert GoCardlessGateway.fulfilled_billing_request_ids(events) == ["BRQ_A"]
    assert GoCardlessGateway.fulfilled_billing_request_ids(None) == []


# --------------------------------------------------------------------------- #
# Persistent paid store
# --------------------------------------------------------------------------- #
def test_paid_billing_request_store(monkeypatch):
    from align import accounts
    with tempfile.TemporaryDirectory() as d:
        monkeypatch.setattr(accounts, "_DB_PATH", os.path.join(d, "t.db"))
        assert accounts.is_billing_request_paid("BRQ9") is False
        accounts.mark_billing_request_paid("BRQ9")
        assert accounts.is_billing_request_paid("BRQ9") is True
        # Idempotent, and blank ids are ignored.
        accounts.mark_billing_request_paid("BRQ9")
        accounts.mark_billing_request_paid("")
        assert accounts.is_billing_request_paid("") is False
