from pydantic import BaseSettings


class Settings(BaseSettings):
    BOT_TOKEN: str
    SENTRY_DSN: str = ""
    WEBHOOK_URL: str

    class Config:
        env_file = ".env"


settings = Settings()
