from fastapi import APIRouter

from app.api.v1.businesses import router as businesses_router
from app.api.v1.clients import router as clients_router
from app.api.v1.services import router as services_router
from app.api.v1.templates import router as templates_router
from app.api.v1.reminders import router as reminders_router
from app.api.v1.webhooks import router as webhooks_router

api_router = APIRouter()

api_router.include_router(businesses_router)
api_router.include_router(clients_router)
api_router.include_router(services_router)
api_router.include_router(templates_router)
api_router.include_router(reminders_router)
api_router.include_router(webhooks_router)
