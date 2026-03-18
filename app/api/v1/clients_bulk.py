"""
Carga masiva de clientes desde CSV (KOS-58).

POST /businesses/{id}/clients/bulk-upload
"""
import csv
import io
import re
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.deps import verify_business_access
from app.models.business import Business
from app.models.client import Client, ClientStatus

router = APIRouter(prefix="/businesses/{business_id}/clients", tags=["clients"])
logger = logging.getLogger(__name__)

TEMPLATE_HEADERS = "nombre,telefono,email,notas"


def _normalize_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 10 and digits.startswith("3"):
        return f"+57{digits}"
    if len(digits) == 12 and digits.startswith("57"):
        return f"+{digits}"
    if len(digits) >= 10:
        return f"+{digits}"
    raise ValueError(f"Teléfono inválido: {raw}")


def _find_col(fields_lower: dict, *keywords) -> str | None:
    for kw in keywords:
        for col_lower, col_orig in fields_lower.items():
            if kw in col_lower:
                return col_orig
    return None


@router.post("/bulk-upload")
async def bulk_upload_clients(
    business_id: UUID,
    file: UploadFile = File(...),
    _biz: Business = Depends(verify_business_access),
    db: AsyncSession = Depends(get_db),
):
    """
    Carga masiva de clientes desde CSV.

    Columnas requeridas: nombre, telefono
    Columnas opcionales: email, notas (o info, extra)

    Retorna estadísticas: created, skipped (duplicados), errors.
    """
    if not (file.filename or "").lower().endswith(".csv"):
        raise HTTPException(
            status_code=400,
            detail="Solo se aceptan archivos .csv. Descarga la plantilla de ejemplo.",
        )

    content = await file.read()
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = content.decode("latin-1")
        except Exception:
            raise HTTPException(status_code=400, detail="No se pudo leer el archivo. Verifica que sea UTF-8 o Latin-1.")

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="Archivo CSV vacío o sin encabezados.")

    fields_lower = {f.strip().lower(): f.strip() for f in reader.fieldnames if f}

    name_col = _find_col(fields_lower, "nombre", "name", "cliente")
    phone_col = _find_col(fields_lower, "tel", "celular", "phone", "whatsapp", "movil", "móvil")
    email_col = _find_col(fields_lower, "email", "correo")
    notes_col = _find_col(fields_lower, "nota", "info", "extra", "observa")

    if not name_col or not phone_col:
        raise HTTPException(
            status_code=400,
            detail=(
                f"No se encontraron columnas requeridas. "
                f"Columnas detectadas: {list(reader.fieldnames)}. "
                f"Se necesitan columnas con 'nombre' y 'telefono'."
            ),
        )

    # Obtener teléfonos existentes para evitar duplicados
    existing_res = await db.execute(
        select(Client.phone).where(Client.business_id == business_id)
    )
    existing_phones = {r[0] for r in existing_res.all()}

    created = []
    skipped = []
    errors = []
    new_clients = []

    for i, row in enumerate(reader, start=2):
        raw_name = (row.get(name_col) or "").strip()
        raw_phone = (row.get(phone_col) or "").strip()

        if not raw_name or not raw_phone:
            errors.append({"row": i, "reason": "Nombre o teléfono vacío", "data": f"{raw_name} / {raw_phone}"})
            continue

        try:
            phone = _normalize_phone(raw_phone)
        except ValueError as e:
            errors.append({"row": i, "reason": str(e), "data": raw_phone})
            continue

        if phone in existing_phones:
            skipped.append({"row": i, "name": raw_name, "phone": phone, "reason": "Ya existe"})
            continue

        email = (row.get(email_col, "") or "").strip() or None if email_col else None
        notes = (row.get(notes_col, "") or "").strip() or None if notes_col else None

        client = Client(
            business_id=business_id,
            display_name=raw_name[:50],
            phone=phone,
            email=email[:100] if email else None,
            extra_info=notes,
            status=ClientStatus.ACTIVE,
        )
        db.add(client)
        existing_phones.add(phone)
        new_clients.append(client)
        created.append({"row": i, "name": raw_name, "phone": phone})

    if new_clients:
        await db.flush()

    logger.info(
        f"[bulk-upload] business={business_id} created={len(created)} "
        f"skipped={len(skipped)} errors={len(errors)}"
    )

    return {
        "total_rows": len(created) + len(skipped) + len(errors),
        "created": len(created),
        "skipped": len(skipped),
        "errors_count": len(errors),
        "created_list": created[:50],
        "skipped_list": skipped[:50],
        "errors": errors[:50],
        "template": TEMPLATE_HEADERS,
    }
