"""
Create an admin login for the dashboard.

Usage:
    python create_admin.py admin@example.com
    (will prompt for a password)
"""
import asyncio
import getpass
import sys

import asyncpg

from helpers.auth import hash_password
from database.database import DATABASE_URL


async def main(email: str, password: str) -> None:
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        await conn.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS admins (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        await conn.execute(
            """
            INSERT INTO admins (email, password_hash)
            VALUES ($1, $2)
            ON CONFLICT (email) DO UPDATE SET password_hash = EXCLUDED.password_hash
            """,
            email,
            hash_password(password),
        )
        print(f"Admin '{email}' created/updated.")
    finally:
        await conn.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python create_admin.py <email>")
        sys.exit(1)
    email_arg = sys.argv[1]
    password_arg = getpass.getpass("Password: ")
    asyncio.run(main(email_arg, password_arg))
