from pydantic import BaseModel, Field


class ApplicationCreate(BaseModel):
    job_id: int
    cover_letter: str = ""
    resume_id: int | None = None


class ApplicationStatusIn(BaseModel):
    status: str = Field(
        description="submitted / screening / interview / rejected（进入 offer 阶段请使用 Offer 接口）"
    )
    note: str = ""
