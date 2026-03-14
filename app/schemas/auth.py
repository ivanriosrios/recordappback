from uuid import UUID
from pydantic import BaseModel, EmailStr


class RegisterRequest(BaseModel):
    name: str
    business_type: str = "general"
    whatsapp_phone: str
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    business_id: UUID
    business_name: str
