"""结构化模拟面试：出题 → 逐题作答 → 评分 → 报告。"""

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.llm.client import chat_completion, message_text
from app.models import Application, Interview, Job, Resume, User
from app.schemas.interview import InterviewPlan, InterviewReport, ScoreResult
from app.services.job_service import job_to_dict

DIMENSIONS = ("skills", "project", "communication", "motivation")


class InterviewError(ValueError):
    pass


PLAN_SYSTEM = """你是资深技术面试官。根据岗位与候选人简历，出 6 道中文面试题：技术 2 道、项目 2 道、行为 2 道。
只输出 JSON：
{"questions": [{"id": "q1", "category": "technical|project|behavior", "question": "题目", "focus": "考察点", "reference_points": ["要点1", "要点2"]}]}

要求：
- 题目必须基于岗位必需技能与简历中的真实经历，不得编造简历里没有的项目；
- 避免重复，每题只问一个点，难度中等；
- 中文，不要输出 JSON 以外的内容。"""

SCORE_SYSTEM = """你是严格但公正的面试评估官。根据岗位要求与每题参考要点，为每个回答打分（0-100）并给出一句评语。
只输出 JSON：
{"results": [{"question_id": "q1", "score": 72, "rationale": "一句话评语"}]}

要求：
- 必须覆盖所有 question_id；
- 评分区分度明显：优秀 85+，合格 70-84，薄弱 50-69，跑题或空泛 <50；
- 评语要指出具体依据，不得编造回答里没有的内容；
- 中文，不要输出 JSON 以外的内容。"""

REPORT_SYSTEM = """你是人才评估专家。基于逐题得分与评语，输出面试报告，只输出 JSON：
{"overall_score": 0, "dimensions": {"skills": 0, "project": 0, "communication": 0, "motivation": 0}, "strengths": [], "risks": [], "suggestions": [], "summary": "一句话结论"}

要求：
- 分数为 0-100；
- strengths / risks / suggestions 各 2-3 条，具体可执行；
- 中文，不要使用 Markdown 表格。"""


async def _json_call(system: str, payload: dict, temperature: float, model_cls):
    messages: list[dict] = [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False, default=str)},
    ]
    last_error: Exception | None = None
    for _ in range(2):
        reply = await chat_completion(
            messages, temperature=temperature, response_format={"type": "json_object"}
        )
        content = message_text(reply.get("content"))
        try:
            return model_cls.model_validate(json.loads(content))
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            messages.append({"role": "assistant", "content": content})
            messages.append(
                {"role": "user", "content": f"输出不符合要求（{exc}），请只输出合法 JSON。"}
            )
    raise InterviewError(f"AI 输出解析失败：{last_error}")


def _resume_of(db: Session, user_id: int) -> Resume | None:
    return db.scalar(select(Resume).where(Resume.user_id == user_id))


async def generate_plan(job: Job, resume: Resume) -> dict:
    payload = {"岗位": job_to_dict(job), "简历": resume.structured or {}}
    last_error: Exception | None = None
    for _ in range(2):
        try:
            plan = await _json_call(PLAN_SYSTEM, payload, 0.4, InterviewPlan)
        except InterviewError as exc:
            last_error = exc
            continue
        if len(plan.questions) < 4:
            last_error = InterviewError("题目数量不足")
            continue
        # 规范化 id，保证唯一可引用
        seen: set[str] = set()
        for index, question in enumerate(plan.questions, start=1):
            if not question.id or question.id in seen:
                question.id = f"q{index}"
            seen.add(question.id)
        return plan.model_dump()
    raise InterviewError(f"出题失败，请稍后重试（{last_error}）")


async def create_interview(db: Session, user: User, job_id: int) -> Interview:
    resume = _resume_of(db, user.id)
    if resume is None:
        raise InterviewError("请先创建简历，才能开始模拟面试")
    job = db.get(Job, job_id)
    if job is None or job.status != "open":
        raise InterviewError("岗位不存在或已下线")

    plan = await generate_plan(job, resume)
    application = db.scalar(
        select(Application).where(
            Application.user_id == user.id, Application.job_id == job.id
        )
    )
    interview = Interview(
        user_id=user.id,
        job_id=job.id,
        application_id=application.id if application else None,
        status="in_progress",
        plan=plan,
        answers=[],
    )
    db.add(interview)
    db.commit()
    db.refresh(interview)
    return interview


def get_owned_interview(db: Session, user: User, interview_id: int) -> Interview:
    interview = db.get(Interview, interview_id)
    if interview is None or interview.user_id != user.id:
        raise PermissionError("面试记录不存在或无权访问")
    return interview


def submit_answer(
    db: Session, user: User, interview_id: int, question_id: str, answer: str
) -> Interview:
    interview = get_owned_interview(db, user, interview_id)
    if interview.status == "completed":
        raise InterviewError("该面试已完成，不能继续作答")
    questions = (interview.plan or {}).get("questions") or []
    if not any(question.get("id") == question_id for question in questions):
        raise InterviewError("题目不存在")
    text = answer.strip()
    if not text:
        raise InterviewError("回答不能为空")

    answers = list(interview.answers or [])
    answers = [item for item in answers if item.get("question_id") != question_id]
    answers.append({"question_id": question_id, "answer": text})
    interview.answers = answers
    db.commit()
    db.refresh(interview)
    return interview


