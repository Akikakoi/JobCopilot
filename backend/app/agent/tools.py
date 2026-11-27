"""工具注册器：工具 = 可被 agent 调用的 service 函数，参数走 JSON Schema，权限在工具层收口。"""

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agent import memory as memory_tools
from app.llm.client import chat_completion, message_text
from app.matching import pipeline
from app.matching.rules import score_resume_job
from app.models import Application, Job, Resume, User
from app.services import (
    application_service,
    candidate_service,
    interview_invite_service,
    interview_service,
    job_service,
    onboarding_service,
    offer_service,
    resume_service,
    subscription_service,
)

Handler = Callable[..., Awaitable[Any]]


def obj(properties: dict | None = None, required: list[str] | None = None) -> dict:
    return {"type": "object", "properties": properties or {}, "required": required or []}


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict
    handler: Handler

    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


# ============================== 求职者工具 ==============================


def _my_resume(db: Session, user: User) -> Resume | None:
    return db.scalar(select(Resume).where(Resume.user_id == user.id))


async def _get_my_resume(db: Session, user: User) -> Any:
    resume = _my_resume(db, user)
    if resume is None:
        return {"error": "该用户还没有简历，请引导用户先上传或粘贴简历"}
    return {
        "structured": resume.structured or {},
        "source": resume.source,
        "has_embedding": bool(resume.embedding),
    }


async def _search_jobs(
    db: Session,
    user: User,
    keywords: str | None = None,
    location: str | None = None,
    salary_min: float | None = None,
) -> Any:
    jobs = (
        await job_service.search_jobs(
            db, keywords=keywords, location=location, salary_min=salary_min
        )
    )[:10]
    return {
        "total": len(jobs),
        "jobs": [
            {
                "id": j.id,
                "title": j.title,
                "company": j.company.name if j.company else "",
                "location": j.location,
                "salary": f"{j.salary_min}-{j.salary_max}K",
                "experience": f"{j.experience_min}-{j.experience_max} 年",
                "required_skills": j.required_skills or [],
            }
            for j in jobs
        ],
    }


async def _get_job_detail(db: Session, user: User, job_id: int) -> Any:
    job = job_service.get_job(db, job_id)
    if job is None:
        return {"error": f"岗位 {job_id} 不存在"}
    return job_service.job_to_dict(job)


async def _match_jobs_for_me(db: Session, user: User, top_n: int = 5) -> Any:
    resume = _my_resume(db, user)
    if resume is None or not resume.embedding:
        return {"error": "用户还没有可用简历，请引导用户先上传简历"}
    items = await pipeline.match_jobs_for_resume(db, resume, max_results=top_n, user=user)
    return {
        "jobs": [
            {
                "id": item["id"],
                "title": item["title"],
                "company": item["company_name"],
                "location": item["location"],
                "salary": f"{item['salary_min']}-{item['salary_max']}K",
                "match_score": item["match_score"],
                "similarity": item["similarity"],
                "matched_skills": item["breakdown"]["skills_required"]["matched"],
                "missing_skills": item["breakdown"]["skills_required"]["missing"],
                "experience": item["breakdown"]["experience"],
                "location_score": item["breakdown"]["location"]["score"],
                "salary_score": item["breakdown"]["salary"]["score"],
            }
            for item in items
        ]
    }


async def _suggest_resume_improvements(
    db: Session, user: User, job_id: int | None = None
) -> Any:
    resume = _my_resume(db, user)
    if resume is None:
        return {"error": "用户还没有简历"}
    job: Job | None = None
    if job_id:
        job = job_service.get_job(db, job_id)
    elif resume.embedding:
        matches = await pipeline.match_jobs_for_resume(db, resume, max_results=1, user=user)
        job = job_service.get_job(db, matches[0]["id"]) if matches else None
    if job is None:
        return {"error": "未找到目标岗位"}

    scoring = score_resume_job(resume.structured or {}, job)
    required = job.required_skills or []
    matched = scoring["breakdown"]["skills_required"]["matched"]
    return {
        "target_job": {"id": job.id, "title": job.title, "company": job.company.name if job.company else ""},
        "match_score": scoring["total"],
        "resume_skills": (resume.structured or {}).get("skills") or [],
        "required_skills": required,
        "matched_skills": matched,
        "missing_skills": [s for s in required if s not in matched],
        "experience_requirement": {
            "required_years": job.experience_min,
            "resume_years": scoring["breakdown"]["experience"]["resume_years"],
        },
        "location": scoring["breakdown"]["location"],
        "salary": scoring["breakdown"]["salary"],
    }


async def _get_my_job_intent(db: Session, user: User) -> Any:
    resume = _my_resume(db, user)
    intent = resume_service.job_intent_to_dict(resume)
    if not any(
        [intent["target_title"], intent["categories"], intent["locations"], intent["salary_min"]]
    ):
        return {"intent": intent, "hint": "用户还没有设置求职意向，可以询问目标职位、方向、城市与薪资后调用 update_job_intent"}
    return {"intent": intent}


