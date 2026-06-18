from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    ANTHROPIC_API_KEY: str
    TELEGRAM_BOT_TOKEN: str
    TELEGRAM_ALLOWED_USER_IDS: str  # "123,456" → parseado a lista
    APP_ENV: str = "local"
    SECRET_KEY: str = "dev-secret"
    DATABASE_URL: str = "sqlite:///./surehub.db"
    TELEGRAM_MODE: str = "polling"
    WEBHOOK_URL: str = ""
    TIMEZONE: str = "Europe/Madrid"  # hora local para timestamps de notas
    INBOX_DIGEST_HOUR: int = 9  # hora local del digest diario de la inbox

    # Obsidian vault (notas .md planas, sin DB)
    OBSIDIAN_VAULT_PATH: str = "./data/obsidian"

    # Whisper local (notas de voz en Telegram)
    WHISPER_MODEL: str = "small"
    WHISPER_DEVICE: str = "cpu"
    WHISPER_COMPUTE_TYPE: str = "int8"
    WHISPER_LANGUAGE: str = "es"
    WHISPER_CACHE_DIR: str = "/data/.cache/whisper"

    # LLM — tags usan Haiku (barato); chat/análisis usan Sonnet
    LLM_MODEL: str = "claude-sonnet-4-6"
    TAG_MODEL: str = "claude-haiku-4-5"

    # Google Calendar (Inbox Fase 2 — eventos)
    GOOGLE_CALENDAR_CREDENTIALS: str = "./data/google_client_secret.json"
    GOOGLE_CALENDAR_TOKEN: str = "./data/google_token.json"
    GOOGLE_CALENDAR_ID: str = "primary"

    @property
    def allowed_user_ids(self) -> list[int]:
        return [int(uid.strip()) for uid in self.TELEGRAM_ALLOWED_USER_IDS.split(",")]

    class Config:
        env_file = ".env"


settings = Settings()
