from pydantic import BaseModel, Field


class MessageIn(BaseModel):
    content: str = Field(min_length=1, max_length=2000)


class ConversationStartIn(BaseModel):
    """发起沟通：求职者传 job_id / company_id，招聘方传 seeker_user_id。"""

    job_id: int | None = None
    company_id: int | None = None
    seeker_user_id: int | None = None