async def _update_job_intent(
    db: Session,
    user: User,
    target_title: str | None = None,
    categories: list[str] | None = None,
    subcategories: list[str] | None = None,
    locations: list[str] | None = None,
    districts: dict[str, list[str]] | None = None,
    salary_min: float | None = None,
    salary_max: float | None = None,
    job_types: list[str] | None = None,
) -> Any:
    """更新求职意向（岗位定位）。只传需要修改的字段，其余保持原值。"""
    current = resume_service.job_intent_to_dict(_my_resume(db, user))
    resume = await resume_service.save_job_intent(
        db,
        user.id,
        target_title=(
            target_title if target_title is not None else current["target_title"]
        ),
        categories=categories if categories is not None else current["categories"],
        subcategories=subcategories if subcategories is not None else current["subcategories"],
        locations=locations if locations is not None else current["locations"],
        districts=districts if districts is not None else current.get("districts") or {},
        salary_min=salary_min if salary_min is not None else current["salary_min"],
        salary_max=salary_max if salary_max is not None else current["salary_max"],
        job_types=job_types if job_types is not None else current["job_types"],
    )
    return {"saved": True, "intent": resume_service.job_intent_to_dict(resume)}


async def _diagnose_job_fit(
    db: Session,
    user: User,
    category: str | None = None,
    subcategory: str | None = None,
) -> Any:
    try:
        return await resume_service.diagnose_job_fit(
            db, user.id, category=category, subcategory=subcategory
        )
    except ValueError as exc:
        return {"error": str(exc)}


async def _apply_to_job(
    db: Session, user: User, job_id: int, cover_letter: str = ""
) -> Any:
    try:
        application = application_service.apply_to_job(db, user, job_id, cover_letter)
    except ValueError as exc:
        return {"error": str(exc)}
    return {
        "application_id": application.id,
        "job_id": application.job_id,
        "match_score": application.match_score,
        "status": application.status,
        "message": "投递成功",
    }


async def _get_my_applications(db: Session, user: User) -> Any:
    apps = application_service.list_my_applications(db, user)
    return {
        "total": len(apps),
        "applications": [
            {
                "id": a.id,
                "job_id": a.job_id,
                "job_title": a.job.title if a.job else "",
                "company": a.job.company.name if a.job and a.job.company else "",
                "status": a.status,
                "status_label": application_service.STATUS_LABELS.get(a.status, a.status),
                "match_score": a.match_score,
                "created_at": str(a.created_at),
            }
            for a in apps
        ],
    }


async def _start_mock_interview(db: Session, user: User, job_id: int | None = None) -> Any:
    job: Job | None = None
    if job_id:
        job = job_service.get_job(db, job_id)
    else:
        resume = _my_resume(db, user)
        if resume and resume.embedding:
            matches = await pipeline.match_jobs_for_resume(db, resume, max_results=1, user=user)
            job = job_service.get_job(db, matches[0]["id"]) if matches else None
    if job is None:
        return {"error": "未找到可用于模拟面试的目标岗位"}
    return {
        "job": {
            "id": job.id,
            "title": job.title,
            "description": job.description,
            "required_skills": job.required_skills or [],
        },
        "instruction": "请以面试官身份开始模拟面试：先简短自我介绍，再每次只提一个问题，根据回答追问，共 3-5 轮。",
    }


async def _create_mock_interview(db: Session, user: User, job_id: int) -> Any:
    try:
        interview = await interview_service.create_interview(db, user, job_id)
    except interview_service.InterviewError as exc:
        return {"error": str(exc)}
    questions = (interview.plan or {}).get("questions") or []
    return {
        "interview_id": interview.id,
        "job": {
            "id": interview.job_id,
            "title": interview.job.title if interview.job else "",
        },
        "total_questions": len(questions),
        "first_question": questions[0] if questions else None,
        "instruction": "先向用户提出第一题；用户回答后调用 submit_interview_answer；全部答完后调用 get_interview_report。",
    }


async def _submit_interview_answer(
    db: Session, user: User, interview_id: int, answer: str
) -> Any:
    try:
        interview = interview_service.get_owned_interview(db, user, interview_id)
    except PermissionError as exc:
        return {"error": str(exc)}

    questions = (interview.plan or {}).get("questions") or []
    answered_ids = {item["question_id"] for item in interview.answers or []}
    current = next((item for item in questions if item["id"] not in answered_ids), None)
    if current is None:
        return {"error": "所有题目已作答，请调用 get_interview_report 生成报告"}

    try:
        updated = interview_service.submit_answer(
            db, user, interview_id, current["id"], answer
        )
    except interview_service.InterviewError as exc:
        return {"error": str(exc)}

    remaining_ids = {item["question_id"] for item in updated.answers or []}
    remaining = [item for item in questions if item["id"] not in remaining_ids]
    return {
        "interview_id": interview_id,
        "submitted_question": current["id"],
        "answered": len(updated.answers or []),
        "total": len(questions),
        "next_question": remaining[0] if remaining else None,
        "all_answered": not remaining,
    }


