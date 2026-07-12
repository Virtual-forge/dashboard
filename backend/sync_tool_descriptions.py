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
# Option A — import the raw functions directly:
#   from my_agents.tools import send_email, delete_file, refund_order
#   TOOLS = [send_email, delete_file, refund_order]
#
# Option B — import your Agent object and read its registered tools
# (Agno stores them as Function objects on `agent.tools`, each already
# carrying a `.name` and a `.description` built from the docstring):
#   from my_agents.agent import my_agent
#   TOOLS = my_agent.tools
#
# You can also mix agents:
#   TOOLS = agent_one.tools + agent_two.tools
# ----------------------------------------------------------------------------
TOOLS = []


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
    if not TOOLS:
        print(
            "TOOLS is empty — edit sync_tool_descriptions.py to import your real tools "
            "before running this script."
        )
        return

    conn = await asyncpg.connect(DATABASE_URL)
    try:
        for tool in TOOLS:
            name, description = extract_name_and_description(tool)
            await conn.execute(
                """
                INSERT INTO tool_descriptions (tool_name, description, updated_at)
                VALUES ($1, $2, now())
                ON CONFLICT (tool_name)
                DO UPDATE SET description = EXCLUDED.description, updated_at = now()
                """,
                name,
                description,
            )
            print(f"synced: {name}")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
