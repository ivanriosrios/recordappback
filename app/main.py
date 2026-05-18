import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import get_settings
from app.api.v1.router import api_router

settings = get_settings()
logger = logging.getLogger("recordapp")
logging.basicConfig(level=logging.INFO)


# ──────────────────────────────────────────────────────────────────────
# Observabilidad: Sentry (opcional, si hay DSN)
# ──────────────────────────────────────────────────────────────────────

def _init_sentry() -> None:
    if not settings.SENTRY_DSN:
        return
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            environment=settings.ENV,
            traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
            integrations=[FastApiIntegration(), SqlalchemyIntegration()],
            send_default_pii=False,
        )
        logger.info("[sentry] inicializado")
    except Exception as exc:
        logger.warning(f"[sentry] no se pudo inicializar: {exc}")


_init_sentry()


# ──────────────────────────────────────────────────────────────────────
# Métricas mínimas: latencia + status por request en logs estructurados
# ──────────────────────────────────────────────────────────────────────

class AccessLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "access method=%s path=%s status=%s elapsed_ms=%.1f",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
        return response


# ──────────────────────────────────────────────────────────────────────
# App
# ──────────────────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.APP_NAME,
    description="Sistema de recordatorios inteligentes para negocios locales",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(AccessLogMiddleware)

# CORS — orígenes desde env, parseado a lista
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/health", tags=["system"])
async def health_check():
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": "0.1.0",
        "env": settings.ENV,
    }


@app.get("/", tags=["system"])
async def root():
    return {
        "message": f"Bienvenido a {settings.APP_NAME} API",
        "docs": "/docs",
    }
