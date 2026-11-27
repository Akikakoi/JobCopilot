from typing import Literal

from pydantic import BaseModel, Field, field_validator


def _clean_skills(v: list[str]) -> list[str]:
    return [s.strip() for s in v if s and s.strip()]


class JobCreate(BaseModel):
    title: str = Field(min_length=2, max_length=128)
    description: str = ""
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    experience_min: int = Field(default=0, ge=0, le=30)
    experience_max: int = Field(default=10, ge=0, le=30)
    location: str = "不限"
    district: str = ""
    category: str = "其他"
    job_type: str = "全职"
    salary_min: float = Field(default=0, ge=0)
    salary_max: float = Field(default=0, ge=0)
    status: Literal["open", "closed"] = "open"

    @field_validator("required_skills", "preferred_skills")
    @classmethod
    def _skills(cls, v: list[str]) -> list[str]:
        return _clean_skills(v)


class JobFeedbackIn(BaseModel):
    action: Literal["dislike", "save", "clear"]
    reason: str = Field(default="", max_length=200)


class JobUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    required_skills: list[str] | None = None
    preferred_skills: list[str] | None = None
    experience_min: int | None = None
    experience_max: int | None = None
    location: str | None = None
    district: str | None = None
    category: str | None = None
    job_type: str | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    status: Literal["open", "closed"] | None = None

    @field_validator("required_skills", "preferred_skills")
    @classmethod
    def _skills(cls, v: list[str] | None) -> list[str] | None:
        return None if v is None else _clean_skills(v)
