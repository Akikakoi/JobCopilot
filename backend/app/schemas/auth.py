from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

Role = Literal["seeker", "employer"]


class RegisterIn(BaseModel):
    username: str = Field(min_length=2, max_length=32)
    password: str = Field(min_length=6, max_length=64)
    role: Role
    display_name: str = Field(min_length=1, max_length=32)
    company_name: str | None = Field(default=None, max_length=64)

    @field_validator("username")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()


class LoginIn(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: int
    username: str
    role: str
    display_name: str
    company_name: str | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
