from pydantic import BaseModel, Field, field_validator


class CompanyUpdateIn(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    industry: str = Field(default="", max_length=64)
    description: str = ""

    @field_validator("name")
    @classmethod
    def _strip_name(cls, v: str) -> str:
        value = v.strip()
        if not value:
            raise ValueError("公司名称不能为空")
        return value
