import os

import asyncpg


async def get_db_connection():
    return await asyncpg.connect(
        host=os.getenv("POSTGRES_HOST", "db"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        user=os.getenv("POSTGRES_USER", "zakupai"),
        password=os.getenv("POSTGRES_PASSWORD", "zakupai"),
        database=os.getenv("POSTGRES_DB", "zakupai"),
    )


async def get_api_key(user_id: int) -> str:
    try:
        conn = await get_db_connection()
        result = await conn.fetchval(
            "SELECT api_key FROM tg_keys WHERE chat_id = $1", user_id
        )
        await conn.close()
        return result
    except Exception:
        return None


async def save_api_key(user_id: int, api_key: str):
    conn = await get_db_connection()
    await conn.execute(
        "INSERT INTO tg_keys (chat_id, api_key) VALUES ($1, $2) ON CONFLICT (chat_id) DO UPDATE SET api_key = $2",
        user_id,
        api_key,
    )
    await conn.close()


async def init_db():
    conn = await get_db_connection()
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tg_keys (
            chat_id BIGINT PRIMARY KEY,
            api_key TEXT NOT NULL,
            created_at TIMESTAMPTZ DEFAULT now()
        )
    """
    )
    await conn.close()
