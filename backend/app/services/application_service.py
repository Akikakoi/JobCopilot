from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.matching.rules import score_resume_job
from app.models import Application, Job, Resume, User

VALID_STATUSES = {"submitted", "screening", "interview", "offer", "rejected"}
# 只能向前推进或淘汰；offer / rejected 为终态，禁止回退
STAGE_ORDER = ["submitted", "screening", "interview", "offer"]


def _transition_allowed(current: str, target: str) -> bool:
    if current == target:
        return True
    if current in ("offer", "rejected"):
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
    "rejected": "未通过",
}


def application_to_dict(app: Application) -> dict:
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

    application.status = status
    if note:
        application.status_note = note
    db.commit()
    db.refresh(application)
    return application
