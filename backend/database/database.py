import os

import asyncpg

DATABASE_URL = os.environ["DATABASE_URL"]

pool: asyncpg.Pool | None = None


async def init_pool() -> None:
    global pool
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10)


async def close_pool() -> None:
    global pool
    if pool is not None:
        await pool.close()
        pool = None


def get_pool() -> asyncpg.Pool:
    if pool is None:
        raise RuntimeError("DB pool not initialized — did startup run?")
    return pool