async def _get_interview_report(db: Session, user: User, interview_id: int) -> Any:
    try:
        interview = interview_service.get_owned_interview(db, user, interview_id)
    except PermissionError as exc:
        return {"error": str(exc)}

    if interview.status != "completed":
        try:
            interview = await interview_service.complete_interview(db, user, interview_id)
        except interview_service.InterviewError as exc:
            return {"error": str(exc)}

    report = interview.report or {}
    return {
        "interview_id": interview.id,
        "status": interview.status,
        "overall_score": report.get("overall_score"),
        "dimensions": report.get("dimensions", {}),
        "summary": report.get("summary", ""),
        "strengths": report.get("strengths", []),
        "risks": report.get("risks", []),
        "suggestions": report.get("suggestions", []),
    }


async def _create_subscription(
    db: Session,
    user: User,
    keywords: str = "",
    location: str = "",
    salary_min: float | None = None,
    skills: list[str] | None = None,
    match_score_min: float | None = None,
    name: str = "我的岗位订阅",
) -> Any:
    filters = {
        "keywords": (keywords or "").strip(),
        "location": (location or "").strip(),
        "salary_min": salary_min,
        "skills": [item.strip() for item in (skills or []) if item and item.strip()],
        "match_score_min": match_score_min,
    }
    try:
        subscription = subscription_service.create_subscription(
            db, user, name or "我的岗位订阅", filters, True
        )
    except subscription_service.SubscriptionError as exc:
        return {"error": str(exc)}
    return {
        "subscription_id": subscription.id,
        "name": subscription.name,
        "filters": filters,
        "message": "订阅已创建，新发布的匹配岗位会进入站内通知",
    }


async def _list_unread_notifications(db: Session, user: User) -> Any:
    items, unread = subscription_service.list_notifications(
        db, user, unread_only=True, limit=10
    )
    return {
        "unread": unread,
        "notifications": [
            {
                "id": item.id,
                "title": item.title,
                "job_id": (item.payload or {}).get("job_id"),
                "match_score": (item.payload or {}).get("match_score"),
            }
            for item in items
        ],
    }


async def _save_memory(db: Session, user: User, content: str) -> Any:
    return await memory_tools.save_memory(db, user.id, content)


async def _search_memory(db: Session, user: User, query: str) -> Any:
    return {"memories": await memory_tools.search_memory(db, user.id, query)}


# ============================== 招聘方工具 ==============================

JD_SYSTEM = """你是招聘 JD 撰写专家。根据招聘需求生成结构化 JD 草稿，只输出 JSON：
{
  "title": "岗位标题",
  "description": "岗位描述，包含职责与要求，150-300 字",
  "required_skills": ["必需技能"],
  "preferred_skills": ["加分技能"],
  "experience_min": 3,
  "experience_max": 5,
  "location": "上海",
  "salary_min": 25,
  "salary_max": 35
}
薪资单位 K/月。信息不足时给出合理默认值，不要输出 JSON 以外的内容。"""


async def _generate_job_description(db: Session, user: User, requirements: str) -> Any:
    reply = await chat_completion(
        [
            {"role": "system", "content": JD_SYSTEM},
            {"role": "user", "content": requirements},
        ],
        temperature=0.4,
        response_format={"type": "json_object"},
    )
    try:
        return json.loads(message_text(reply.get("content")) or "{}")
    except json.JSONDecodeError:
        return {"error": "JD 生成失败，请重试"}


async def _create_job(db: Session, user: User, **fields) -> Any:
    try:
        job = job_service.create_job(db, user, fields)
    except Exception as exc:  # noqa: BLE001
        return {"error": f"发布失败：{exc}"}
    return {"job_id": job.id, "title": job.title, "status": job.status, "message": "岗位已发布"}


async def _update_job(db: Session, user: User, job_id: int, **fields) -> Any:
    try:
        job = job_service.update_job(db, user, job_id, {k: v for k, v in fields.items() if v is not None})
    except PermissionError as exc:
        return {"error": str(exc)}
    return {"job_id": job.id, "title": job.title, "message": "岗位已更新"}


async def _list_my_jobs(db: Session, user: User) -> Any:
    jobs = job_service.list_my_jobs(db, user)
    items = []
    for job in jobs:
        count = db.scalar(select(func.count(Application.id)).where(Application.job_id == job.id))
        items.append(
            {
                "id": job.id,
                "title": job.title,
                "location": job.location,
                "salary": f"{job.salary_min}-{job.salary_max}K",
                "status": job.status,
                "applicant_count": int(count or 0),
            }
        )
    return {"total": len(items), "jobs": items}


