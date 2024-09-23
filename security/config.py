import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr


DOTENV = os.path.join(os.path.dirname(os.path.dirname(__file__)), "security.env")


class SecuritySettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=DOTENV,
        env_file_encoding="utf-8"
    )
    SECRET_KEY: SecretStr
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    ALGORITHM: str


security_conf = SecuritySettings()
