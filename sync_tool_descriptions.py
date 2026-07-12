"""
Sync tool docstrings into the `tool_descriptions` table.

This table is separate from Agno's own `ai.agno_approvals` table — we never
modify that one, per Agno's guidance. Run this whenever you add, remove, or
rename a tool, so the dashboard can show a human-readable description next
to each approval request.

    python sync_tool_descriptions.py

Edit the TOOLS list below to point at your actual agent/tool definitions.
"""
import asyncio
import inspect

import asyncpg

from database import DATABASE_URL

# --- EDIT THIS: point at the tools your agents actually use ---------------
#
# Option A — hardcode name -> description pairs, no imports needed.
# Safest if importing your agent module has side effects (e.g. it connects
# to the DB or starts running on import). Just copy each tool's docstring
# in by hand:
#   TOOLS_MANUAL = {
#       "send_email": "Sends an email to the given address with subject and body.",
#       "delete_file": "Permanently deletes a file from the workspace.",
#   }
#
# Option B — import the raw functions directly (only if your tools live in
# a module with NO side effects at import time — no agent creation, no
# server startup, no DB connections outside of what asyncpg here does):
#   from my_agents.tools import send_email, delete_file, refund_order
#   TOOLS = [send_email, delete_file, refund_order]
#
# Option C — import your Agent object and read its registered tools
# (Agno stores them as Function objects on `agent.tools`, each already
# carrying a `.name` and a `.description` built from the docstring).
# Only safe if creating the Agent object itself has no side effects:
#   from my_agents.agent import my_agent
#   TOOLS = my_agent.tools
# ----------------------------------------------------------------------------
TOOLS = []
TOOLS_MANUAL: dict[str, str] = {}


def extract_name_and_description(tool) -> tuple[str, str]:
    """Works for plain functions, @tool-decorated functions, and Agno
    Function/Toolkit-wrapped objects."""
    name = getattr(tool, "name", None) or getattr(tool, "__name__", None)
    description = getattr(tool, "description", None)

    if not description:
        doc = inspect.getdoc(tool) or getattr(tool, "__doc__", None)
        description = (doc or "").strip()

    if not name:
        raise ValueError(f"Could not determine a name for tool: {tool!r}")

    return name, description or "(no description available)"


async def main() -> None:
    if not TOOLS and not TOOLS_MANUAL:
        print(
            "TOOLS and TOOLS_MANUAL are both empty — edit sync_tool_descriptions.py "
            "before running this script."
        )
        return

    conn = await asyncpg.connect(DATABASE_URL)
    try:
        for tool in TOOLS:
            name, description = extract_name_and_description(tool)
            await upsert(conn, name, description)

        for name, description in TOOLS_MANUAL.items():
            await upsert(conn, name, description)
    finally:
        await conn.close()


async def upsert(conn, name: str, description: str) -> None:
    await conn.execute(
        """
        INSERT INTO ai.tool_descriptions (tool_name, description, updated_at)
        VALUES ($1, $2, now())
        ON CONFLICT (tool_name)
        DO UPDATE SET description = EXCLUDED.description, updated_at = now()
        """,
        name,
        description,
    )
    print(f"synced: {name}")


if __name__ == "__main__":
    asyncio.run(main())