async def _list_candidates(db: Session, user: User, job_id: int) -> Any:
    try:
        items = await candidate_service.rank_candidates(db, user, job_id)
    except PermissionError as exc:
        return {"error": str(exc)}
    return {
        "job_id": job_id,
        "candidates": [
            {
                "application_id": item["application_id"],
                "name": item["candidate_name"],
                "match_score": item["match_score"],
                "status": item["status"],
                "years": (item["structured"].get("years_of_experience") or 0),
                "skills": (item["structured"].get("skills") or [])[:12],
                "missing_skills": item["breakdown"]["skills_required"]["missing"],
                "offer_status": (item.get("offer") or {}).get("status"),
                "onboarding": item.get("onboarding"),
                "next_step": _onboarding_next_step(item["status"], bool(item.get("onboarding", {}).get("confirmed")), employer=True),
                "latest_interview": (
                    {
                        "invite_id": item["interview_invites"][-1]["id"],
                        "round": item["interview_invites"][-1]["round"],
                        "status": item["interview_invites"][-1]["status"],
                        "scheduled_at": item["interview_invites"][-1]["scheduled_at"],
                    }
                    if item.get("interview_invites")
                    else None
                ),
            }
            for item in items
        ],
    }


async def _screen_candidate(db: Session, user: User, application_id: int) -> Any:
    application = db.get(Application, application_id)
    if application is None:
        return {"error": "投递记录不存在"}
    job = db.get(Job, application.job_id)
    if job is None or job.company is None or job.company.owner_user_id != user.id:
        return {"error": "无权评估该投递"}
    resume = db.get(Resume, application.resume_id)
    if resume is None:
        return {"error": "候选人简历缺失"}

    scoring = score_resume_job(resume.structured or {}, job)
    explanation = await pipeline.get_cached_explanation(db, resume, job, scoring)
    application.match_score = scoring["total"]
    application.match_explanation = explanation
    db.commit()
    return {
        "application_id": application.id,
        "candidate": resume.structured or {},
        "job": {"id": job.id, "title": job.title, "required_skills": job.required_skills or []},
        "match_score": scoring["total"],
        "breakdown": scoring["breakdown"],
        "evaluation": explanation,
    }


async def _rank_candidates(db: Session, user: User, job_id: int) -> Any:
    try:
        items = await candidate_service.rank_candidates(db, user, job_id)
    except PermissionError as exc:
        return {"error": str(exc)}
    return {
        "job_id": job_id,
        "ranking": [
            {
                "rank": index + 1,
                "application_id": item["application_id"],
                "name": item["candidate_name"],
                "match_score": item["match_score"],
                "status": item["status"],
                "summary": (item.get("match_explanation") or {}).get("summary", ""),
            }
            for index, item in enumerate(items)
        ],
    }


async def _update_application_status(
    db: Session, user: User, application_id: int, status: str, note: str = ""
) -> Any:
    try:
        application = application_service.update_status(db, user, application_id, status, note)
    except (ValueError, PermissionError) as exc:
        return {"error": str(exc)}
    return {
        "application_id": application.id,
        "status": application.status,
        "status_label": application_service.STATUS_LABELS.get(application.status, application.status),
        "message": "状态已更新",
    }


async def _get_candidate_interview_report(
    db: Session, user: User, application_id: int
) -> Any:
    try:
        interview = interview_service.application_report(db, user, application_id)
    except PermissionError as exc:
        return {"error": str(exc)}
    if interview is None:
        return {"error": "该候选人还没有完成 AI 模拟面试"}

    report = interview.report or {}
    return {
        "application_id": application_id,
        "interview_id": interview.id,
        "job_title": interview.job.title if interview.job else "",
        "overall_score": report.get("overall_score"),
        "dimensions": report.get("dimensions", {}),
        "summary": report.get("summary", ""),
        "strengths": report.get("strengths", []),
        "risks": report.get("risks", []),
        "suggestions": report.get("suggestions", []),
    }


def _parse_tool_datetime(value: str) -> datetime:
    text = (value or "").strip()
    if not text:
        raise ValueError("时间不能为空，请使用 ISO 格式，如 2030-01-01T10:00")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("时间格式不正确，请使用 ISO 格式，如 2030-01-01T10:00") from exc
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _offer_summary(offer: dict | None) -> dict | None:
    if not offer:
        return None
    return {
        "offer_id": offer["id"],
        "salary_min": offer["salary_min"],
        "salary_max": offer["salary_max"],
        "start_date": offer["start_date"],
        "expires_at": offer["expires_at"],
        "status": offer["status"],
        "status_label": offer["status_label"],
        "note": offer["note"],
        "response_note": offer["response_note"],
    }


def _onboarding_next_step(status: str, confirmed: bool, employer: bool = False) -> str:
    if status == "onboarding":
        if employer:
            return "记录实际到岗结果" if confirmed else "等待候选人确认入职"
        return "等待招聘方记录到岗结果" if confirmed else "确认入职安排"
    if status == "hired":
        return "已完成入职"
    if status == "abandoned":
        return "已放弃入职"
    return ""


def _invite_summary(invite: dict) -> dict:
    return {
        "invite_id": invite["id"],
        "round": invite["round"],
        "scheduled_at": invite["scheduled_at"],
        "duration_minutes": invite["duration_minutes"],
        "mode": invite["mode"],
        "mode_label": invite["mode_label"],
        "location": invite["location"],
        "note": invite["note"],
        "status": invite["status"],
        "status_label": invite["status_label"],
        "candidate_note": invite["candidate_note"],
    }


