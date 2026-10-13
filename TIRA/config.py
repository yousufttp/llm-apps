import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    db_path: str = os.getenv("TIRA_DB_PATH", "tira.db")
    log_level: str = os.getenv("TIRA_LOG_LEVEL", "INFO")
    langsmith_project: str = os.getenv("LANGSMITH_PROJECT", "tira-local")


settings = Settings()
