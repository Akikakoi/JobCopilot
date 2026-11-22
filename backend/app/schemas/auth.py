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


class ProfileUpdateIn(BaseModel):
    display_name: str = Field(min_length=1, max_length=32)

    @field_validator("display_name")
    @classmethod
    def _strip(cls, v: str) -> str:
        value = v.strip()
        if not value:
            raise ValueError("显示名不能为空")
        return value


class PasswordChangeIn(BaseModel):
    old_password: str = Field(min_length=1)
    new_password: str = Field(min_length=6, max_length=64)
