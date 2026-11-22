from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class OfferIn(BaseModel):
    salary_min: float = Field(default=0, ge=0)
    salary_max: float = Field(default=0, ge=0)
    start_date: str = Field(default="", max_length=32)
    expires_at: datetime | None = None
    note: str = Field(default="", max_length=2000)

    @model_validator(mode="after")
    def _check_range(self) -> "OfferIn":
        if self.salary_min and self.salary_max and self.salary_max < self.salary_min:
            raise ValueError("最高薪资不能低于最低薪资")
        return self


class OfferRespondIn(BaseModel):
    action: Literal["accept", "decline"]
    note: str = Field(default="", max_length=2000)
