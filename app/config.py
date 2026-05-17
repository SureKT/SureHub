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

    @property
    def allowed_user_ids(self) -> list[int]:
        return [int(uid.strip()) for uid in self.TELEGRAM_ALLOWED_USER_IDS.split(",")]

    class Config:
        env_file = ".env"


settings = Settings()
