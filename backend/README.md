# Agno approvals -> Jira sync — how to actually run this

## Short answer
You keep running the same things you already run: **dashboard backend**,
**agents backend**, and (for now, optionally) **dashboard frontend**. There
is no new process to start. The Jira listener lives *inside* your existing
dashboard backend as a background task, and the webhook is just a new
route on the same FastAPI app you already have running.

## What changes for each of your 3 usual processes

**Dashboard backend** (`uvicorn main:app` in `backend/`)
→ This is the one that changes. Copy `jira_client.py`,
`approval_listener.py`, and `jira_webhook.py` into `backend/` (flat,
alongside `main.py`, `database.py`, etc. — not a subfolder). Then apply
the 4 small edits in `main_patch_instructions.md`. When you run it the
way you already do, the Jira listener starts automatically as a
background `asyncio` task the moment the app boots, and the
`/webhooks/jira-approval` route is live alongside your existing
`/api/approvals` routes.

**Agents backend** (wherever Agno OS runs)
→ Completely unchanged. It has no idea Jira exists. It keeps inserting
rows into `ai.agno_approvals` exactly as before.

**Dashboard frontend** (`npm run dev` in `frontend/`)
→ Also unchanged, and you can keep it running as a fallback UI (it still
reads/writes the same table, so approving from either the dashboard or
Jira works — first one to resolve a row wins, the other just gets a "no
rows updated" no-op, which `jira_webhook.py` and your existing
`resolve_approval` endpoint both already handle gracefully via `WHERE
status = 'pending'`). Once you trust the Jira flow, you can stop running
it, or keep it around for a while as a safety net.

## One-time setup (not something you "run" repeatedly)
1. `psql "$DATABASE_URL" -f sql/001_jira_listener_setup.sql` — creates
   `jira_sync` + the trigger. Run once against your DB.
2. Create the Jira project, custom fields, and Automation rule (see
   earlier setup steps / `jira_webhook.py` docstring).
3. Add the `JIRA_*` env vars to your dashboard backend's `.env`.

## Day to day
```
# same as always:
cd backend && uvicorn main:app --reload         # dashboard backend (now includes Jira sync)
cd agents && <however you start Agno OS today>  # agents backend, unchanged
cd frontend && npm run dev                       # optional now
```

## Sanity check it's working
- Tail the dashboard backend's logs — you should see `Listening on
  channel 'new_approval'...` at startup, and `Synced approval <id> ->
  Jira issue <key>` whenever an agent tool pauses for approval.
- Trigger one approval from your agent, confirm a Jira issue appears.
- Approve it in Jira, confirm your agent run resumes (this is the part
  worth watching closely the first time, per the `resolved_at`/
  `updated_at` caveat below).

## Files in this bundle
- `sql/001_jira_listener_setup.sql` — one-time DB migration
- `backend/jira_client.py` — Jira REST API calls
- `backend/approval_listener.py` — the background sync task
- `backend/jira_webhook.py` — the Jira → Postgres callback route
- `backend/main_patch_instructions.md` — exact diff for your `main.py`

## Remaining open question
`resolved_at` and `updated_at` are both epoch bigints on
`ai.agno_approvals`. The webhook sets both defensively, but I don't have
visibility into which one Agno OS's resume logic actually reads. If the
agent doesn't resume after a Jira approval, that mismatch is the first
thing to check.
