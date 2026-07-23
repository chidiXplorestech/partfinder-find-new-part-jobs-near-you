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

## Onboarding (first launch, the full intended sequence)

The onboarding is one continuous flow, not just intro slides. Order:

1. **Intro slides (×3)** — swipeable, skippable, remembered in localStorage.
   1. *"Stop scrolling through endless job boards."* — the overwhelm.
   2. *"Swipe through real jobs in seconds."* — teaches ✕ pass / ♥ shortlist.
   3. *"See one you like? One tap to apply."* — application flies off.
2. **Where are you?** *(planned)* — **postcode / location input** that sets the
   search origin, replacing the hardcoded NG7 1NZ so it works for any user.
3. **Create your account** *(planned)* — **email + password on one page**, with
   an **email-validity check** and **strong-password** enforcement. Ties saved
   jobs and the £1 unlock to a person, not just a device cookie.
4. **Unlock Align — £1** *(paywall, move here)* — surface the "less than a
   coffee" £1 unlock **right after onboarding**, not only at first search.

→ then into the app.

Onboarding (and the app) should feel like the **Tinder rebrand for jobs** —
bold, expressive, editorial — carried by **photographic Magnific-generated
imagery** on the slides (and wherever it lifts the UI), not the current
"clean fintech" look.

## App flow & screens

`Onboarding (slides → postcode → account → £1 paywall) → Home → Deck (swipe) → Job detail → Apply → Matches`

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

## Build status

- **Done:** intro slides, home, deck, job detail (full-screen, back + ✕),
  Apply + application-sent, matches, states, £1 GoCardless/Stripe paywall,
  Mastercard palette, bespoke SVG art. "View job" doubled-card bug fixed.
- **Planned (onboarding sequence above):** postcode/location input; email +
  password account setup (validity + strong-password); paywall moved to
  straight after onboarding.
- **Planned (polish):** consistent **home / back / X** on every screen (no dead
  ends); photographic **Magnific** imagery; bolder Tinder-rebrand visual pivot.

## Conventions for future work

- Keep it **honest** (no fake data/counts) and **lightweight** (few taps).
- Server-side Adzuna only; never call it from the browser.
- Match the existing token-driven CSS and the reserved-red rule.
- Verify UI changes by actually driving the app before committing.
