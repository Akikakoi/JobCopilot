from typing import Literal

from pydantic import BaseModel, Field


class OnboardingNoteIn(BaseModel):
    note: str = Field(default="", max_length=2000)


class OnboardingResultIn(BaseModel):
    result: Literal["hired", "abandoned"]
    note: str = Field(default="", max_length=2000)
    onboarding_date: str = Field(default="", max_length=32)
