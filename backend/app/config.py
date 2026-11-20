from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent  # backend/


class Settings(BaseSettings):
    """全部配置来自环境变量 / backend/.env，切换模型供应商只改环境变量。"""

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "JobCopilot"
    app_env: str = "development"
    secret_key: str = "dev-secret-change-me"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24

    database_url: str = f"sqlite:///{(BASE_DIR / 'jobcopilot.db').as_posix()}"

    # 对话模型（OpenAI 兼容协议）
    chat_base_url: str = "https://api.deepseek.com/v1"
    chat_api_key: str = ""
    chat_model: str = "deepseek-chat"
    chat_temperature: float = 0.3

    # Embedding（OpenAI 兼容协议）
    embedding_base_url: str = ""
    embedding_api_key: str = ""
    embedding_model: str = "text-embedding-v4"
    embedding_dimensions: int = 1024

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5180,http://127.0.0.1:5180"
    upload_dir: str = str(BASE_DIR / "uploads")

    @model_validator(mode="after")
    def _resolve_sqlite_path(self) -> "Settings":
        # 允许 .env 写相对路径，统一解析到 backend/ 下，避免受启动目录影响
        prefix = "sqlite:///"
        if self.database_url.startswith(prefix):
            raw = self.database_url[len(prefix) :]
            if not raw.startswith("/") and ":" not in raw:
                self.database_url = prefix + (BASE_DIR / raw).resolve().as_posix()
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
