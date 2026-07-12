-- Run this once against your Postgres database:
--   psql "$DATABASE_URL" -f migrations.sql

CREATE EXTENSION IF NOT EXISTS pgcrypto;  -- for gen_random_uuid()

-- Admins who can log into the dashboard and approve/block requests.
CREATE TABLE IF NOT EXISTS admins (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Approval requests raised by your Agno agents (@approval / requires_confirmation tools).
-- If Agno already created this table for you (e.g. via
--   PostgresDb(db_url=..., approvals_table="approvals")
-- ), the CREATE TABLE below is a no-op, and the ALTER TABLE statements just
-- patch in the couple of columns this dashboard needs (context, requested_by)
-- in case Agno's default schema doesn't already have them. Check your real
-- columns first with:  \d approvals   in psql, and adjust backend/database.py
-- if your column names differ from what's below.
CREATE TABLE IF NOT EXISTS approvals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id TEXT,
    agent_id TEXT,
    tool_name TEXT NOT NULL,
    tool_args JSONB NOT NULL DEFAULT '{}'::jsonb,
    context TEXT,              -- description / reasoning for the request
    requested_by TEXT,         -- who/what triggered the agent run
    status TEXT NOT NULL DEFAULT 'pending',   -- pending | approved | rejected
    resolved_by TEXT,          -- admin email who resolved it
    resolved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE approvals ADD COLUMN IF NOT EXISTS context TEXT;
ALTER TABLE approvals ADD COLUMN IF NOT EXISTS requested_by TEXT;

CREATE INDEX IF NOT EXISTS idx_approvals_status ON approvals (status);
CREATE INDEX IF NOT EXISTS idx_approvals_created_at ON approvals (created_at DESC);

-- Human-readable tool descriptions, kept in a table WE own (public schema),
-- completely separate from Agno's `ai.agno_approvals`. The backend LEFT
-- JOINs this onto ai.agno_approvals by tool_name at read time — Agno's
-- table is never touched. Populate it by running
--   python sync_tool_descriptions.py
-- any time you add/rename a tool, or upsert rows by hand.
CREATE TABLE IF NOT EXISTS tool_descriptions (
    tool_name TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
