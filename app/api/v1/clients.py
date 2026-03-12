from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID

from app.core.database import get_db
from app.models.client import Client, ClientStatus
from app.schemas.client import ClientCreate, ClientUpdate, ClientResponse

router = APIRouter(prefix="/businesses/{business_id}/clients", tags=["clients"])


@router.post("/", response_model=ClientResponse, status_code=status.HTTP_201_CREATED)
async def create_client(business_id: UUID, data: ClientCreate, db: AsyncSession = Depends(get_db)):
    client = Client(
        business_id=business_id,
        display_name=data.display_name,
        phone=data.phone,
        email=data.email,
        preferred_channel=data.preferred_channel,
        notes=data.notes,
    )
    db.add(client)
    await db.flush()
    await db.refresh(client)
    return client


@router.get("/", response_model=list[ClientResponse])
async def list_clients(
    business_id: UUID,
    status: ClientStatus | None = None,
    search: str | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    query = select(Client).where(Client.business_id == business_id)
    if status:
        query = query.where(Client.status == status)
    if search:
        query = query.where(Client.display_name.ilike(f"%{search}%"))
    query = query.offset(skip).limit(limit).order_by(Client.created_at.desc())

    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{client_id}", response_model=ClientResponse)
async def get_client(business_id: UUID, client_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Client).where(Client.id == client_id, Client.business_id == business_id)
    )
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    return client


@router.patch("/{client_id}", response_model=ClientResponse)
async def update_client(business_id: UUID, client_id: UUID, data: ClientUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Client).where(Client.id == client_id, Client.business_id == business_id)
    )
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(client, field, value)

    await db.flush()
    await db.refresh(client)
    return client
