# PartFinder

Find legitimate, local **part-time jobs** around Nottingham — built for
University of Nottingham students. PartFinder searches trusted job boards,
filters out full-time and senior roles, keeps only listings posted within the
last two weeks, and ranks the best matches by distance, freshness, availability,
pay, and source reliability.

Searches are centred on **57 Albert Grove, Nottingham, NG7 1NZ**.

---

## Highlights

- **Live job data** via the free [Adzuna](https://developer.adzuna.com/) API,
  which aggregates listings from Indeed, Totaljobs, Reed, LinkedIn, CV-Library
  and more — so you are not limited to any single board.
- **Works offline out of the box.** With no API keys, PartFinder serves a
  bundled seed dataset of realistic Nottingham roles, so the app runs on first
  clone. Add keys to switch on live results.
- **Student-first filtering.** Keeps part-time, weekend, casual, student,
  temporary and zero-hour roles; rejects full-time, senior, manager, graduate
  and director roles. Enforces a **£12.71/hour pay floor** and never shows
  anything older than 14 days.
- **Gen Z / Tinder-inspired UI.** Editorial serif headlines, the flame
  gradient, pill controls, and swipe-style result cards.
- **Transparent ranking** by distance → posting date → availability match →
  pay → source reliability.
- **Minimal, fast, responsive UI** — no frontend frameworks, no clutter.

---

## Tech stack

| Layer     | Technology                                   |
|-----------|----------------------------------------------|
| Frontend  | HTML5, CSS3, vanilla JavaScript (responsive) |
| Backend   | Python, Flask, Jinja templates               |
| Database  | SQLite (isolated behind `database.py`)       |
| Live data | Adzuna Jobs API (free tier)                  |

---

## Installation

Requires **Python 3.10+**.

```bash
git clone <your-repo-url>
cd partfinder-find-new-part-jobs-near-you

# (recommended) create a virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

## Running locally

```bash
cp .env.example .env             # optional: add Adzuna keys for live data
python server.py
```

Then open <http://127.0.0.1:5000>.

On first run the SQLite database is created and seeded automatically. Without
Adzuna keys you will see a "demo data" notice and results come from the seed
dataset; add keys (below) to get live listings.

### Getting free Adzuna keys

1. Register at <https://developer.adzuna.com/>.
2. Copy your `app_id` and `app_key` into `.env`:
   ```
   ADZUNA_APP_ID=your_app_id
   ADZUNA_APP_KEY=your_app_key
   ```
3. Restart `python server.py`. Live results now merge in and are deduplicated
   against the seed data.

## Running the tests

```bash
python -m pytest tests/
```

---

## Environment variables

| Variable          | Required | Default                | Purpose                                             |
|-------------------|----------|------------------------|-----------------------------------------------------|
| `ADZUNA_APP_ID`   | No       | _(none)_               | Adzuna API app id. Enables live job data.           |
| `ADZUNA_APP_KEY`  | No       | _(none)_               | Adzuna API app key. Enables live job data.          |
| `SECRET_KEY`      | No       | `dev-secret-change-me` | Flask session/flash signing key.                    |
| _pay floor_       | n/a      | `£12.71/hour`          | Set in `config.py` (`minimum_hourly_pay`).          |
| `DB_PATH`         | No       | `partfinder.sqlite3`   | SQLite database file path.                           |
| `RESULTS_LIMIT`   | No       | `50`                   | Max number of jobs shown per search.                |
| `FLASK_DEBUG`     | No       | `0`                    | Set to `1` for Flask debug mode during development. |

All variables are read from the environment, optionally via a local `.env`
file (git-ignored). Never commit real keys.

---

## Folder structure

```
partfinder/
├── server.py            # Flask app factory + routes (entry point)
├── config.py            # Central config: origin, categories, thresholds, keys
├── models.py            # Job and SearchCriteria dataclasses
├── database.py          # SQLite storage + seed loading
├── search.py            # Query providers, normalize, deduplicate
├── filters.py           # Date / salary / distance / employment filtering
├── ranking.py           # Weighted scoring and sorting
├── partfinder.py        # Orchestrator: search -> filter -> rank
├── utils.py             # Shared helpers (haversine, dates, pay formatting)
├── requirements.txt
│
├── providers/           # Pluggable job sources
│   ├── base.py          # JobProvider ABC + SeedBackedProvider
│   ├── adzuna.py        # Live Adzuna API provider
│   ├── indeed.py        # Board adapters (seed-backed; extension points)
│   ├── linkedin.py
│   ├── glassdoor.py
│   └── totaljobs.py
│
├── templates/           # Jinja templates
│   ├── base.html
│   ├── index.html
│   └── results.html
│
├── static/
│   ├── css/style.css
│   ├── js/main.js
│   └── images/logo.svg
│
├── data/
│   └── seed_jobs.json   # Bundled offline dataset
│
└── tests/
    └── test_pipeline.py
```

### How a search flows

```
Home form (index.html)
  -> server.py            parse category, days, radius
  -> partfinder.py        run_search(criteria)
       -> search.py        query providers, normalize, dedup
            -> providers/  Adzuna (live) + board adapters (seed)
       -> filters.py       drop old / senior / too-far / full-time roles
       -> ranking.py       score and sort best-first
  -> results.html         responsive ranked table with Apply links
```

---

## Adding a new provider

1. Create `providers/yourboard.py` subclassing `JobProvider` (or
   `SeedBackedProvider`) and implement `search(criteria) -> list[Job]`.
2. Set a `name` and a `reliability` (0–1) used by ranking.
3. Register it in `build_default_providers()` in `providers/__init__.py`.

No other module needs to change — normalization, filtering, ranking, and the
UI all work off the shared `Job` model.

---

## Future improvements

- Real per-board integrations for the adapter providers (e.g. a licensed
  LinkedIn/Indeed feed or a hosted scraper actor).
- Add Reed and Jooble as additional free providers for wider coverage.
- Geocode arbitrary job locations (currently distance needs coordinates).
- Persist and cache live results in SQLite to reduce API calls.
- Optional LLM pass to summarise descriptions and flag genuinely
  student-friendly roles.
- Saved searches, email alerts, and pagination.
- Deployment config (Docker / gunicorn) and switch to Postgres.
