from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    ANTHROPIC_API_KEY: str
    TELEGRAM_BOT_TOKEN: str
    TELEGRAM_ALLOWED_USER_IDS: str  # "123,456" → parseado a lista
    APP_ENV: str = "local"
    DATABASE_URL: str = "sqlite:///./surehub.db"
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

    # Google Calendar — OAuth web flow (token persistido en SQLite, no en fichero)
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:8001/api/calendar/oauth/callback"
    GOOGLE_CALENDAR_ID: str = "primary"

    # LLM — tags usan Haiku (barato); chat/análisis usan Sonnet
    LLM_MODEL: str = "claude-sonnet-4-6"
    TAG_MODEL: str = "claude-haiku-4-5"

    # LLM local (Ollama en el server, CPU) para el tier local_ok.
    # OLLAMA_BASE_URL vacío = tier local_ok 100% cloud: ese es el interruptor,
    # así dev sin Ollama funciona igual sin una flag aparte.
    OLLAMA_BASE_URL: str = ""
    OLLAMA_MODEL: str = "qwen2.5:3b"
    LLM_LOCAL_TIMEOUT: float = 20.0

    @property
    def allowed_user_ids(self) -> list[int]:
        return [int(uid.strip()) for uid in self.TELEGRAM_ALLOWED_USER_IDS.split(",")]

    class Config:
        env_file = ".env"


settings = Settings()
