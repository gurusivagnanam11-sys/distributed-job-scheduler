from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/jobscheduler"
    JWT_SECRET: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_MINUTES: int = 30
    WORKER_LEASE_DURATION_SECONDS: int = 300
    HEARTBEAT_INTERVAL_SECONDS: int = 10
    REAPER_INTERVAL_SECONDS: int = 60
    RECURRING_SCHEDULER_INTERVAL_SECONDS: int = 60
    GRACEFUL_SHUTDOWN_TIMEOUT_SECONDS: int = 30
    LOG_FORMAT: str = "text"
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    GEMINI_API_KEY: str = ""

settings = Settings()
