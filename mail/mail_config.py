from fastapi_mail import ConnectionConfig
from mail.mail_config_reader import mail_config

conf = ConnectionConfig(
    MAIL_USERNAME=mail_config.MAIL_USERNAME,
    MAIL_PASSWORD=mail_config.MAIL_PASSWORD.get_secret_value(),
    MAIL_FROM=mail_config.MAIL_USERNAME,
    MAIL_PORT=465,
    MAIL_SERVER="smtp.yandex.ru",
    MAIL_STARTTLS=False,
    MAIL_SSL_TLS=True,
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True
)
