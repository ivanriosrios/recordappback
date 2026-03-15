import re
from uuid import UUID
from pydantic import BaseModel, EmailStr, field_validator


class RegisterRequest(BaseModel):
    name: str
    business_type: str = "general"
    whatsapp_phone: str
    email: EmailStr
    password: str

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        v = v.strip()
        if len(v) < 2:
            raise ValueError("El nombre del negocio debe tener al menos 2 caracteres")
        if len(v) > 100:
            raise ValueError("El nombre del negocio no puede superar 100 caracteres")
        return v

    @field_validator("whatsapp_phone")
    @classmethod
    def validate_phone(cls, v):
        # Limpiar: solo dígitos y +
        digits = re.sub(r"[^\d]", "", v)
        if len(digits) < 10:
            raise ValueError("El número debe tener al menos 10 dígitos incluyendo indicativo de país")
        if len(digits) > 15:
            raise ValueError("El número es demasiado largo")
        # Verificar que empiece con un indicativo conocido
        valid_prefixes = ("57", "52", "51", "56", "54", "34", "1", "55")
        if not any(digits.startswith(p) for p in valid_prefixes):
            raise ValueError("Incluye el indicativo de país (ej: 57 para Colombia)")
        return digits  # Guardar solo dígitos

    @field_validator("password")
    @classmethod
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError("La contraseña debe tener al menos 8 caracteres")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    business_id: UUID
    business_name: str
