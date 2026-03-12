from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.api.v1.router import api_router

settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    description="Sistema de recordatorios inteligentes para negocios locales",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS — permitir frontend PWA
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción: restringir al dominio del frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rutas API v1
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/health", tags=["system"])
async def health_check():
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": "0.1.0",
    }


@app.get("/", tags=["system"])
async def root():
    return {
        "message": f"Bienvenido a {settings.APP_NAME} API",
        "docs": "/docs",
    }
