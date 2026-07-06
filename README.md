# Alumni Intelligence Agent

A local web application that enriches an alumni/contact roster spreadsheet
(LinkedIn, public email, graduation year, country of origin, current
location, current employer) by searching the public web (Tavily),
reasoning over the evidence with an LLM (Anthropic's Claude), and
finding/verifying a replacement email with Hunter.io when the known one is
missing or stale.

Every write is confidence-scored: high-confidence results are applied
automatically, everything else lands in a manual review queue so a human
signs off before anything questionable reaches the final spreadsheet.

## Features

- **Multi-query web research** per person, merged/ranked, with a SQLite
  cache so repeat runs never re-spend a search credit on an identical query.
- **LLM reasoning** over the gathered evidence, constrained to a strict
  JSON schema (no free-text parsing), with its own response cache.
- **Confidence-tiered writes**: 95+ auto-writes, a configurable threshold
  (default 80) writes as medium-confidence, anything below goes to the
  review queue. A field that's already filled is never downgraded by a
  low-confidence guess.
- **Email finder/verifier (Hunter.io)**, consulted only when the known
  email is missing or at your institution's stale/alumni domain -- an
  email Hunter can't confirm is deliverable is dropped rather than written.
- **Concurrent, crash-resumable processing**: each row is checkpointed to
  the database the moment it's picked up and the moment it finishes, so
  restarting a run after a crash just resumes where it left off.
- **Live dashboard** (progress, worker status, ETA, API request counts),
  **manual review queue** (approve/reject/edit/skip), and a **Reports**
  page with a one-click completed-spreadsheet download.
- Works for any institution -- the institution name and "stale" email
  domain are configurable, not hardcoded.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Then fill in `.env`:

- `CLAUDE_API_KEY` -- an Anthropic API key ([console.anthropic.com](https://console.anthropic.com))
- `TAVILY_API_KEY` -- a Tavily Search API key ([tavily.com](https://tavily.com))
- `HUNTER_API_KEY` -- a Hunter.io API key ([hunter.io](https://hunter.io)), optional but required for email finding/verification
- `INSTITUTION_NAME` -- e.g. `"Example University"`, shown to the LLM for identity verification and used in search queries
- `STALE_EMAIL_DOMAIN` -- e.g. `example.edu`; addresses at this domain are treated as stale (alongside a missing email) and become eligible for replacement. Leave blank to only replace missing emails.

All of the above (except the API keys, which are masked) can also be changed later from the in-app Settings page without editing `.env` by hand.

## Run

```bash
uvicorn app.main:app --reload
```

Then open http://127.0.0.1:8000

## Tests

```bash
pytest
```

## Workflow

1. **Upload** a `.xlsx` roster on the Upload page. Column headers are
   matched against a set of common aliases (e.g. "Grad Year" -> Graduation
   Year); anything unrecognized is preserved verbatim and re-appended to
   the export.
2. Go to **Processing** for that upload and click Start Processing --
   rows are enriched concurrently (default 5 workers), with each row's
   result checkpointed to the database immediately. If the app crashes or
   is restarted, clicking Start Processing again resumes exactly where it
   left off (completed rows are never reprocessed).
3. Rows below the confidence threshold land in the global **Review
   Queue**, where you can approve, reject, manually edit, or skip each one.
4. **Reports** shows per-upload stats (rows processed/skipped/reviewed,
   missing email/LinkedIn counts, average confidence, API usage, elapsed
   time) and a button to download the completed spreadsheet.
5. **Settings** lets you change the Claude/Tavily/Hunter.io API keys,
   institution identity, worker count, confidence threshold, retry count,
   cache expiration, and output directory without editing `.env` by hand.

## Project layout

```
app/
  api/         # FastAPI routers (thin, delegate to services)
  services/    # business logic (search, LLM reasoning, email finding, validation, enrichment)
  models/      # SQLAlchemy models
  database/    # DB session/engine setup
  workers/     # async worker pool / processing queue
  templates/   # Jinja2 + Bootstrap 5 + HTMX templates
  static/      # CSS/JS assets
config/        # Settings (env-driven)
cache/         # SQLite cache + checkpoint DB
logs/          # daily log files
uploads/       # uploaded spreadsheets
output/        # completed spreadsheets
tests/         # pytest suite
```
