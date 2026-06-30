# Configuration shell for FitPath
import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    MODEL_NAME: str = "gemini-2.5-flash"
    GEMINI_API_KEY: str | None = None
    GOOGLE_API_KEY: str | None = None
    DATABASE_PROVIDER: str = "sqlite"
    DATABASE_URL: str = "sqlite+aiosqlite:///fitpath.db"
    MONGODB_URL: str = "mongodb://localhost:27017/fitpath"
    HOST: str = "0.0.0.0"
    PORT: int = 8001
    LOG_LEVEL: str = "info"
    # Phase 5: mock workflow flag (default True for local/demo; set False for live Gemini)
    MOCK_AGENT_MODE: bool = True
    # Phase 5: explicit frontend origin for CORS (no wildcard)
    FRONTEND_ORIGIN: str = "http://127.0.0.1:5173"

    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()

