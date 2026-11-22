from pydantic import BaseModel, Field, field_validator


class EducationItem(BaseModel):
    school: str = ""
    degree: str = ""
    major: str = ""
    period: str = ""


class WorkItem(BaseModel):
    company: str = ""
    role: str = ""
    period: str = ""
    highlights: list[str] = Field(default_factory=list)

    @field_validator("highlights", mode="before")
    @classmethod
    def _listify(cls, v):
        if isinstance(v, str):
            return [v]
        return v or []


class Expectations(BaseModel):
    locations: list[str] = Field(default_factory=list)
    salary_min: float | None = None
    salary_max: float | None = None
    job_types: list[str] = Field(default_factory=list)


class ResumeStructured(BaseModel):
    name: str = ""
    title: str = ""
    skills: list[str] = Field(default_factory=list)
    years_of_experience: float = 0
    education: list[EducationItem] = Field(default_factory=list)
    work_experience: list[WorkItem] = Field(default_factory=list)
    expectations: Expectations = Field(default_factory=Expectations)

    model_config = {"extra": "ignore"}

    @field_validator("skills", mode="before")
    @classmethod
    def _skills(cls, v):
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return v or []


class ResumePasteIn(BaseModel):
    text: str = Field(min_length=20, description="简历纯文本（兜底输入方式）")


class OptimizeIn(BaseModel):
    job_id: int


class OptimizeApplyIn(BaseModel):
    job_id: int
    skills_to_add: list[str] = Field(default_factory=list)


class ResumeRewrite(BaseModel):
    target: str = ""
    original: str = ""
    suggestion: str = ""


class ResumeOptimizeResult(BaseModel):
    summary: str = ""
    missing_skills: list[str] = Field(default_factory=list)
    skills_to_add: list[str] = Field(default_factory=list)
    rewrites: list[ResumeRewrite] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