async def _list_my_pipeline(db: Session, user: User) -> Any:
    applications = application_service.list_my_applications(db, user)
    app_ids = [item.id for item in applications]
    offers = offer_service.group_offers(db, app_ids)
    invites = interview_invite_service.group_invites(db, app_ids)
    items = []
    for application in applications:
        job = application.job
        items.append(
            {
                "application_id": application.id,
                "job_id": application.job_id,
                "job_title": job.title if job else "",
                "company": job.company.name if job and job.company else "",
                "status": application.status,
                "status_label": application_service.STATUS_LABELS.get(
                    application.status, application.status
                ),
                "offer": _offer_summary(offers.get(application.id)),
                "onboarding": application_service.onboarding_to_dict(application),
                "next_step": _onboarding_next_step(
                    application.status,
                    application.onboarding_confirmed_at is not None,
                ),
                "interview_invites": [
                    _invite_summary(item)
                    for item in invites.get(application.id, [])
                ],
            }
        )
    return {"total": len(items), "applications": items}


async def _respond_interview_invite(
    db: Session,
    user: User,
    application_id: int,
    invite_id: int,
    action: str,
    note: str = "",
) -> Any:
    if action not in ("confirm", "decline"):
        return {"error": "action 只能是 confirm 或 decline"}
    try:
        invite = interview_invite_service.respond_invite(
            db, user, application_id, invite_id, action, note
        )
    except (ValueError, PermissionError) as exc:
        return {"error": str(exc)}
    return {
        **_invite_summary(interview_invite_service.invite_to_dict(invite)),
        "message": "已确认面试" if action == "confirm" else "已拒绝面试邀约",
    }


async def _respond_offer(
    db: Session, user: User, application_id: int, action: str, note: str = ""
) -> Any:
    if action not in ("accept", "decline"):
        return {"error": "action 只能是 accept 或 decline"}
    try:
        offer = offer_service.respond_offer(db, user, application_id, action, note)
    except (ValueError, PermissionError) as exc:
        return {"error": str(exc)}
    return {
        **_offer_summary(offer_service.offer_to_dict(offer)),
        "message": "已接受 Offer" if action == "accept" else "已拒绝 Offer",
    }


async def _confirm_onboarding(
    db: Session, user: User, application_id: int, note: str = ""
) -> Any:
    try:
        application = onboarding_service.confirm_onboarding(
            db, user, application_id, note
        )
    except (ValueError, PermissionError) as exc:
        return {"error": str(exc)}
    return {
        "application_id": application.id,
        "status": application.status,
        "status_label": application_service.STATUS_LABELS.get(
            application.status, application.status
        ),
        "onboarding": application_service.onboarding_to_dict(application),
        "message": "已确认入职安排",
    }


async def _abandon_onboarding(
    db: Session, user: User, application_id: int, note: str = ""
) -> Any:
    try:
        application = onboarding_service.abandon_onboarding(
            db, user, application_id, note
        )
    except (ValueError, PermissionError) as exc:
        return {"error": str(exc)}
    return {
        "application_id": application.id,
        "status": application.status,
        "status_label": application_service.STATUS_LABELS.get(
            application.status, application.status
        ),
        "onboarding": application_service.onboarding_to_dict(application),
        "message": "已放弃入职",
    }


async def _record_onboarding_result(
    db: Session,
    user: User,
    application_id: int,
    result: str,
    note: str = "",
    onboarding_date: str = "",
) -> Any:
    try:
        application = onboarding_service.record_onboarding_result(
            db, user, application_id, result, note, onboarding_date
        )
    except (ValueError, PermissionError) as exc:
        return {"error": str(exc)}
    return {
        "application_id": application.id,
        "status": application.status,
        "status_label": application_service.STATUS_LABELS.get(
            application.status, application.status
        ),
        "onboarding": application_service.onboarding_to_dict(application),
        "message": "入职结果已记录",
    }


async def _create_interview_invite(
    db: Session,
    user: User,
    application_id: int,
    scheduled_at: str,
    duration_minutes: int = 45,
    mode: str = "video",
    location: str = "",
    note: str = "",
) -> Any:
    try:
        scheduled = _parse_tool_datetime(scheduled_at)
        invite = interview_invite_service.create_invite(
            db,
            user,
            application_id,
            {
                "scheduled_at": scheduled,
                "duration_minutes": duration_minutes,
                "mode": mode,
                "location": location,
                "note": note,
            },
        )
    except (ValueError, PermissionError) as exc:
        return {"error": str(exc)}
    return {
        **_invite_summary(interview_invite_service.invite_to_dict(invite)),
        "message": "面试邀约已发送，候选人会收到站内通知",
    }


async def _cancel_interview_invite(
    db: Session, user: User, application_id: int, invite_id: int, note: str = ""
) -> Any:
    try:
        invite = interview_invite_service.cancel_invite(
            db, user, application_id, invite_id, note
        )
    except (ValueError, PermissionError) as exc:
        return {"error": str(exc)}
    return {
        **_invite_summary(interview_invite_service.invite_to_dict(invite)),
        "message": "面试邀约已取消",
    }


