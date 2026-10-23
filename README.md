# Mini Expense Tracker

FastAPI + Supabase Postgres expense tracker with a framework-free HTML/CSS/JS frontend,
served by the same app (one service, one origin).

## API

| Method | Path | Success | Errors |
|---|---|---|---|
| POST | `/expenses` | `201` expense | `400 {"error"}` |
| GET | `/expenses?category&from&to&page&limit` | `200 {items, total_count, total_amount}` | `400` |
| DELETE | `/expenses/{id}` | `204` | `404 {"error": "Expense not found"}` |
| GET | `/expenses/summary?month=YYYY-MM` | `200 {month, totals, total}` | `400` |
| GET | `/health` | `200 {"status": "ok"}` | |

Interactive docs: `/docs`. All errors use `{"error": "message"}`.

## Configuration

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Supabase **session pooler** connection string (secret) |
| `APP_TIMEZONE` | Timezone for "today" (default `Asia/Kolkata`) |

Copy `.env.example` to `.env` locally. `.env` is gitignored; on Render, set
`DATABASE_URL` in the dashboard.

## Database

Schema: `migrations/001_create_expenses.sql` (applied to Supabase `public`).
CHECK constraints mirror the API rules; RLS is enabled with no policies so the
Supabase Data API cannot access the table (the backend connects as the owner).

## Run locally

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt
.venv/Scripts/python -m uvicorn app.main:app --reload
```

## Tests

```bash
.venv/Scripts/python -m pytest -q
```

Tests run against an isolated `test` schema in the same Supabase project
(created from the same migration file); `public.expenses` is never touched.

Client-side validation (mirrors the backend rules) is tested with Node's built-in runner:

```bash
node --test "tests/js/*.test.mjs"
```

## Deploy (Render)

`render.yaml` is a Blueprint: Render Dashboard → New → Blueprint → select this
repo → enter `DATABASE_URL` → Apply. Pushes to `main` redeploy automatically.
