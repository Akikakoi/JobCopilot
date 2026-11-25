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
    # 岗位定位：目标职位、技能类别、二级方向
    target_title: str = ""
    categories: list[str] = Field(default_factory=list)
    subcategories: list[str] = Field(default_factory=list)
    # 地点定位：城市 → 区（如 {"上海": ["徐汇区", "闵行区"]}）
    districts: dict[str, list[str]] = Field(default_factory=dict)


class JobIntentIn(BaseModel):
    """用户显式设置的求职意向（岗位定位）。"""

    target_title: str = ""
    categories: list[str] = Field(default_factory=list)
    subcategories: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    districts: dict[str, list[str]] = Field(default_factory=dict)
    salary_min: float | None = None
    salary_max: float | None = None
    job_types: list[str] = Field(default_factory=list)

    @field_validator("target_title")
    @classmethod
    def _title(cls, v: str) -> str:
        return (v or "").strip()[:64]

    @field_validator("categories", "subcategories", "locations", "job_types")
    @classmethod
    def _clean_list(cls, v: list[str]) -> list[str]:
        out: list[str] = []
        for item in v or []:
            item = str(item).strip()
            if item and item not in out:
                out.append(item)
        return out[:10]

    @field_validator("districts")
    @classmethod
    def _clean_districts(cls, v: dict[str, list[str]] | None) -> dict[str, list[str]]:
        """清洗区映射：只保留有区的城市，去掉空值与重复，每个城市最多 8 个区。"""
        if not v:
            return {}
        out: dict[str, list[str]] = {}
        for city, districts in v.items():
            city = str(city or "").strip()
            if not city:
                continue
            cleaned: list[str] = []
            for d in districts or []:
                d = str(d or "").strip()
                if d and d not in cleaned:
                    cleaned.append(d)
            if cleaned:
                out[city] = cleaned[:8]
        return out


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
    job_id: int | None = None
    category: str | None = None
    subcategory: str | None = None


class OptimizeApplyIn(BaseModel):
    job_id: int | None = None
    category: str | None = None
    subcategory: str | None = None
    skills_to_add: list[str] = Field(default_factory=list)


class DiagnoseIn(BaseModel):
    category: str | None = None
    subcategory: str | None = None


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
