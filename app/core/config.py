from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # App
    APP_NAME: str = "RecordApp"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"
    # production | staging | development — usado para fail-closed de firmas, etc.
    ENV: str = "development"

    # CORS — coma-separado en env, parseado en main.py
    CORS_ORIGINS: str = "http://localhost:5173,https://recordapp-production.up.railway.app"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://user:password@localhost:5432/recordapp"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # WhatsApp Cloud API (Meta — DEPRECADO, ver MESSAGING_PROVIDER)
    WHATSAPP_TOKEN: str = ""
    WHATSAPP_PHONE_NUMBER_ID: str = ""
    WHATSAPP_VERIFY_TOKEN: str = ""
    WHATSAPP_API_URL: str = "https://graph.facebook.com/v21.0"

    # Twilio (provider activo)
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_API_KEY_SID: str = ""
    TWILIO_API_KEY_SECRET: str = ""
    TWILIO_WHATSAPP_NUMBER: str = ""  # whatsapp:+573001234567
    TWILIO_WEBHOOK_AUTH_TOKEN: str = ""  # firma de webhooks
    TWILIO_CONTENT_SID_RECORDATORIO_CITA: str = ""
    TWILIO_CONTENT_SID_FELIZ_CUMPLEANOS: str = ""
    TWILIO_CONTENT_SID_ENCUESTA_SERVICIO: str = ""
    TWILIO_CONTENT_SID_REACTIVACION_CLIENTE: str = ""
    TWILIO_CONTENT_SID_CONFIRMACION_OPTOUT: str = ""
    TWILIO_CONTENT_SID_RESUMEN_SERVICIO: str = ""

    # Proveedor activo
    MESSAGING_PROVIDER: str = "twilio"

    # JWT Auth
    SECRET_KEY: str = "change-this-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # Observability
    SENTRY_DSN: str = ""
    SENTRY_TRACES_SAMPLE_RATE: float = 0.1

    # Clasificador LLM opcional para intents de webhook entrante
    LLM_INTENT_CLASSIFIER_ENABLED: bool = False
    ANTHROPIC_API_KEY: str = ""
    LLM_MODEL: str = "claude-haiku-4-5-20251001"

    model_config = {"env_file": ".env", "extra": "ignore"}

    @property
    def is_production(self) -> bool:
        return self.ENV.lower() == "production"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
