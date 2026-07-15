-- Migration: Jira sync tracking, WITHOUT touching ai.agno_approvals' schema.
-- Built against the REAL column list (from inspect_table.py output):
--   id, run_id, session_id, status, source_type, approval_type, pause_type,
--   tool_name, tool_args, expires_at, agent_id, team_id, workflow_id,
--   user_id, schedule_id, schedule_run_id, source_name, requirements,
--   context, resolution_data, resolved_by, resolved_at, created_at,
--   updated_at, run_status
-- Note: id is `character varying`, NOT uuid. context/requirements/
-- resolution_data are jsonb. resolved_at/created_at/updated_at/expires_at
-- are epoch bigints.

BEGIN;

-- Correlation table: one row per approval we've synced (or attempted to
-- sync) to Jira. approval_id is a logical FK to ai.agno_approvals.id --
-- deliberately no FOREIGN KEY constraint (that would hard-depend on a
-- table we don't manage), and TEXT to match id's real varchar type.
CREATE TABLE IF NOT EXISTS jira_sync (
    approval_id TEXT PRIMARY KEY,
    jira_issue_key TEXT,               -- NULL until the Jira API call succeeds
    claimed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    synced_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_jira_sync_unsynced
    ON jira_sync (approval_id) WHERE jira_issue_key IS NULL;

-- Trigger lives ON ai.agno_approvals (NOTIFY has to fire from the table
-- that changes), but only reads NEW.*, it does not add/touch any column.
CREATE OR REPLACE FUNCTION notify_new_approval() RETURNS trigger AS $$
BEGIN
    PERFORM pg_notify('new_approval', NEW.id);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_notify_new_approval ON ai.agno_approvals;
CREATE TRIGGER trg_notify_new_approval
    AFTER INSERT ON ai.agno_approvals
    FOR EACH ROW
    WHEN (NEW.status = 'pending' OR NEW.approval_type = 'audit')
    EXECUTE FUNCTION notify_new_approval();

COMMIT;

-- CAVEAT: since Agno owns ai.agno_approvals, a future Agno upgrade that
-- recreates this table could silently drop the trigger. The listener's
-- reconciliation poll (approval_listener.py) covers that gap. Re-check
-- after any Agno version bump with:
--   SELECT tgname FROM pg_trigger WHERE tgrelid = 'ai.agno_approvals'::regclass;
