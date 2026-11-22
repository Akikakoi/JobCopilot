from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.matching.rules import score_resume_job
from app.models import (
    Application,
    ApplicationEvent,
    Job,
    Notification,
    Resume,
    ResumeFile,
    User,
)
from app.services import message_service
from app.services.notification_service import notify_once

VALID_STATUSES = {
    "submitted",
    "screening",
    "interview",
    "offer",
    "onboarding",
    "hired",
    "abandoned",
    "rejected",
}
# 招聘方拖拽只推进招聘阶段；入职阶段由候选人与招聘方的入职动作驱动
STAGE_ORDER = ["submitted", "screening", "interview", "offer"]
TERMINAL_STATUSES = {"offer", "rejected", "onboarding", "hired", "abandoned"}


def _transition_allowed(current: str, target: str) -> bool:
    if current == target:
        return True
    if current in TERMINAL_STATUSES:
        return False
    if target == "rejected":
        return True
    if target not in STAGE_ORDER:
        return False
    return STAGE_ORDER.index(target) > STAGE_ORDER.index(current)


STATUS_LABELS = {
    "submitted": "已投递",
    "screening": "筛选中",
    "interview": "面试中",
    "offer": "已录用",
    "onboarding": "待入职",
    "hired": "已入职",
    "abandoned": "放弃入职",
    "rejected": "未通过",
}

ONBOARDING_RESULT_LABELS = {
    "": "待确认",
    "hired": "已入职",
    "abandoned": "放弃入职",
}


def onboarding_to_dict(application: Application) -> dict:
    result = application.onboarding_result or ""
    return {
        "date": application.onboarding_date or "",
        "confirmed": application.onboarding_confirmed_at is not None,
        "confirmed_at": application.onboarding_confirmed_at,
        "result": result,
        "result_label": ONBOARDING_RESULT_LABELS.get(result, result),
        "result_at": application.onboarding_result_at,
        "note": application.onboarding_note or "",
    }


def event_to_dict(event: ApplicationEvent) -> dict:
    return {
        "id": event.id,
        "application_id": event.application_id,
        "from_status": event.from_status,
        "from_status_label": STATUS_LABELS.get(event.from_status, event.from_status),
        "to_status": event.to_status,
        "to_status_label": STATUS_LABELS.get(event.to_status, event.to_status),
        "note": event.note or "",
        "created_at": event.created_at,
    }


def application_to_dict(
    app: Application,
    events: list[ApplicationEvent] | None = None,
    offer: dict | None = None,
    invites: list[dict] | None = None,
) -> dict:
    job = app.job if hasattr(app, "job") else None
    return {
        "id": app.id,
        "job_id": app.job_id,
        "job_title": job.title if job else "",
        "company_name": job.company.name if job and job.company else "",
        "resume_id": app.resume_id,
        "user_id": app.user_id,
        "status": app.status,
        "status_label": STATUS_LABELS.get(app.status, app.status),
        "status_note": app.status_note or "",
        "match_score": app.match_score,
        "match_explanation": app.match_explanation,
        "cover_letter": app.cover_letter,
        "offer": offer,
        "onboarding": onboarding_to_dict(app),
        "interview_invites": invites or [],
        "events": [event_to_dict(item) for item in (events or [])],
        "created_at": app.created_at,
        "updated_at": app.updated_at,
    }


def get_resume(db: Session, user: User) -> Resume | None:
    return db.scalar(select(Resume).where(Resume.user_id == user.id))


def apply_to_job(
    db: Session, user: User, job_id: int, cover_letter: str = "", resume_id: int | None = None
) -> Application:
    job = db.get(Job, job_id)
    if job is None or job.status != "open":
        raise ValueError("岗位不存在或已下线")

    resume = db.get(Resume, resume_id) if resume_id else get_resume(db, user)
    if resume is None or resume.user_id != user.id:
        raise ValueError("请先创建简历再投递")

    exists = db.scalar(
        select(Application).where(Application.user_id == user.id, Application.job_id == job_id)
    )
    if exists:
        raise ValueError("你已经投递过该岗位")

    scoring = score_resume_job(resume.structured or {}, job)
    application = Application(
        job_id=job_id,
        resume_id=resume.id,
        user_id=user.id,
        cover_letter=cover_letter,
        match_score=scoring["total"],
    )
    db.add(application)
    try:
        db.flush()
        company = job.company
        try:
            message_service.ensure_conversation(db, application)
        except message_service.MessageError:
            pass  # 会话创建失败不影响投递本身
        if company is not None:
            candidate_name = (
                (resume.structured or {}).get("name")
                or user.display_name
                or user.username
            )
            db.add(
                Notification(
                    user_id=company.owner_user_id,
                    type="new_application",
                    title=f"收到新投递：{job.title} · {candidate_name}",
                    payload={
                        "application_id": application.id,
                        "job_id": job.id,
                        "title": job.title,
                        "candidate_name": candidate_name,
                        "match_score": scoring["total"],
                    },
                    dedupe_key=f"application:{application.id}:submitted",
                )
            )
        db.commit()
    except IntegrityError as exc:  # 并发/工具重试导致重复投递，靠唯一约束兜底
        db.rollback()
        raise ValueError("你已经投递过该岗位") from exc
    db.refresh(application)
    return application


