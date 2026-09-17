from pydantic import BaseModel, EmailStr, Field

from app.models.user import UserRole


class InviteUserRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=255)
    role: UserRole = UserRole.clinician
    temporary_password: str = Field(min_length=8, max_length=72)


class RoleChangeRequest(BaseModel):
    role: UserRole
