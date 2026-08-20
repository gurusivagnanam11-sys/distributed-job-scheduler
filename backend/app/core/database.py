from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool
from app.core.config import settings

# If testing, use NullPool to avoid cross-test connection pollution in asyncpg
pool_kwargs = {"poolclass": NullPool} if "_test" in settings.DATABASE_URL else {}
engine = create_async_engine(settings.DATABASE_URL, echo=False, future=True, **pool_kwargs)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_db():
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
