from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = ""
    oracle_host: str = "localhost"
    oracle_port: int = 1521
    oracle_service: str = "xepdb1"
    oracle_user: str = "careagent"
    oracle_password: str = ""
    model_mode: str = "demo"
    llm_model: str = "ollama_chat/qwen2.5:7b"
    llm_api_base: str | None = None
    llm_api_key: str | None = None
    cookie_secure: bool = False
    allowed_origin: str = "http://localhost:3000"
    telemetry_enabled: bool = False
    otel_exporter_otlp_endpoint: str = "http://localhost:4318"

    def db_url(self):
        return self.database_url or URL.create(
            "oracle+oracledb",
            username=self.oracle_user,
            password=self.oracle_password,
            host=self.oracle_host,
            port=self.oracle_port,
            query={"service_name": self.oracle_service},
        )

    def provider_kwargs(self):
        api_base = self.llm_api_base
        # LiteLLM expects OpenAI-compatible endpoints under /v1. Accept the
        # common root URL users paste from the OpenAI dashboard as well.
        if self.llm_model.startswith("openai/") and api_base:
            normalized = api_base.rstrip("/")
            if normalized == "https://api.openai.com":
                api_base = normalized + "/v1"
        return {
            key: value
            for key, value in {
                "api_base": api_base,
                "api_key": self.llm_api_key,
            }.items()
            if value
        }


@lru_cache
def settings():
    return Settings()
