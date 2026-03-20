from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    APP_NAME: str = "RecordApp"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost:5432/recordapp"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # WhatsApp Cloud API (Meta — legacy, se mantiene para backward compat)
    WHATSAPP_TOKEN: str = ""
    WHATSAPP_PHONE_NUMBER_ID: str = ""
    WHATSAPP_VERIFY_TOKEN: str = ""
    WHATSAPP_API_URL: str = "https://graph.facebook.com/v21.0"

    # Twilio (nuevo provider de mensajería)
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_API_KEY_SID: str = ""
    TWILIO_API_KEY_SECRET: str = ""
    TWILIO_WHATSAPP_NUMBER: str = ""  # formato: whatsapp:+573001234567
    TWILIO_WEBHOOK_AUTH_TOKEN: str = ""  # para validar firma de webhooks
    TWILIO_CONTENT_SID_ENCUESTA_SERVICIO: str = ""  # opcional: content_sid del template aprobado

    # Proveedor de mensajería activo: "twilio" o "meta"
    MESSAGING_PROVIDER: str = "twilio"

    # JWT Auth
    SECRET_KEY: str = "change-this-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 horas

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
