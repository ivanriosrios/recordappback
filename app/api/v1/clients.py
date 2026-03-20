import csv
import io

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID

from app.core.database import get_db
from app.core.deps import verify_business_access
from app.models.business import Business
from app.models.client import Client, ClientStatus, ChannelType
from app.schemas.client import ClientCreate, ClientUpdate, ClientResponse

router = APIRouter(prefix="/businesses/{business_id}/clients", tags=["clients"])


@router.post("/", response_model=ClientResponse, status_code=status.HTTP_201_CREATED)
async def create_client(business_id: UUID, data: ClientCreate, _biz: Business = Depends(verify_business_access), db: AsyncSession = Depends(get_db)):
    # Normalizar enums a minúsculas para evitar errores de tipo en PostgreSQL
    if isinstance(data.preferred_channel, ChannelType):
        channel_enum = data.preferred_channel
    elif data.preferred_channel:
        ch_val = str(data.preferred_channel).lower()
        channel_enum = ChannelType(ch_val) if ch_val in {c.value for c in ChannelType} else ChannelType.WHATSAPP
    else:
        channel_enum = ChannelType.WHATSAPP

    status_enum = ClientStatus.ACTIVE  # default

    client = Client(
        business_id=business_id,
        display_name=data.display_name,
        phone=data.phone,
        email=data.email,
        preferred_channel=channel_enum,
        status=status_enum,
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
    _biz: Business = Depends(verify_business_access),
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
async def get_client(business_id: UUID, client_id: UUID, _biz: Business = Depends(verify_business_access), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Client).where(Client.id == client_id, Client.business_id == business_id)
    )
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    return client


@router.patch("/{client_id}", response_model=ClientResponse)
async def update_client(business_id: UUID, client_id: UUID, data: ClientUpdate, _biz: Business = Depends(verify_business_access), db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Client).where(Client.id == client_id, Client.business_id == business_id)
    )
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    update_data = data.model_dump(exclude_unset=True)

    # Normalizar enums si vienen como string
    if "preferred_channel" in update_data:
        val = update_data["preferred_channel"]
        if isinstance(val, ChannelType):
            update_data["preferred_channel"] = val
        else:
            ch_val = str(val).lower()
            update_data["preferred_channel"] = ChannelType(ch_val) if ch_val in {c.value for c in ChannelType} else ChannelType.WHATSAPP

    if "status" in update_data:
        val = update_data["status"]
        if isinstance(val, ClientStatus):
            update_data["status"] = val
        else:
            st_val = str(val).lower()
            update_data["status"] = ClientStatus(st_val) if st_val in {s.value for s in ClientStatus} else ClientStatus.ACTIVE

    for field, value in update_data.items():
        setattr(client, field, value)

    await db.flush()
    await db.refresh(client)
    return client


@router.post("/bulk-upload", status_code=status.HTTP_200_OK)
async def bulk_upload_clients(
    business_id: UUID,
    file: UploadFile = File(...),
    _biz: Business = Depends(verify_business_access),
    db: AsyncSession = Depends(get_db),
):
    """
    Carga masiva de clientes desde CSV.
    Columnas: nombre (req), telefono (req), email (opt), notas (opt)
    Retorna un resumen: created, skipped, errors.
    """
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos .csv")

    content = await file.read()
    try:
        text = content.decode("utf-8-sig")  # utf-8-sig maneja BOM de Excel
    except UnicodeDecodeError:
        text = content.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text))

    # Normalizar nombres de columna a minúsculas sin espacios
    def normalize_key(row):
        return {k.strip().lower(): v.strip() if v else "" for k, v in row.items()}

    # Obtener teléfonos existentes para evitar duplicados
    existing = await db.execute(
        select(Client.phone).where(Client.business_id == business_id)
    )
    existing_phones = {row[0] for row in existing.fetchall()}

    created = 0
    skipped = 0
    errors = []

    for i, raw_row in enumerate(reader, start=2):  # fila 2 = primera de datos
        row = normalize_key(raw_row)

        name = row.get("nombre") or row.get("name") or row.get("display_name", "")
        phone = row.get("telefono") or row.get("phone") or row.get("teléfono", "")
        email = row.get("email") or row.get("correo", "") or None
        notes = row.get("notas") or row.get("notes", "") or None

        if not name or not phone:
            errors.append({"row": i, "reason": "Nombre y teléfono son obligatorios"})
            continue

        # Normalizar teléfono: quitar espacios y guiones
        phone_clean = phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        # Agregar +57 si es número colombiano de 10 dígitos sin prefijo
        if phone_clean.isdigit() and len(phone_clean) == 10:
            phone_clean = "57" + phone_clean

        if phone_clean in existing_phones:
            skipped += 1
            continue

        client = Client(
            business_id=business_id,
            display_name=name,
            phone=phone_clean,
            email=email or None,
            notes=notes or None,
            status=ClientStatus.ACTIVE,
            preferred_channel=ChannelType.WHATSAPP,
        )
        db.add(client)
        existing_phones.add(phone_clean)
        created += 1

    await db.flush()
    return {"created": created, "skipped": skipped, "errors": errors, "total_rows": created + skipped + len(errors)}
