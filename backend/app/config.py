# Configuration shell for FitPath
import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    MODEL_NAME: str = "gemini-2.5-flash"
    GEMINI_API_KEY: str | None = None
    DATABASE_PROVIDER: str = "sqlite"
    DATABASE_URL: str = "sqlite+aiosqlite:///fitpath.db"
    MONGODB_URL: str = "mongodb://localhost:27017/fitpath"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    LOG_LEVEL: str = "info"

    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()
