# Align 🔥

**The Tinder for part-time jobs.** Swipe real, local part-time roles near the
University of Nottingham, match with the ones that fit, and apply in one tap.

Align pulls **live listings from the Adzuna GB Jobs API** (called
server-side, so the API key never touches the browser and there's no CORS),
filters out anything that isn't a genuine, fresh, living-wage part-time role,
ranks what's left by how well it matches *you*, and presents it as a dark,
Gen-Z swipe deck. Every "Apply" button is the real Adzuna listing link — no
fake jobs, ever.

---

## Features

- 🎴 **Swipe deck UI** — one tall gradient job card at a time with peeked cards
  behind for depth. Drag to swipe (left = Pass, right = Apply), tap the control
  bar, or use the ← / → arrow keys.
- 💯 **Match %** — the weighted ranking score surfaced as a compatibility number,
  with "why you two match" reason chips (distance, freshness, weekend-friendly,
  pay).
- 🔥 **"It's a Match!"** moment on Apply, plus a **Your Matches** shelf of saved
  roles.
- 🛰️ **Live Adzuna data**, called server-side from Flask.
- 🧹 **Honest filtering** — rejects full-time/senior/manager roles, anything
  paying under **£12.71/hr**, listings older than 14 days, and jobs outside your
  chosen radius of NG7 1NZ.
- 🪗 **Graceful search** — if strict filters return too little, Align
  automatically relaxes (drops the category tag, widens the radius) and tells
  you what it did, so the deck is rarely empty.
- 💳 **Optional £1 paywall** — an off-by-default Stripe Checkout gate that
  charges a one-time fee to unlock matches (see [Paywall](#paywall-1-unlock)).
- ♿ Explicit loading / empty / error / "all caught up" states, and
  `prefers-reduced-motion` support.

---

## Architecture

```
align/
├── config.py          # constants, category → Adzuna mapping, ranking weights
├── models.py          # SearchQuery + Job dataclasses (typed)
├── adzuna_client.py    # server-side Adzuna API client + normalisation
├── filters.py         # hard rules (pay, freshness, distance, seniority)
├── ranking.py         # weighted best-first score, Match %, reason chips
└── orchestrator.py    # tiered search pipeline (fetch → filter → rank)
server.py              # Flask app: home page + /api/search JSON endpoint
templates/index.html   # single-page shell (Jinja)
static/css/style.css   # the dark "Tinder 2025" theme
static/js/app.js       # swipe deck controller (vanilla JS + GSAP Draggable)
tests/                 # unit tests for filters + ranking
```

The frontend is HTML5 + modern CSS + vanilla JS with **GSAP** (from CDN) for the
swipe/entrance animations. No frontend frameworks. The browser only ever talks to
this Flask server's `/api/search` endpoint — never Adzuna directly.

### How ranking works

Each surviving job earns five component scores in `[0, 1]`, combined with the
weights in `config.RANKING_WEIGHTS` (they sum to 1.0):

| Component     | Weight | Meaning                                             |
|---------------|--------|-----------------------------------------------------|
| Distance      | 0.35   | Closer to NG7 1NZ scores higher                     |
| Freshness     | 0.25   | Newer postings score higher                         |
| Availability  | 0.20   | Weekend/flexible signals vs. your selected days     |
| Pay           | 0.12   | Living-wage-friendly entry-level pay                 |
| Source        | 0.08   | Source reliability (real Adzuna apply link)          |

The final score is shown as a **Match %** (mapped to a friendly 60–99% band, so
nothing that already passed the hard filters reads as a "bad" match). Ties break
on distance, then posting date.

---

## Getting started

### 1. Prerequisites

- Python 3.11+
- A free Adzuna API key — sign up at <https://developer.adzuna.com/>. Your
  **App ID** and **App Key** are on the access-details page.

### 2. Install

```bash
pip install -r requirements.txt
```

### 3. Configure secrets

```bash
cp .env.example .env
# then edit .env and add your real ADZUNA_APP_ID / ADZUNA_APP_KEY
```

`.env` is git-ignored — never commit real keys. If your keys have ever been
shared (e.g. pasted in chat), **regenerate the App Key** in the Adzuna dashboard
before deploying.

### 4. Run

```bash
python server.py
```

Open <http://127.0.0.1:5000>.

> ⚠️ This is a **Flask app, not static files** — it will *not* work under VS Code
> Live Server. Run it with `python server.py`.

---

## Environment variables

| Variable          | Required | Default     | Description                          |
|-------------------|----------|-------------|--------------------------------------|
| `ADZUNA_APP_ID`   | ✅       | —           | Adzuna application ID                 |
| `ADZUNA_APP_KEY`  | ✅       | —           | Adzuna application key                |
| `SECRET_KEY`      | ➖       | dev value   | Flask session secret                  |
| `HOST`            | ➖       | `127.0.0.1` | Bind host                             |
| `PORT`            | ➖       | `5000`      | Bind port                             |
| `FLASK_DEBUG`     | ➖       | `0`         | `1` to enable debug/auto-reload       |
| `PAYWALL_ENABLED` | ➖       | `0`         | `1` to require the £1 payment          |
| `GOCARDLESS_PAYMENT_LINK` | ➖ | —      | GoCardless hosted pay link (Option A)  |
| `PAYMENT_RETURN_TOKEN` | ➖  | —          | Secret guarding the GoCardless return  |
| `STRIPE_SECRET_KEY`| ➖      | —           | Stripe secret key (Option B fallback)  |
| `PRICE_PENCE`     | ➖       | `100`       | Access price in pence (100 = £1.00)   |
| `CURRENCY`        | ➖       | `gbp`       | Currency code                         |
| `PUBLIC_BASE_URL` | ➖       | —           | Deployed URL, for payment return links |

---

## Tests

```bash
python -m pytest -q
```

Covers the haversine geometry, every hard filter rule (including the "never drop
a job just because Adzuna omitted its coordinates or salary" guarantee), the
weighted scoring, Match % banding, and best-first ordering.

---

## Paywall (£1 unlock)

Align ships with an **optional** one-time paywall. It is **off by default**
(`PAYWALL_ENABLED=0` → the app is completely free). Two payment methods are
supported; the app picks GoCardless if a link is set, otherwise Stripe.

### Option A — GoCardless payment link (simplest)

A [GoCardless](https://gocardless.com) hosted payment link is just a URL you
send payers to — no API keys, no card handling on your side.

1. In your GoCardless dashboard, create a payment link for £1.
2. Set its **success redirect URL** to
   `https://your-app-url/pay/success?token=YOUR_SECRET_TOKEN`
   (invent any value for the token).
3. Set these environment variables (in `.env` locally, or your host dashboard):
   ```env
   PAYWALL_ENABLED=1
   GOCARDLESS_PAYMENT_LINK=https://pay.gocardless.com/XXXXXXXX
   PAYMENT_RETURN_TOKEN=YOUR_SECRET_TOKEN
   PUBLIC_BASE_URL=https://your-app-url
   ```
4. Restart. "Find my matches" now shows a £1 unlock screen; the CTA sends the
   user to your GoCardless link, and GoCardless redirects them back to unlock.

**Security note:** a static payment link can't be verified from its redirect the
way a Stripe session can, so the unlock is gated on the shared
`PAYMENT_RETURN_TOKEN` — only a return from *your* configured GoCardless link
carries the right token. For airtight verification, add a GoCardless webhook
(`payments.confirmed`) that records paid customers server-side; that's the
recommended next step for production.

### Option B — Stripe Checkout (fallback)

If you leave `GOCARDLESS_PAYMENT_LINK` blank but set a `STRIPE_SECRET_KEY`
(from <https://dashboard.stripe.com/apikeys>), the app uses Stripe Checkout
instead. Here the payment **is** verified server-side (`payment_status == "paid"`)
so the return URL can't be forged. Test with card `4242 4242 4242 4242`, any
future expiry and any CVC.

> 💡 Either way, payment unlocks access for the current browser session. For
> permanent per-user accounts you'd add a login + database — out of scope here.

---

## Deploy (free, shareable URL)

The repo includes a `Procfile`, `runtime.txt` and a `render.yaml` blueprint, so
it deploys as-is to [Render](https://render.com) or [Railway](https://railway.app).

**Render — one click (recommended)**

1. Push this repo to your GitHub.
2. In Render: **New → Blueprint** → connect the repo. Render reads `render.yaml`
   and creates the service for you.
3. When prompted, paste `ADZUNA_APP_ID` and `ADZUNA_APP_KEY` (and, if you want
   the paywall, `STRIPE_SECRET_KEY` + set `PAYWALL_ENABLED=1`). `SECRET_KEY` is
   generated automatically.
4. Deploy. You get a public URL like `https://align.onrender.com` — set that as
   `PUBLIC_BASE_URL` if you enabled the paywall.

**Render — manual**

1. New → Web Service → connect this repo.
2. Build command: `pip install -r requirements.txt`
3. Start command: `gunicorn server:app --bind 0.0.0.0:$PORT`
4. Add env vars `ADZUNA_APP_ID`, `ADZUNA_APP_KEY`, `SECRET_KEY` in the dashboard.

**Railway**

1. New Project → Deploy from repo. Railway auto-detects the `Procfile`.
2. Add the same environment variables under *Variables*.

Health probe: `GET /healthz`.

---

## Notes & limitations

- Adzuna caps `results_per_page` at 50 and its data quality varies (salary and
  coordinates are often missing). Align treats missing data as *unknown, not
  disqualifying*, and leans on Adzuna's own `where` + `distance` geo-filter as
  the primary distance guard.
- The origin is fixed to **57 Albert Grove, Nottingham, NG7 1NZ**
  (lat 52.9515, lng −1.1789).
