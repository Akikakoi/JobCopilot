from pydantic import BaseModel, Field


class SubscriptionFilters(BaseModel):
    keywords: str = ""
    location: str = ""
    salary_min: float | None = None
    skills: list[str] = Field(default_factory=list)
    match_score_min: float | None = None


class SubscriptionIn(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    filters: SubscriptionFilters = Field(default_factory=SubscriptionFilters)
    active: bool = True


class SubscriptionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=40)
    filters: SubscriptionFilters | None = None
    active: bool | None = None
