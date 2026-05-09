import asyncio
import os
from dataclasses import dataclass
from typing import Optional

import asyncpg
import psycopg2
from dotenv import load_dotenv


@dataclass
class DatabaseConfig:
    host: str
    port: int
    name: str
    user: str
    password: str

    @classmethod
    def from_env(cls) -> "DatabaseConfig":
        load_dotenv()
        return cls(
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", "5432")),
            name=os.getenv("DB_NAME", "smartspend_db"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", ""),
        )

    @property
    def dsn(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"


_async_pool: Optional[asyncpg.Pool] = None


def get_db_connection() -> psycopg2.extensions.connection:
    config = DatabaseConfig.from_env()
    return psycopg2.connect(
        host=config.host,
        port=config.port,
        dbname=config.name,
        user=config.user,
        password=config.password,
    )


async def get_async_pool() -> asyncpg.Pool:
    global _async_pool
    if _async_pool is None:
        config = DatabaseConfig.from_env()
        _async_pool = await asyncpg.create_pool(
            host=config.host,
            port=config.port,
            database=config.name,
            user=config.user,
            password=config.password,
            min_size=1,
            max_size=10,
        )
    return _async_pool


def test_connection() -> None:
    print("🔍 Testing PostgreSQL connection...")
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT version();")
            version = cur.fetchone()[0]
            print(f"✅ Connected: {version}")

            table_names = ["users", "transactions", "alerts", "monthly_summary", "spending_patterns"]
            print("\n📊 Current table row counts:")
            for table_name in table_names:
                cur.execute(f"SELECT COUNT(*) FROM {table_name};")
                count = cur.fetchone()[0]
                print(f"  - {table_name:<18} {count}")
    finally:
        conn.close()


async def _test_async_pool() -> None:
    pool = await get_async_pool()
    async with pool.acquire() as conn:
        db_name = await conn.fetchval("SELECT current_database();")
        print(f"✅ Async pool connected to database: {db_name}")


if __name__ == "__main__":
    test_connection()
    asyncio.run(_test_async_pool())
