from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import hash_password, verify_password, create_access_token
from app.core.deps import get_current_business
from app.models.business import Business, PlanType
from app.schemas.auth import RegisterRequest, LoginRequest, TokenResponse
from app.schemas.business import BusinessResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(data: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Registrar un nuevo negocio y devolver token."""
    # Verificar email único
    existing = await db.execute(select(Business).where(Business.email == data.email))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un negocio con este email",
        )

    business = Business(
        name=data.name,
        business_type=data.business_type,
        whatsapp_phone=data.whatsapp_phone,
        email=data.email,
        password_hash=hash_password(data.password),
        plan=PlanType.FREE,
    )
    db.add(business)
    await db.flush()
    await db.refresh(business)

    token = create_access_token(str(business.id))
    return TokenResponse(
        access_token=token,
        business_id=business.id,
        business_name=business.name,
    )


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Login con email y password."""
    result = await db.execute(
        select(Business).where(Business.email == data.email, Business.is_active.is_(True))
    )
    business = result.scalar_one_or_none()

    if not business or not business.password_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas",
        )

    if not verify_password(data.password, business.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas",
        )

    token = create_access_token(str(business.id))
    return TokenResponse(
        access_token=token,
        business_id=business.id,
        business_name=business.name,
    )


@router.get("/me", response_model=BusinessResponse)
async def get_me(business: Business = Depends(get_current_business)):
    """Devuelve el negocio autenticado."""
    return business
