"""
Background worker that watches ai.agno_approvals for new pending rows and
creates a matching Jira issue for each -- without altering Agno's table.
Correlation state lives in `jira_sync`, a table we own (same pattern as
your `tool_descriptions` table), keyed by the real `id` type (varchar).

Two mechanisms feed the same sync path:
  1. LISTEN/NOTIFY -- near-instant reaction when Agno OS inserts a row.
  2. A periodic reconciliation poll -- catches anything NOTIFY missed.

Run as a long-lived asyncio task inside your FastAPI app's lifespan.
"""

import asyncio
import json
import logging

import asyncpg

from jira_client import create_approval_issue

logger = logging.getLogger("jira_approval_listener")

RECONCILE_INTERVAL_SECONDS = 30

# Confirmed: public schema, matches backend/main.py's unqualified LEFT JOIN.
TOOL_DESCRIPTIONS_TABLE = "tool_descriptions"


async def _claim_pending_ids(conn: asyncpg.Connection) -> list[str]:
    """Find pending approvals with no jira_sync row yet, and atomically
    claim them via INSERT ... ON CONFLICT DO NOTHING. That INSERT is the
    atomic step -- safe to run more than one worker instance without
    double-creating issues, no need to lock ai.agno_approvals itself."""
    candidates = await conn.fetch(
        """
        SELECT a.id
        FROM ai.agno_approvals a
        LEFT JOIN jira_sync js ON js.approval_id = a.id
        WHERE js.approval_id IS NULL
          AND (a.status = 'pending' OR a.approval_type = 'audit')
        """
    )
    claimed_ids: list[str] = []
    for row in candidates:
        claimed = await conn.fetchrow(
            """
            INSERT INTO jira_sync (approval_id)
            VALUES ($1)
            ON CONFLICT (approval_id) DO NOTHING
            RETURNING approval_id
            """,
            row["id"],
        )
        if claimed:
            claimed_ids.append(row["id"])

    # Retry anything claimed earlier but not yet synced (previous Jira
    # API call failed, jira_issue_key still NULL).
    retry_rows = await conn.fetch(
        "SELECT approval_id FROM jira_sync WHERE jira_issue_key IS NULL"
    )
    for row in retry_rows:
        if row["approval_id"] not in claimed_ids:
            claimed_ids.append(row["approval_id"])

    return claimed_ids


def _parse_jsonb(value):
    if isinstance(value, str):
        return json.loads(value) if value else None
    return value


async def _fetch_approval_row(conn: asyncpg.Connection, approval_id: str) -> dict | None:
    query = f"""
        SELECT a.id, a.run_id, a.session_id, a.status, a.source_type,
               a.source_name, a.approval_type, a.pause_type, a.tool_name,
               a.tool_args, a.agent_id, a.team_id, a.workflow_id, a.user_id,
               a.requirements, a.context, a.expires_at,
               td.description AS tool_description
        FROM ai.agno_approvals a
        LEFT JOIN {TOOL_DESCRIPTIONS_TABLE} td ON td.tool_name = a.tool_name
        WHERE a.id = $1
    """
    row = await conn.fetchrow(query, approval_id)
    if row is None:
        return None
    data = dict(row)
    for jsonb_col in ("tool_args", "requirements", "context"):
        data[jsonb_col] = _parse_jsonb(data.get(jsonb_col))
    return data


async def _sync_one(pool: asyncpg.Pool, approval_id: str) -> None:
    async with pool.acquire() as conn:
        row = await _fetch_approval_row(conn, approval_id)

    if row is None:
        logger.warning("Approval %s claimed but not found (deleted?)", approval_id)
        return

    is_audit = row.get("approval_type") == "audit"

    if not is_audit and row["status"] != "pending":
        # Resolved between claim and now (required-type only -- audit-type
        # rows are already resolved by design, see below).
        return

    try:
        # create_approval_issue() now sends the "Approval Type" select
        # field (Audit / Required) on the issue itself. A Jira Automation
        # rule reads that field and auto-transitions Audit issues to
        # Approved -- no guessing at transition IDs from Python anymore.
        issue_key = await create_approval_issue(row)
    except Exception:
        logger.exception("Failed to create Jira issue for approval %s", approval_id)
        return  # jira_issue_key stays NULL -> retried on next reconcile pass

    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE jira_sync
            SET jira_issue_key = $1, synced_at = now()
            WHERE approval_id = $2
            """,
            issue_key,
            approval_id,
        )
    logger.info("Synced approval %s -> Jira issue %s%s", approval_id, issue_key, " (audit)" if is_audit else "")


async def _claim_and_sync_pending(pool: asyncpg.Pool) -> None:
    async with pool.acquire() as conn:
        claimed_ids = await _claim_pending_ids(conn)
    for approval_id in claimed_ids:
        await _sync_one(pool, approval_id)


async def _reconcile_loop(pool: asyncpg.Pool) -> None:
    while True:
        try:
            await _claim_and_sync_pending(pool)
        except Exception:
            logger.exception("Reconciliation pass failed")
        await asyncio.sleep(RECONCILE_INTERVAL_SECONDS)


async def run_approval_listener(dsn: str) -> None:
    """Entry point. Call as an asyncio task at app startup:
        asyncio.create_task(run_approval_listener(DATABASE_URL))
    """
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=2)

    await _claim_and_sync_pending(pool)  # startup catch-up

    reconcile_task = asyncio.create_task(_reconcile_loop(pool))

    listen_conn: asyncpg.Connection = await pool.acquire()

    async def _on_notify(conn, pid, channel, payload):
        await _claim_and_sync_pending(pool)

    await listen_conn.add_listener("new_approval", _on_notify)
    logger.info("Listening on channel 'new_approval'...")

    try:
        await asyncio.Event().wait()
    finally:
        await listen_conn.remove_listener("new_approval", _on_notify)
        await pool.release(listen_conn)
        reconcile_task.cancel()
        await pool.close()
