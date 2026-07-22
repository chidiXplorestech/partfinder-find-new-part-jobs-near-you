# Align — project brief

> **Stop searching. Start swiping. Find your next job faster.**

## What Align is

Align is a **Tinder-style job-discovery web app** for people who want **local,
part-time work fast** — students, weekend/retail/hospitality workers, young
professionals. Instead of trawling job boards, you **swipe through one job at a
time**: right to shortlist, left to pass, tap for details, one tap to apply.

- **Live data:** jobs come from the **Adzuna GB Jobs API**, called **server-side**
  from Flask (hides the API key, avoids CORS). Every "Apply" link is the real
  Adzuna `redirect_url` — **no fabricated jobs, ever**.
- **We are not an ATS/LinkedIn/Indeed.** We don't host jobs or take CVs. When a
  user applies, we send them **straight to the employer's site** — that's where
  their CV goes.
- **Honest by design:** no fake counts, no dark patterns, no manipulative
  subscriptions. If data is missing we say so; we never invent it.
- **Business model:** a symbolic **£1 one-time unlock** ("less than a coffee")
  that covers API + infrastructure. Payment via **GoCardless** hosted link
  (Stripe Checkout is a fallback). Off by default (`PAYWALL_ENABLED=0`).

Search origin currently defaults to **57 Albert Grove, Nottingham, NG7 1NZ**
(hardcoded — a per-user postcode input is a known next step).

## Onboarding (first launch only, skippable, remembered in localStorage)

Three swipeable slides, then the app:

1. **"Stop scrolling through endless job boards."** — the overwhelm (a job-board
   pile with a soft-red overload badge).
2. **"Swipe through real jobs in seconds."** — teaches the gesture (a card
   flanked by ✕ pass / ♥ shortlist cues).
3. **"See one you like? One tap to apply."** — a job card sending an application
   flying off as a paper plane.

## App flow & screens

`Onboarding → Home (set up search) → Deck (swipe) → Job detail → Apply → Matches`

- **Home:** category (Sales, Customer Service, Office, Remote, Retail, Housing,
  Contract) · available days · radius (3/5/10/15 mi) · "Start swiping".
  Shows a status pill and a time-of-day greeting.
- **Deck:** one tall card at a time with peeked cards behind. Card shows company
  tile, **match %** ring, title, salary/type/distance pills, "why it fits"
  reasons. Controls: **✕ Pass · View job · ♥ Shortlist**. Drag-to-swipe (GSAP),
  buttons, and ←/→ arrow keys all work.
- **Job detail:** full-screen page (back + title + ✕ close) with description,
  posted/type/pay/source, shortlist, and **Apply on employer site**.
- **Application sent:** confirmation moment after Apply ("Application on its
  way…"), with Keep swiping / View my applications.
- **Matches (profile sheet):** Saved / Applied tabs, persisted in localStorage.
- **Paywall:** "Less than a coffee" £1 unlock (only when enabled).
- **States:** skeleton **loading** (radar), **empty**, **error** (broken-link),
  **"all caught up"** — each with bespoke copy and illustration.

## UI / UX principles

- **Mobile-first, single centred phone column** (max-width ~430px).
- **Design system (Mastercard-inspired):** accent **orange `#FF5F00`**, warm
  **amber `#F79E1B`** highlights (salary/ticks), **black `#141414`** ink on a
  **warm off-white `#F6F5F2`** canvas. **Red `#E2413B` is reserved** for
  warnings / Pass / errors only — never a happy-path colour.
- **Type:** SF Pro on Apple devices, Inter elsewhere; big, tight headings.
- **Illustrations:** hand-built **inline SVG/CSS** from the design tokens —
  crisp at any DPR, no network, no stock. (Optional photographic art can be
  dropped into `static/img/` later.)
- **Motion:** GSAP (+ Draggable) for swipe physics, sheet transitions, entrance
  reveals and celebratory beats; **all respect `prefers-reduced-motion`**.
- **Accessibility:** 44px+ tap targets, focus-visible rings, dialog roles,
  Escape to close, keyboard swiping, honest microcopy.

## Tech / where things live

- **Backend:** Python + **Flask** + Jinja. `server.py` (routes: `/`,
  `/api/search`, `/api/checkout`, `/pay/*`, `/healthz`).
- **Pipeline package `align/`:** `config` · `models` · `adzuna_client` ·
  `filters` (pay ≥ £12.71/hr, ≤14 days old, distance, seniority reject) ·
  `ranking` (weighted best-first → match %) · `orchestrator` (tiered search
  that widens gracefully) · `payments` (GoCardless/Stripe).
- **Frontend:** `templates/index.html`, `static/css/style.css`,
  `static/js/app.js` (vanilla JS, no frameworks; GSAP from CDN).
- **Tests:** `tests/` (filters + ranking). Run `python -m pytest -q`.
- **Run:** `pip install -r requirements.txt` → copy `.env.example` to `.env`
  (add Adzuna keys) → `python server.py` → http://127.0.0.1:5000.
  Secrets: `ADZUNA_APP_ID`, `ADZUNA_APP_KEY`, `SECRET_KEY` (+ paywall vars).
  `.env` is git-ignored — never commit real keys.

## Conventions for future work

- Keep it **honest** (no fake data/counts) and **lightweight** (few taps).
- Server-side Adzuna only; never call it from the browser.
- Match the existing token-driven CSS and the reserved-red rule.
- Verify UI changes by actually driving the app before committing.
