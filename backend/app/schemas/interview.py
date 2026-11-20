from pydantic import BaseModel, Field


class InterviewQuestion(BaseModel):
    id: str
    category: str = "technical"
    question: str
    focus: str = ""
    reference_points: list[str] = Field(default_factory=list)


class InterviewPlan(BaseModel):
    questions: list[InterviewQuestion] = Field(default_factory=list)


class InterviewAnswerIn(BaseModel):
    question_id: str
    answer: str = Field(min_length=1, max_length=4000)


class InterviewCreateIn(BaseModel):
    job_id: int


class QuestionScore(BaseModel):
    question_id: str
    score: float = 0
    rationale: str = ""


class ScoreResult(BaseModel):
    results: list[QuestionScore] = Field(default_factory=list)


class InterviewReport(BaseModel):
    overall_score: float = 0
    dimensions: dict[str, float] = Field(default_factory=dict)
    strengths: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    summary: str = ""