async def _complete_interview_invite(
    db: Session, user: User, application_id: int, invite_id: int, note: str = ""
) -> Any:
    try:
        invite = interview_invite_service.complete_invite(
            db, user, application_id, invite_id, note
        )
    except (ValueError, PermissionError) as exc:
        return {"error": str(exc)}
    return {
        **_invite_summary(interview_invite_service.invite_to_dict(invite)),
        "message": "面试已标记完成",
    }


async def _create_offer(
    db: Session,
    user: User,
    application_id: int,
    salary_min: float = 0,
    salary_max: float = 0,
    start_date: str = "",
    expires_at: str | None = None,
    note: str = "",
) -> Any:
    try:
        expires = _parse_tool_datetime(expires_at) if expires_at else None
        offer = offer_service.create_offer(
            db,
            user,
            application_id,
            {
                "salary_min": salary_min,
                "salary_max": salary_max,
                "start_date": start_date,
                "expires_at": expires,
                "note": note,
            },
        )
    except (ValueError, PermissionError) as exc:
        return {"error": str(exc)}
    return {
        **_offer_summary(offer_service.offer_to_dict(offer)),
        "message": "Offer 已发送，候选人会收到站内通知",
    }


# ============================== 注册表 ==============================

SEEKER_TOOLS: list[Tool] = [
    Tool("get_my_resume", "读取当前用户的结构化简历", obj(), _get_my_resume),
    Tool(
        "search_jobs",
        "按关键词/城市/最低薪资检索在招岗位（关键词支持语义匹配）",
        obj(
            {
                "keywords": {"type": "string", "description": "关键词，如 Python 后端"},
                "location": {"type": "string", "description": "城市，如 上海"},
                "salary_min": {"type": "number", "description": "期望最低月薪，单位 K"},
            }
        ),
        _search_jobs,
    ),
    Tool(
        "get_job_detail",
        "获取单个岗位详情",
        obj({"job_id": {"type": "integer"}}, ["job_id"]),
        _get_job_detail,
    ),
    Tool(
        "match_jobs_for_me",
        "对当前用户简历跑匹配管线，返回 Top 岗位、匹配分与缺口",
        obj({"top_n": {"type": "integer", "description": "返回数量，默认 5"}}),
        _match_jobs_for_me,
    ),
    Tool(
        "suggest_resume_improvements",
        "针对目标岗位给出简历差距数据（缺失技能、年限、地点、薪资）",
        obj({"job_id": {"type": "integer", "description": "目标岗位 id，缺省则用最佳匹配岗位"}}),
        _suggest_resume_improvements,
    ),
    Tool(
        "get_my_job_intent",
        "读取当前用户的求职意向（目标职位、方向、城市、薪资）",
        obj(),
        _get_my_job_intent,
    ),
    Tool(
        "update_job_intent",
        "更新求职意向（岗位定位），保存后会影响岗位推荐与匹配排序。只传需要修改的字段",
        obj(
            {
                "target_title": {"type": "string", "description": "目标职位，如 后端开发工程师"},
                "categories": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "岗位类别，可选：技术研发/产品与项目/设计/运营/市场与销售/职能支持/生活服务",
                },
                "subcategories": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "二级方向，如 后端开发、算法与人工智能",
                },
                "locations": {"type": "array", "items": {"type": "string"}, "description": "期望城市"},
                "districts": {
                    "type": "object",
                    "description": "期望区域，城市到区的映射，如 {\"上海\": [\"徐汇区\", \"闵行区\"]}",
                    "additionalProperties": {"type": "array", "items": {"type": "string"}},
                },
                "salary_min": {"type": "number", "description": "期望最低月薪（K）"},
                "salary_max": {"type": "number", "description": "期望最高月薪（K）"},
                "job_types": {"type": "array", "items": {"type": "string"}, "description": "全职/实习"},
            }
        ),
        _update_job_intent,
    ),
    Tool(
        "diagnose_job_fit",
        "岗位定位诊断：基于简历判断适合哪些岗位方向、匹配度、差距与下一步建议",
        obj(
            {
                "category": {"type": "string", "description": "重点关注的技术类别，可选"},
                "subcategory": {"type": "string", "description": "重点关注的二级方向，可选"},
            }
        ),
        _diagnose_job_fit,
    ),
    Tool(
        "apply_to_job",
        "投递岗位（调用前必须获得用户确认）",
        obj(
            {
                "job_id": {"type": "integer"},
                "cover_letter": {"type": "string", "description": "求职信正文"},
            },
            ["job_id"],
        ),
        _apply_to_job,
    ),
    Tool("get_my_applications", "查看当前用户的投递记录与状态", obj(), _get_my_applications),
    Tool(
        "start_mock_interview",
        "准备基于目标岗位的模拟面试上下文",
        obj({"job_id": {"type": "integer"}}),
        _start_mock_interview,
    ),
    Tool(
        "create_mock_interview",
        "针对岗位生成结构化模拟面试（6 道题，含技术/项目/行为），返回第一题",
        obj({"job_id": {"type": "integer"}}, ["job_id"]),
        _create_mock_interview,
    ),
    Tool(
        "submit_interview_answer",
        "提交当前题目的回答，自动推进到下一道未答题",
        obj(
            {
                "interview_id": {"type": "integer"},
                "answer": {"type": "string", "description": "用户对当前题目的回答原文"},
            },
            ["interview_id", "answer"],
        ),
        _submit_interview_answer,
    ),
    Tool(
        "get_interview_report",
        "生成或读取结构化面试报告（全部题目作答后可用）",
        obj({"interview_id": {"type": "integer"}}, ["interview_id"]),
        _get_interview_report,
    ),
    Tool(
        "create_subscription",
        "创建岗位订阅（至少需提供关键词/城市/最低月薪/技能/最低匹配分中的一个条件），新发布的匹配岗位会进入站内通知",
        obj(
            {
                "keywords": {"type": "string"},
                "location": {"type": "string"},
                "salary_min": {"type": "number", "description": "最低月薪，单位 K"},
                "skills": {"type": "array", "items": {"type": "string"}},
                "match_score_min": {"type": "number", "description": "最低匹配分 0-100"},
                "name": {"type": "string"},
            }
        ),
        _create_subscription,
    ),
    Tool(
        "list_unread_notifications",
        "查看当前用户的未读站内通知（新岗位推荐）",
        obj(),
        _list_unread_notifications,
    ),
    Tool(
        "list_my_pipeline",
        "查看我的投递及其面试邀约、Offer 状态（含后续操作用的 id）",
        obj(),
        _list_my_pipeline,
    ),
    Tool(
        "respond_interview_invite",
        "确认或拒绝面试邀约；必须由用户明确决定后才能调用",
        obj(
            {
                "application_id": {"type": "integer"},
                "invite_id": {"type": "integer"},
                "action": {"type": "string", "enum": ["confirm", "decline"]},
                "note": {"type": "string", "description": "给招聘方的备注，如时间冲突原因"},
            },
            ["application_id", "invite_id", "action"],
        ),
        _respond_interview_invite,
    ),
    Tool(
        "respond_offer",
        "接受或拒绝 Offer；必须由用户明确决定后才能调用，不可代为同意",
        obj(
            {
                "application_id": {"type": "integer"},
                "action": {"type": "string", "enum": ["accept", "decline"]},
                "note": {"type": "string"},
            },
            ["application_id", "action"],
        ),
        _respond_offer,
    ),
    Tool(
        "confirm_onboarding",
        "确认入职安排（Offer 接受后进入待入职）；必须由用户明确表态后调用",
        obj(
            {
                "application_id": {"type": "integer"},
                "note": {"type": "string", "description": "给招聘方的备注，如到岗时间说明"},
            },
            ["application_id"],
        ),
        _confirm_onboarding,
    ),
    Tool(
        "abandon_onboarding",
        "放弃入职（待入职阶段）；必须由用户明确决定后调用，调用后投递结束",
        obj(
            {
                "application_id": {"type": "integer"},
                "note": {"type": "string", "description": "放弃原因"},
            },
            ["application_id"],
        ),
        _abandon_onboarding,
    ),
    Tool(
        "save_memory",
        "保存对用户的长期认知（偏好城市/薪资/方向/性格等）",
        obj({"content": {"type": "string"}}, ["content"]),
        _save_memory,
    ),
    Tool(
        "search_memory",
        "按语义检索该用户的长期记忆",
        obj({"query": {"type": "string"}}, ["query"]),
        _search_memory,
    ),
]

