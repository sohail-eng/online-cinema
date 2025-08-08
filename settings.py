from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    MAILJET_API_KEY: str
    MAILJET_API_SECRET_KEY: str
    SECRET_KEY: str
    ADMIN_FULL_NAME: str
    ADMIN_EMAIL: str
    DATABASE_URL: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    REFRESH_TOKEN_EXPIRE_DAYS: int
    WEBSITE_URL: str
    ACTIVATION_TOKEN_EXPIRE_HOURS: int
    PASSWORD_RESET_TOKEN_EXPIRE_HOURS: int

    class Config:
        env_file = ".env"

settings = Settings()
