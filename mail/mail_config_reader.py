import os
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


DOTENV = os.path.join(os.path.dirname(os.path.dirname(__file__)), "mail.env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=DOTENV,
        env_file_encoding="utf-8"
    )
    MAIL_USERNAME: str
    MAIL_PASSWORD: SecretStr


mail_config = Settings()
