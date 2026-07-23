"""UK postcode -> coordinates lookup via the free postcodes.io API.

Server-side so the browser never makes the call. Returns a normalised postcode
plus latitude/longitude, or a clear error the UI can show.
"""

from __future__ import annotations

import re
from typing import Any, Dict

import requests

POSTCODES_IO = "https://api.postcodes.io/postcodes/{}"
POSTCODES_IO_REVERSE = "https://api.postcodes.io/postcodes"
REQUEST_TIMEOUT = 8

_UK_POSTCODE = re.compile(r"^[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}$", re.IGNORECASE)


def looks_like_postcode(value: str) -> bool:
    """Cheap format check before hitting the network."""
    return bool(_UK_POSTCODE.match((value or "").strip()))


def lookup_postcode(postcode: str) -> Dict[str, Any]:
    """Resolve a UK postcode to coordinates.

    Returns ``{"ok": True, "postcode", "lat", "lng"}`` on success, or
    ``{"ok": False, "error": ...}`` on any failure (bad format, not found,
    network error).
    """
    pc = (postcode or "").strip()
    if not looks_like_postcode(pc):
        return {"ok": False, "error": "That doesn't look like a UK postcode."}

    try:
        resp = requests.get(POSTCODES_IO.format(pc), timeout=REQUEST_TIMEOUT)
    except requests.RequestException:
        return {"ok": False, "error": "Couldn't reach the postcode service — try again."}

    if resp.status_code == 404:
        return {"ok": False, "error": "We couldn't find that postcode."}
    if resp.status_code != 200:
        return {"ok": False, "error": "Postcode lookup failed — try again."}

    try:
        result = (resp.json() or {}).get("result") or {}
    except ValueError:
        return {"ok": False, "error": "Postcode lookup returned bad data."}

    lat, lng = result.get("latitude"), result.get("longitude")
    if lat is None or lng is None:
        return {"ok": False, "error": "That postcode has no location data."}

    return {
        "ok": True,
        "postcode": result.get("postcode", pc.upper()),
        "lat": float(lat),
        "lng": float(lng),
    }


def reverse_geocode(lat: float, lng: float) -> Dict[str, Any]:
    """Resolve coordinates to the nearest UK postcode (for 'use my location')."""
    try:
        lat_f, lng_f = float(lat), float(lng)
    except (TypeError, ValueError):
        return {"ok": False, "error": "Invalid coordinates."}

    try:
        resp = requests.get(
            POSTCODES_IO_REVERSE,
            params={"lat": lat_f, "lon": lng_f, "limit": 1},
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException:
        return {"ok": False, "error": "Couldn't reach the postcode service — try again."}

    if resp.status_code != 200:
        return {"ok": False, "error": "Location lookup failed — try again."}

    try:
        results = (resp.json() or {}).get("result") or []
    except ValueError:
        return {"ok": False, "error": "Location lookup returned bad data."}

    if not results:
        return {"ok": False, "error": "No UK postcode found for your location."}

    top = results[0]
    return {
        "ok": True,
        "postcode": top.get("postcode", ""),
        "lat": float(top.get("latitude", lat_f)),
        "lng": float(top.get("longitude", lng_f)),
    }
