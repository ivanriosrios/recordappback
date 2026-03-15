"""Utilidades para sesiones síncronas en tareas Celery."""


def get_sync_session():
    """Crea una sesión síncrona para usar dentro de Celery (no async)."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.core.config import get_settings

    settings = get_settings()
    # Convierte asyncpg URL a psycopg2 para uso síncrono en Celery
    sync_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    engine = create_engine(sync_url, pool_pre_ping=True)
    Session = sessionmaker(bind=engine)
    return Session()
