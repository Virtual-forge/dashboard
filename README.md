# Agent Approval Dashboard

Admin dashboard for reviewing and resolving approval requests raised by your
Agno agents (`@approval` / `requires_confirmation=True` tools).

- **Backend**: FastAPI + asyncpg, JWT login, queries Postgres directly.
- **Frontend**: React (Vite), polls every 15s, Approve / Block buttons.

## 1. Database

Your Agno agents already write pending requests into a Postgres `approvals`
table (via `PostgresDb(db_url=..., approvals_table="approvals")`). This repo
assumes that table looks like the shape in `backend/migrations.sql`.

**Before doing anything else**, connect to your DB and check the real columns:

```sql
\d approvals
```

If your column names differ (e.g. Agno doesn't have `context` or
`requested_by` by default — those often come from your own tool's arguments
or from a join to the run/session), either:
- adjust the `SELECT`/`UPDATE` queries in `backend/main.py`, or
- populate `context` / `requested_by` yourself when the tool call happens
  (e.g. write them into `tool_args`, or add the columns and set them from
  your agent code before the run pauses).

Then run the migration (safe to run even if the table already exists — it
only adds an `admins` table and patches in missing columns):

```bash
psql "$DATABASE_URL" -f backend/migrations.sql
```

## 1b. Tool descriptions (for readability)

To show each tool's docstring next to its approval requests without touching
Agno's approvals table, there's a separate `tool_descriptions` table (also
created by `migrations.sql`) that the backend `LEFT JOIN`s in at read time,
matched by `tool_name`.

Populate it by editing `backend/sync_tool_descriptions.py` to import your
real tools (or your `Agent` object, since `agent.tools` already carries
Agno's parsed `.description` per tool), then run:

```bash
cd backend
python sync_tool_descriptions.py
```

Re-run it whenever you add, rename, or edit a tool. Nothing about this
touches Agno's own table — it's purely an extra table you own, joined by
`tool_name`.

## 2. Backend

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in DATABASE_URL and a random JWT_SECRET
python create_admin.py you@example.com   # sets your login password
uvicorn main:app --reload --port 8000
```

Endpoints:
- `POST /api/auth/login` → `{ email, password }` → `{ token, email }`
- `GET /api/approvals?status=pending|approved|rejected|all` (auth required)
- `POST /api/approvals/{id}/resolve` → `{ decision: "approved" | "rejected" }`
  (auth required — the logged-in admin's email is stored as `resolved_by`)

## 3. Frontend

```bash
cd frontend
npm install
cp .env.example .env   # points at the backend URL
npm run dev
```

Open http://localhost:5173, log in with the admin you created, and you'll
see pending requests with the tool name, arguments, context, and requester —
Approve or Block updates the row in Postgres and stamps your email + timestamp
on `resolved_by` / `resolved_at`.

## Notes on "who made the request" vs "who resolved it"

Two different people show up per row:
- `requested_by` — whoever/whatever triggered the agent run (populate this
  from your agent code).
- `resolved_by` — the admin who clicked Approve/Block, captured automatically
  from their login session (no separate email prompt needed).

## Production checklist

- Lock down CORS in `backend/main.py` (`allow_origins=["*"]` → your real domain).
- Put the backend behind HTTPS; JWTs are bearer tokens with no revocation list.
- Consider replacing polling with Postgres `LISTEN/NOTIFY` or SSE if you need
  near-instant updates instead of the 15s poll.
