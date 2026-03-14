from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID

from app.core.database import get_db
from app.core.deps import verify_business_access
from app.models.business import Business
from app.models.template import Template
from app.schemas.template import TemplateCreate, TemplateUpdate, TemplateResponse

router = APIRouter(prefix="/businesses/{business_id}/templates", tags=["templates"])


@router.post("/", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(business_id: UUID, data: TemplateCreate, _biz: Business = Depends(verify_business_access), db: AsyncSession = Depends(get_db)):
    template = Template(
        business_id=business_id,
        name=data.name,
        body=data.body,
        type=data.type,
        channel=data.channel,
    )
    db.add(template)
    await db.flush()
    await db.refresh(template)
    return template


@router.get("/", response_model=list[TemplateResponse])
async def list_templates(business_id: UUID, _biz: Business = Depends(verify_business_access), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Template).where(Template.business_id == business_id)
    )
    return result.scalars().all()


@router.patch("/{template_id}", response_model=TemplateResponse)
async def update_template(business_id: UUID, template_id: UUID, data: TemplateUpdate, _biz: Business = Depends(verify_business_access), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Template).where(Template.id == template_id, Template.business_id == business_id)
    )
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="Plantilla no encontrada")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(template, field, value)

    await db.flush()
    await db.refresh(template)
    return template
