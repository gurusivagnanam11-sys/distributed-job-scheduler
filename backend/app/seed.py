import asyncio
import secrets
from datetime import datetime, timezone, timedelta
from passlib.hash import pbkdf2_sha256
from app.core.database import async_session_factory
from app.core.security import hash_password
from app.models.organization import Organization
from app.models.user import User
from app.models.project import Project, ApiKey
from app.models.queue import Queue
from app.models.retry_policy import RetryPolicy
from app.models.job import Job
from app.models.job_execution import JobExecution
from app.models.recurring_job_template import RecurringJobTemplate
from sqlalchemy import select, delete

import asyncpg
import subprocess
from app.core.config import settings

async def ensure_db():
    db_url = settings.DATABASE_URL
    # parse db_url
    # format: postgresql+asyncpg://user:pass@host:port/dbname
    clean_url = db_url.replace("postgresql+asyncpg://", "")
    auth_host, db_name = clean_url.split("/")
    if "@" in auth_host:
        auth, host_port = auth_host.split("@")
        user, password = auth.split(":")
    else:
        user = "postgres"
        password = "postgres"
        host_port = auth_host
    
    if ":" in host_port:
        host, port = host_port.split(":")
    else:
        host = host_port
        port = "5432"

    try:
        sys_conn = await asyncpg.connect(user=user, password=password, host=host, port=int(port), database="postgres")
        res = await sys_conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", db_name)
        if not res:
            print(f"Database {db_name} does not exist. Creating database...")
            await sys_conn.execute(f'CREATE DATABASE "{db_name}"')
        await sys_conn.close()
    except Exception as e:
        print(f"Database check/creation notice: {e}")

    try:
        subprocess.run(["alembic", "upgrade", "head"], check=True)
    except Exception as e:
        print(f"Alembic migration notice: {e}")

