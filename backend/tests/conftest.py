import os
import pytest
import asyncio
import asyncpg
import subprocess

DB_HOST = os.getenv("POSTGRES_HOST", "postgres")
DB_USER = os.getenv("POSTGRES_USER", "postgres")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "postgres")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")

TEST_DB_URL = f"postgresql+asyncpg://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/jobscheduler_test"
os.environ["DATABASE_URL"] = TEST_DB_URL

async def init_db():
    sys_conn = await asyncpg.connect(
        user=DB_USER, password=DB_PASS, host=DB_HOST, port=int(DB_PORT), database="postgres"
    )
    await sys_conn.execute('''
        SELECT pg_terminate_backend(pg_stat_activity.pid)
        FROM pg_stat_activity
        WHERE pg_stat_activity.datname = 'jobscheduler_test'
        AND pid <> pg_backend_pid();
    ''')
    await sys_conn.execute("DROP DATABASE IF EXISTS jobscheduler_test")
    await sys_conn.execute("CREATE DATABASE jobscheduler_test")
    await sys_conn.close()

@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    asyncio.run(init_db())
    subprocess.run(["alembic", "upgrade", "head"], check=True)