async def _score_answers(job: Job, plan: dict, answers: list[dict]) -> list[dict]:
    question_map = {q["id"]: q for q in plan.get("questions") or []}
    pairs = [
        {
            "question_id": item["question_id"],
            "question": question_map[item["question_id"]]["question"],
            "focus": question_map[item["question_id"]].get("focus", ""),
            "reference_points": question_map[item["question_id"]].get("reference_points", []),
            "answer": item["answer"],
        }
        for item in answers
        if item["question_id"] in question_map
    ]
    payload = {"岗位": job_to_dict(job), "问答": pairs}

    result = await _json_call(SCORE_SYSTEM, payload, 0.2, ScoreResult)
    scores = {item.question_id: item for item in result.results}
    if set(scores) != {pair["question_id"] for pair in pairs}:
        result = await _json_call(SCORE_SYSTEM, payload, 0.2, ScoreResult)
        scores = {item.question_id: item for item in result.results}
        if set(scores) != {pair["question_id"] for pair in pairs}:
            raise InterviewError("评分结果不完整，请重试")

    merged: list[dict] = []
    for item in answers:
        question_id = item["question_id"]
        score = scores.get(question_id)
        merged.append(
            {
                **item,
                "score": max(0.0, min(100.0, float(score.score if score else 0))),
                "rationale": score.rationale if score else "",
            }
        )
    return merged


async def _build_report(
    job: Job, resume: Resume, answers: list[dict]
) -> dict:
    payload = {
        "岗位": job_to_dict(job),
        "简历摘要": {
            "title": (resume.structured or {}).get("title", ""),
            "skills": (resume.structured or {}).get("skills", []),
            "years_of_experience": (resume.structured or {}).get("years_of_experience", 0),
        },
        "逐题得分": [
            {"question_id": item["question_id"], "score": item["score"], "rationale": item["rationale"]}
            for item in answers
        ],
    }
    report = await _json_call(REPORT_SYSTEM, payload, 0.2, InterviewReport)
    data = report.model_dump()

    scores = [item["score"] for item in answers if "score" in item]
    average = round(sum(scores) / len(scores), 1) if scores else 0.0
    dimensions = data.get("dimensions") or {}
    for key in DIMENSIONS:
        value = dimensions.get(key)
        dimensions[key] = round(float(value), 1) if isinstance(value, (int, float)) else average
    data["dimensions"] = dimensions
    data["overall_score"] = max(0.0, min(100.0, float(data.get("overall_score") or average)))
    data["per_question"] = [
        {"question_id": item["question_id"], "score": item["score"], "rationale": item["rationale"]}
        for item in answers
    ]
    return data


async def complete_interview(db: Session, user: User, interview_id: int) -> Interview:
    interview = get_owned_interview(db, user, interview_id)
    if interview.status == "completed":
        return interview

    questions = (interview.plan or {}).get("questions") or []
    answers = list(interview.answers or [])
    answer_map = {item["question_id"]: item for item in answers}
    missing = [q["id"] for q in questions if not answer_map.get(q["id"], {}).get("answer")]
    if missing:
        raise InterviewError(f"还有 {len(missing)} 道题未作答，不能生成报告")

    resume = _resume_of(db, user.id)
    if resume is None:
        raise InterviewError("简历不存在")

    job = db.get(Job, interview.job_id)
    if job is None:
        raise InterviewError("岗位不存在")

    answered = [answer_map[q["id"]] for q in questions]
    scored = await _score_answers(job, interview.plan or {}, answered)
    report = await _build_report(job, resume, scored)

    interview.answers = scored
    interview.report = report
    interview.status = "completed"
    db.commit()
    db.refresh(interview)
    return interview


def interview_to_dict(interview: Interview) -> dict:
    job = interview.job
    return {
        "id": interview.id,
        "user_id": interview.user_id,
        "job_id": interview.job_id,
        "job_title": job.title if job else "",
        "company_name": job.company.name if job and job.company else "",
        "application_id": interview.application_id,
        "status": interview.status,
        "plan": interview.plan or {},
        "answers": interview.answers or [],
        "report": interview.report,
        "overall_score": (interview.report or {}).get("overall_score")
        if interview.report
        else None,
        "created_at": interview.created_at,
        "updated_at": interview.updated_at,
    }


def list_my_interviews(db: Session, user: User) -> list[Interview]:
    return list(
        db.scalars(
            select(Interview)
            .where(Interview.user_id == user.id)
            .order_by(Interview.id.desc())
        )
    )


def application_report(db: Session, employer: User, application_id: int) -> Interview | None:
    application = db.get(Application, application_id)
    if application is None:
        raise PermissionError("投递记录不存在或无权查看")
    job = db.get(Job, application.job_id)
    if job is None or job.company is None or job.company.owner_user_id != employer.id:
        raise PermissionError("无权查看该候选人的面试报告")
    return db.scalar(
        select(Interview)
        .where(
            Interview.user_id == application.user_id,
            Interview.job_id == application.job_id,
            Interview.status == "completed",
        )
        .order_by(Interview.id.desc())
    )
