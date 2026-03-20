from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.businesses import router as businesses_router
from app.api.v1.clients import router as clients_router
from app.api.v1.services import router as services_router
from app.api.v1.templates import router as templates_router
from app.api.v1.reminders import router as reminders_router
from app.api.v1.webhooks import router as webhooks_router
from app.api.v1.service_logs import router as service_logs_router
from app.api.v1.analytics import router as analytics_router
from app.api.v1.notifications import router as notifications_router
from app.api.v1.client_history import router as client_history_router
from app.api.v1.appointments import router as appointments_router
from app.api.v1.schedule import router as schedule_router
from app.api.v1.reports import router as reports_router
from app.api.v1.clients_bulk import router as clients_bulk_router
from app.api.v1.admin import router as admin_router

api_router = APIRouter()

api_router.include_router(auth_router)
api_router.include_router(businesses_router)
api_router.include_router(clients_bulk_router)  # antes que clients para evitar colisión en /bulk-upload
api_router.include_router(clients_router)
api_router.include_router(services_router)
api_router.include_router(templates_router)
api_router.include_router(reminders_router)
api_router.include_router(webhooks_router)
api_router.include_router(service_logs_router)
api_router.include_router(analytics_router)
api_router.include_router(notifications_router)
api_router.include_router(client_history_router)
api_router.include_router(appointments_router)
api_router.include_router(schedule_router)
api_router.include_router(reports_router)
api_router.include_router(admin_router)
