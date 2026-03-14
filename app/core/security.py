from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

settings = get_settings()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
MAX_BCRYPT_BYTES = 72  # bcrypt ignores after 72 bytes; enforce limit explicitly


def hash_password(password: str) -> str:
    # Guardar contraseñas de más de 72 bytes dispara error en bcrypt
    if len(password.encode("utf-8")) > MAX_BCRYPT_BYTES:
        raise ValueError("Password exceeds bcrypt 72-byte limit")
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    # No intentar verificar contraseñas que exceden el límite de bcrypt
    if len(plain.encode("utf-8")) > MAX_BCRYPT_BYTES:
        return False
    return pwd_context.verify(plain, hashed)


def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return jwt.encode(
        {"sub": subject, "exp": expire},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def decode_access_token(token: str) -> str | None:
    """Devuelve el subject (business_id) o None si es inválido."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None