EMPLOYER_TOOLS: list[Tool] = [
    Tool(
        "generate_job_description",
        "根据招聘需求生成结构化 JD 草稿（不直接发布）",
        obj({"requirements": {"type": "string"}}, ["requirements"]),
        _generate_job_description,
    ),
    Tool(
        "create_job",
        "发布岗位（调用前必须获得用户确认）",
        obj(
            {
                "title": {"type": "string"},
                "description": {"type": "string"},
                "required_skills": {"type": "array", "items": {"type": "string"}},
                "preferred_skills": {"type": "array", "items": {"type": "string"}},
                "experience_min": {"type": "integer"},
                "experience_max": {"type": "integer"},
                "location": {"type": "string"},
                "salary_min": {"type": "number"},
                "salary_max": {"type": "number"},
            },
            ["title"],
        ),
        _create_job,
    ),
    Tool(
        "update_job",
        "更新本公司的岗位",
        obj(
            {
                "job_id": {"type": "integer"},
                "title": {"type": "string"},
                "description": {"type": "string"},
                "required_skills": {"type": "array", "items": {"type": "string"}},
                "preferred_skills": {"type": "array", "items": {"type": "string"}},
                "location": {"type": "string"},
                "salary_min": {"type": "number"},
                "salary_max": {"type": "number"},
                "status": {"type": "string", "enum": ["open", "closed"]},
            },
            ["job_id"],
        ),
        _update_job,
    ),
    Tool("list_my_jobs", "列出本公司在招岗位及投递数量", obj(), _list_my_jobs),
    Tool(
        "list_candidates",
        "列出某岗位的候选人及匹配分",
        obj({"job_id": {"type": "integer"}}, ["job_id"]),
        _list_candidates,
    ),
    Tool(
        "screen_candidate",
        "对单份投递做深度评估（技能/年限/地点/薪资 + 解读）",
        obj({"application_id": {"type": "integer"}}, ["application_id"]),
        _screen_candidate,
    ),
    Tool(
        "rank_candidates",
        "对某岗位候选人排序并给出理由摘要",
        obj({"job_id": {"type": "integer"}}, ["job_id"]),
        _rank_candidates,
    ),
    Tool(
        "update_application_status",
        "推进候选人流程状态",
        obj(
            {
                "application_id": {"type": "integer"},
                "status": {
                    "type": "string",
                    "enum": ["submitted", "screening", "interview", "rejected"],
                },
                "note": {"type": "string"},
            },
            ["application_id", "status"],
        ),
        _update_application_status,
    ),
    Tool(
        "get_candidate_interview_report",
        "查看候选人已完成的结构化模拟面试报告",
        obj({"application_id": {"type": "integer"}}, ["application_id"]),
        _get_candidate_interview_report,
    ),
    Tool(
        "create_interview_invite",
        "给候选人发送面试邀约；调用前先与用户确认时间、方式和地点，发送后会推进投递到面试中",
        obj(
            {
                "application_id": {"type": "integer"},
                "scheduled_at": {
                    "type": "string",
                    "description": "面试时间，ISO 格式，如 2030-01-01T10:00",
                },
                "duration_minutes": {"type": "integer", "description": "时长，默认 45 分钟"},
                "mode": {"type": "string", "enum": ["video", "onsite", "phone"]},
                "location": {"type": "string", "description": "会议链接或现场地址"},
                "note": {"type": "string", "description": "面试官、准备材料等说明"},
            },
            ["application_id", "scheduled_at"],
        ),
        _create_interview_invite,
    ),
    Tool(
        "cancel_interview_invite",
        "取消已发出的面试邀约（需用户确认）",
        obj(
            {
                "application_id": {"type": "integer"},
                "invite_id": {"type": "integer"},
                "note": {"type": "string", "description": "取消原因"},
            },
            ["application_id", "invite_id"],
        ),
        _cancel_interview_invite,
    ),
    Tool(
        "complete_interview_invite",
        "把已进行的面试标记为完成（面试结束后使用）",
        obj(
            {
                "application_id": {"type": "integer"},
                "invite_id": {"type": "integer"},
                "note": {"type": "string", "description": "面试结果或补充说明"},
            },
            ["application_id", "invite_id"],
        ),
        _complete_interview_invite,
    ),
    Tool(
        "create_offer",
        "给候选人发送 Offer；调用前必须获得用户对薪资、入职时间与有效期的确认",
        obj(
            {
                "application_id": {"type": "integer"},
                "salary_min": {"type": "number", "description": "最低月薪，单位 K"},
                "salary_max": {"type": "number", "description": "最高月薪，单位 K"},
                "start_date": {"type": "string", "description": "入职日期，如 2030-02-01"},
                "expires_at": {
                    "type": "string",
                    "description": "Offer 有效期，ISO 格式，如 2030-01-10T23:59:59",
                },
                "note": {"type": "string"},
            },
            ["application_id", "salary_min", "salary_max"],
        ),
        _create_offer,
    ),
    Tool(
        "record_onboarding_result",
        "记录候选人实际到岗结果（已入职 / 放弃入职），需用户确认后调用",
        obj(
            {
                "application_id": {"type": "integer"},
                "result": {"type": "string", "enum": ["hired", "abandoned"]},
                "note": {"type": "string", "description": "到岗情况说明"},
                "onboarding_date": {
                    "type": "string",
                    "description": "实际入职日期，如 2030-02-03；不填沿用 Offer 入职日期",
                },
            },
            ["application_id", "result"],
        ),
        _record_onboarding_result,
    ),
    Tool(
        "save_memory",
        "保存对公司的长期认知（招聘偏好等）",
        obj({"content": {"type": "string"}}, ["content"]),
        _save_memory,
    ),
    Tool(
        "search_memory",
        "按语义检索该用户的长期记忆",
        obj({"query": {"type": "string"}}, ["query"]),
        _search_memory,
    ),
]

TOOLSETS: dict[str, list[Tool]] = {"seeker": SEEKER_TOOLS, "employer": EMPLOYER_TOOLS}


def tool_schemas(agent_type: str) -> list[dict]:
    return [tool.schema() for tool in TOOLSETS[agent_type]]


def get_tool(agent_type: str, name: str) -> Tool | None:
    return next((tool for tool in TOOLSETS[agent_type] if tool.name == name), None)