async def seed():
    await ensure_db()
    print("=== SEEDING EXPANDED DEMO DATABASE ===")
    async with async_session_factory() as session:
        # Clean up any existing demo user or org
        existing_org = await session.execute(select(Organization).where(Organization.name == "Acme Corp Demo"))
        org_obj = existing_org.scalar_one_or_none()
        if org_obj:
            await session.execute(delete(JobExecution))
            await session.delete(org_obj)
            await session.flush()

        now = datetime.now(timezone.utc)

        # 1. Organization & User
        org = Organization(name="Acme Corp Demo", created_at=now, updated_at=now)
        session.add(org)
        await session.flush()

        user = User(
            organization_id=org.id,
            email="demo@example.com",
            password_hash=hash_password("Password123!"),
            is_active=True,
            created_at=now,
            updated_at=now
        )
        session.add(user)
        await session.flush()

        # 2. Projects
        proj_main = Project(
            organization_id=org.id,
            name="Production Services",
            description="Main production pipeline, email queues, and billing workloads",
            created_at=now,
            updated_at=now
        )
        proj_data = Project(
            organization_id=org.id,
            name="Analytics & Data Pipeline",
            description="ETL pipelines, nightly syncs, and data export queues",
            created_at=now,
            updated_at=now
        )
        session.add_all([proj_main, proj_data])
        await session.flush()

        # 3. API Keys
        for label in ["Backend Web Server Key", "CLI Deployment Key", "Staging Integration Key"]:
            raw_key = f"jsk_{secrets.token_hex(32)}"
            session.add(ApiKey(
                project_id=proj_main.id,
                label=label,
                key_hash=pbkdf2_sha256.hash(raw_key),
                key_prefix=raw_key[:12],
                created_at=now,
                updated_at=now
            ))

        # 4. Queues under Production Services
        q_email = Queue(
            project_id=proj_main.id,
            name="email-notifications",
            concurrency_limit=5,
            status="active",
            created_at=now,
            updated_at=now
        )
        q_billing = Queue(
            project_id=proj_main.id,
            name="billing-invoices",
            concurrency_limit=2,
            status="active",
            created_at=now,
            updated_at=now
        )
        q_media = Queue(
            project_id=proj_main.id,
            name="media-processing",
            concurrency_limit=8,
            status="active",
            created_at=now,
            updated_at=now
        )
        session.add_all([q_email, q_billing, q_media])
        await session.flush()

        # 5. Retry Policies
        session.add(RetryPolicy(
            queue_id=q_email.id,
            max_retries=3,
            backoff_strategy="exponential",
            backoff_base_seconds=2.0,
            backoff_max_seconds=60.0,
            created_at=now,
            updated_at=now
        ))
        session.add(RetryPolicy(
            queue_id=q_billing.id,
            max_retries=5,
            backoff_strategy="exponential",
            backoff_base_seconds=5.0,
            backoff_max_seconds=300.0,
            created_at=now,
            updated_at=now
        ))

        # 6. Populate 30+ Jobs across queues
        jobs_to_create = []

        # --- Email Queue Jobs ---
        for i in range(1, 11):
            jobs_to_create.append(Job(
                queue_id=q_email.id,
                status="completed",
                priority=i % 3,
                payload={"to": f"user_{i}@acme.com", "template": "welcome_email", "user_id": 1000 + i},
                attempt_count=1,
                scheduled_at=now - timedelta(minutes=i * 15),
                created_at=now - timedelta(minutes=i * 15),
                updated_at=now - timedelta(minutes=i * 15 - 1)
            ))

        for i in range(1, 6):
            jobs_to_create.append(Job(
                queue_id=q_email.id,
                status="queued",
                priority=i,
                payload={"to": f"customer_{i}@domain.org", "subject": f"Weekly Digest #{i}"},
                attempt_count=0,
                scheduled_at=now,
                created_at=now,
                updated_at=now
            ))

        for i in range(1, 4):
            jobs_to_create.append(Job(
                queue_id=q_email.id,
                status="scheduled",
                priority=1,
                payload={"to": f"vip_{i}@enterprise.io", "subject": "Quarterly Promo"},
                attempt_count=0,
                scheduled_at=now + timedelta(hours=i),
                created_at=now,
                updated_at=now
            ))

        # --- Billing Queue Jobs ---
        for i in range(1, 6):
            jobs_to_create.append(Job(
                queue_id=q_billing.id,
                status="completed",
                priority=5,
                payload={"invoice_id": f"INV-2026-00{i}", "amount_usd": 149.99 * i, "customer_id": f"CUST-{i}"},
                attempt_count=1,
                scheduled_at=now - timedelta(hours=i),
                created_at=now - timedelta(hours=i),
                updated_at=now - timedelta(hours=i - 0.1)
            ))

        for i in range(1, 4):
            jobs_to_create.append(Job(
                queue_id=q_billing.id,
                status="queued",
                priority=10,
                payload={"subscription_id": f"SUB-88{i}", "action": "charge_monthly"},
                attempt_count=0,
                scheduled_at=now,
                created_at=now,
                updated_at=now
            ))

        # --- Dead-Letter Jobs with Failures for AI Summaries ---
        dl_job_1 = Job(
            queue_id=q_email.id,
            status="dead_letter",
            priority=5,
            payload={"to": "invalid_email_format@@domain..com", "template": "password_reset"},
            attempt_count=3,
            scheduled_at=now - timedelta(hours=3),
            created_at=now - timedelta(hours=3),
            updated_at=now - timedelta(hours=2)
        )
        dl_job_2 = Job(
            queue_id=q_billing.id,
            status="dead_letter",
            priority=9,
            payload={"invoice_id": "INV-ERR-99", "gateway": "stripe_v2", "card_token": "tok_invalid"},
            attempt_count=3,
            scheduled_at=now - timedelta(hours=4),
            created_at=now - timedelta(hours=4),
            updated_at=now - timedelta(hours=3)
        )
        session.add_all([dl_job_1, dl_job_2])
        await session.flush()

        # Add failed execution logs for dl_job_1
        for attempt in range(1, 4):
            session.add(JobExecution(
                job_id=dl_job_1.id,
                attempt_number=attempt,
                status="failed",
                error=f"Attempt {attempt}: EmailValidationError('Invalid recipient address format: invalid_email_format@@domain..com')",
                started_at=now - timedelta(minutes=180 - (attempt * 5)),
                finished_at=now - timedelta(minutes=179 - (attempt * 5)),
                created_at=now - timedelta(minutes=180 - (attempt * 5)),
                updated_at=now - timedelta(minutes=179 - (attempt * 5))
            ))

        # Add failed execution logs for dl_job_2
        for attempt in range(1, 4):
            session.add(JobExecution(
                job_id=dl_job_2.id,
                attempt_number=attempt,
                status="failed",
                error=f"Attempt {attempt}: PaymentGatewayError('Stripe API error: Card declined - insufficient_funds (code 402)')",
                started_at=now - timedelta(minutes=240 - (attempt * 5)),
                finished_at=now - timedelta(minutes=239 - (attempt * 5)),
                created_at=now - timedelta(minutes=240 - (attempt * 5)),
                updated_at=now - timedelta(minutes=239 - (attempt * 5))
            ))

        session.add_all(jobs_to_create)

        # 7. Recurring Job Templates
        session.add_all([
            RecurringJobTemplate(
                queue_id=q_email.id,
                cron_expression="*/5 * * * *",
                job_payload={"task": "flush_email_queue"},
                is_active=True,
                next_run_at=now + timedelta(minutes=5),
                created_at=now,
                updated_at=now
            ),
            RecurringJobTemplate(
                queue_id=q_billing.id,
                cron_expression="0 0 * * *",
                job_payload={"task": "generate_daily_financial_report"},
                is_active=True,
                next_run_at=now + timedelta(hours=12),
                created_at=now,
                updated_at=now
            ),
            RecurringJobTemplate(
                queue_id=q_media.id,
                cron_expression="0 */2 * * *",
                job_payload={"task": "optimize_stored_images"},
                is_active=False,
                next_run_at=now + timedelta(hours=2),
                created_at=now,
                updated_at=now
            )
        ])

        await session.commit()
        print("=== EXPANDED DATABASE SEEDED SUCCESSFULLY WITH 30+ JOBS ===")

if __name__ == "__main__":
    asyncio.run(seed())
