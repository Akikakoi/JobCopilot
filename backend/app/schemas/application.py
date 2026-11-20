from pydantic import BaseModel, Field


class ApplicationCreate(BaseModel):
    job_id: int
    cover_letter: str = ""
    resume_id: int | None = None


class ApplicationStatusIn(BaseModel):
    status: str = Field(description="submitted / screening / interview / offer / rejected")
    note: str = ""
