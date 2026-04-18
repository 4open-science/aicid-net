from datetime import datetime

from pydantic import BaseModel, EmailStr, model_validator


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str

    @model_validator(mode="before")
    @classmethod
    def populate_password_from_operator_password(cls, data):
        if isinstance(data, dict) and "password" not in data and "operator_password" in data:
            data = data.copy()
            data["password"] = data["operator_password"]
        return data


class UserRead(BaseModel):
    id: int
    email: str
    full_name: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenRefresh(BaseModel):
    refresh_token: str
