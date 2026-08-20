import os
import pytest
import asyncio
import asyncpg
import subprocess

TEST_DB_URL = "postgresql+asyncpg://postgres:postgres@postgres:5432/jobscheduler_test"
os.environ["DATABASE_URL"] = TEST_DB_URL

async def init_db():
    sys_conn = await asyncpg.connect(
        user="postgres", password="postgres", host="postgres", port=5432, database="postgres"
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
