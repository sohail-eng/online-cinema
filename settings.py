from pydantic import BaseSettings


class Settings(BaseSettings):
    MAILJET_API_KEY: str
    MAILJET_API_SECRET_KEY: str
    SECRET_KEY: str

    class Config:
        env_file = ".env"

settings = Settings()