def list_my_applications(db: Session, user: User) -> list[Application]:
    return list(
        db.scalars(
            select(Application)
            .where(Application.user_id == user.id)
            .order_by(Application.id.desc())
        )
    )


def list_job_applications(db: Session, user: User, job_id: int) -> list[Application]:
    job = db.get(Job, job_id)
    if job is None or job.company is None or job.company.owner_user_id != user.id:
        raise PermissionError("岗位不存在或无权查看")
    return list(
        db.scalars(
            select(Application)
            .where(Application.job_id == job_id)
            .order_by(Application.match_score.desc(), Application.id.asc())
        )
    )


def events_for_applications(
    db: Session, application_ids: list[int]
) -> dict[int, list[ApplicationEvent]]:
    """批量取投递事件，避免求职者投递列表 N+1 查询。"""
    if not application_ids:
        return {}
    rows = db.scalars(
        select(ApplicationEvent)
        .where(ApplicationEvent.application_id.in_(application_ids))
        .order_by(ApplicationEvent.id.asc())
    )
    grouped: dict[int, list[ApplicationEvent]] = {}
    for row in rows:
        grouped.setdefault(row.application_id, []).append(row)
    return grouped


def list_events(db: Session, application_id: int) -> list[ApplicationEvent]:
    return list(
        db.scalars(
            select(ApplicationEvent)
            .where(ApplicationEvent.application_id == application_id)
            .order_by(ApplicationEvent.id.asc())
        )
    )


def get_visible_application(
    db: Session, user: User, application_id: int
) -> Application:
    """投递方本人或岗位所属公司的招聘方可见。"""
    application = db.get(Application, application_id)
    if application is None:
        raise ValueError("投递记录不存在")
    job = db.get(Job, application.job_id)
    is_seeker = application.user_id == user.id
    is_employer = bool(
        job and job.company and job.company.owner_user_id == user.id
    )
    if not is_seeker and not is_employer:
        raise PermissionError("无权查看该投递")
    return application


def get_candidate_resume_file(
    db: Session, user: User, application_id: int
) -> ResumeFile | None:
    """招聘方下载候选人上传的原始简历文件。"""
    application = db.get(Application, application_id)
    if application is None:
        raise ValueError("投递记录不存在")
    job = db.get(Job, application.job_id)
    if job is None or job.company is None or job.company.owner_user_id != user.id:
        raise PermissionError("无权查看该候选人的简历")
    resume = db.get(Resume, application.resume_id)
    if resume is None or resume.user_id != application.user_id:
        raise ValueError("候选人简历缺失")
    return resume.upload_file


def _notify_status_change(
    db: Session,
    application: Application,
    job: Job,
    status: str,
    note: str,
) -> None:
    """状态变更写入站内通知；同一投递同一状态只提醒一次。"""
    notify_once(
        db,
        application.user_id,
        "application_status",
        f"投递状态更新：{job.title} · {STATUS_LABELS.get(status, status)}",
        {
            "application_id": application.id,
            "job_id": job.id,
            "status": status,
            "status_label": STATUS_LABELS.get(status, status),
            "note": note,
            "company_name": job.company.name if job.company else "",
        },
        f"application:{application.id}:{status}",
    )


def update_status(
    db: Session, user: User, application_id: int, status: str, note: str = ""
) -> Application:
    if status not in VALID_STATUSES:
        raise ValueError(f"非法状态：{status}")
    application = db.get(Application, application_id)
    if application is None:
        raise ValueError("投递记录不存在")

    job = db.get(Job, application.job_id)
    if job is None or job.company is None or job.company.owner_user_id != user.id:
        raise PermissionError("仅该岗位所属公司的招聘方可以推进状态")
    if not _transition_allowed(application.status, status):
        raise ValueError(f"不允许的状态流转：{application.status} → {status}")

    previous = application.status
    if previous == status:
        if note:
            application.status_note = note
        db.commit()
        db.refresh(application)
        return application

    application.status = status
    if note:
        application.status_note = note
    db.add(
        ApplicationEvent(
            application_id=application.id,
            from_status=previous,
            to_status=status,
            note=note,
            actor_user_id=user.id,
        )
    )
    _notify_status_change(db, application, job, status, note)
    db.commit()
    db.refresh(application)
    return application
