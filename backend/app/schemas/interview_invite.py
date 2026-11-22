from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class InterviewInviteIn(BaseModel):
    scheduled_at: datetime
    duration_minutes: int = Field(default=45, ge=15, le=240)
    mode: Literal["onsite", "video", "phone"] = "video"
    location: str = Field(default="", max_length=255)
    note: str = Field(default="", max_length=2000)
    round: int | None = Field(default=None, ge=1, le=10)


class InterviewInviteRespondIn(BaseModel):
    action: Literal["confirm", "decline"]
    note: str = Field(default="", max_length=2000)


class InterviewInviteCancelIn(BaseModel):
    note: str = Field(default="", max_length=2000)
