from uuid import UUID
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.business import Business

bearer_scheme = HTTPBearer()


async def get_current_business(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> Business:
    """Extrae el business autenticado del token JWT."""
    business_id = decode_access_token(credentials.credentials)
    if not business_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
        )
    result = await db.execute(
        select(Business).where(Business.id == UUID(business_id), Business.is_active.is_(True))
    )
    business = result.scalar_one_or_none()
    if not business:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Negocio no encontrado o inactivo",
        )
    return business


def verify_business_access(business_id: UUID, current: Business = Depends(get_current_business)) -> Business:
    """Verifica que el business_id de la URL coincida con el token."""
    if current.id != business_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes acceso a este negocio",
        )
    return current
