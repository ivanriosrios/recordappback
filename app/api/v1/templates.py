from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID

from app.core.database import get_db
from app.core.deps import verify_business_access
from app.models.business import Business
from app.models.template import Template
from app.schemas.template import TemplateResponse
from app.services.template_seeder import seed_system_templates

router = APIRouter(prefix="/businesses/{business_id}/templates", tags=["templates"])


@router.get("", include_in_schema=True)
@router.get("/", response_model=list[TemplateResponse], include_in_schema=False)
async def list_templates(business_id: UUID, _biz: Business = Depends(verify_business_access), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Template).where(Template.business_id == business_id)
    )
    templates = result.scalars().all()

    # Si no hay templates, seedear automáticamente (migración para negocios existentes)
    if not templates:
        templates = await seed_system_templates(db, business_id)

    return templates


@router.post("/seed", response_model=list[TemplateResponse], status_code=status.HTTP_200_OK)
async def seed_templates(business_id: UUID, _biz: Business = Depends(verify_business_access), db: AsyncSession = Depends(get_db)):
    """Seedea/actualiza las plantillas del sistema para este negocio."""
    templates = await seed_system_templates(db, business_id)
    return templates


@router.get("/{template_id}", response_model=TemplateResponse)
async def get_template(business_id: UUID, template_id: UUID, _biz: Business = Depends(verify_business_access), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Template).where(Template.id == template_id, Template.business_id == business_id)
    )
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Plantilla no encontrada")
    return template
