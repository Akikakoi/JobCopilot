"""入职闭环：Offer 接受后确认入职、放弃入职，并由招聘方记录实际到岗结果。"""

from sqlalchemy.orm import Session

from app.models import Application, ApplicationEvent, Job, User
from app.services.application_service import (
    ONBOARDING_RESULT_LABELS,
    STATUS_LABELS,
)
from app.services.notification_service import notify_once
from app.utils import utcnow


class OnboardingError(ValueError):
    pass


def _candidate_application(
    db: Session, user: User, application_id: int
) -> tuple[Application, Job]:
    application = db.get(Application, application_id)
    if application is None or application.user_id != user.id:
        raise PermissionError("投递记录不存在")
    job = db.get(Job, application.job_id)
    if job is None:
        raise OnboardingError("岗位不存在")
    return application, job


def _employer_application(
    db: Session, user: User, application_id: int
) -> tuple[Application, Job]:
    application = db.get(Application, application_id)
    if application is None:
        raise OnboardingError("投递记录不存在")
    job = db.get(Job, application.job_id)
    if job is None or job.company is None or job.company.owner_user_id != user.id:
        raise PermissionError("仅该岗位所属公司的招聘方可以记录入职结果")
    return application, job


def _require_onboarding(application: Application) -> None:
    if application.status != "onboarding":
        raise OnboardingError("当前不在待入职阶段，无法执行该操作")


def _add_event(
    db: Session,
    application: Application,
    from_status: str,
    to_status: str,
    note: str,
    actor_user_id: int,
) -> None:
    db.add(
        ApplicationEvent(
            application_id=application.id,
            from_status=from_status,
            to_status=to_status,
            note=note,
            actor_user_id=actor_user_id,
        )
    )


def confirm_onboarding(
    db: Session, user: User, application_id: int, note: str = ""
) -> Application:
    """候选人确认入职安排；重复确认按幂等处理。"""
    application, job = _candidate_application(db, user, application_id)
    _require_onboarding(application)

    note = (note or "").strip()
    application.onboarding_confirmed_at = utcnow()
    if note:
        application.onboarding_note = note

    if job.company is not None:
        notify_once(
            db,
            job.company.owner_user_id,
            "onboarding_confirmed",
            f"候选人已确认入职：{job.title}",
            {
                "application_id": application.id,
                "job_id": job.id,
                "title": job.title,
                "candidate_name": user.display_name or user.username,
                "onboarding_date": application.onboarding_date,
                "note": note,
            },
            f"onboarding:{application.id}:confirmed",
        )

    db.commit()
    db.refresh(application)
    return application


def abandon_onboarding(
    db: Session, user: User, application_id: int, note: str = ""
) -> Application:
    """候选人主动放弃入职，投递进入 abandoned 终态。"""
    application, job = _candidate_application(db, user, application_id)
    _require_onboarding(application)

    note = (note or "").strip()
    previous = application.status
    application.status = "abandoned"
    application.onboarding_result = "abandoned"
    application.onboarding_result_at = utcnow()
    application.status_note = note or "候选人放弃入职"
    application.onboarding_note = note
    _add_event(
        db,
        application,
        previous,
        "abandoned",
        note or "候选人放弃入职",
        user.id,
    )

    if job.company is not None:
        notify_once(
            db,
            job.company.owner_user_id,
            "onboarding_result",
            f"候选人放弃入职：{job.title}",
            {
                "application_id": application.id,
                "job_id": job.id,
                "title": job.title,
                "candidate_name": user.display_name or user.username,
                "result": "abandoned",
                "result_label": ONBOARDING_RESULT_LABELS["abandoned"],
                "note": note,
            },
            f"onboarding:{application.id}:abandoned",
        )

    db.commit()
    db.refresh(application)
    return application


def record_onboarding_result(
    db: Session,
    user: User,
    application_id: int,
    result: str,
    note: str = "",
    onboarding_date: str = "",
) -> Application:
    """招聘方记录实际到岗结果：已入职 / 放弃入职。"""
    if result not in ("hired", "abandoned"):
        raise OnboardingError("result 只能是 hired 或 abandoned")
    application, job = _employer_application(db, user, application_id)
    _require_onboarding(application)

    note = (note or "").strip()
    previous = application.status
    application.status = result
    application.onboarding_result = result
    application.onboarding_result_at = utcnow()
    if onboarding_date:
        application.onboarding_date = onboarding_date.strip()
    application.status_note = note or ONBOARDING_RESULT_LABELS[result]
    application.onboarding_note = note
    _add_event(
        db,
        application,
        previous,
        result,
        note or f"招聘方记录到岗结果：{ONBOARDING_RESULT_LABELS[result]}",
        user.id,
    )

    notify_once(
        db,
        application.user_id,
        "onboarding_result",
        f"入职结果更新：{job.title} · {ONBOARDING_RESULT_LABELS[result]}",
        {
            "application_id": application.id,
            "job_id": job.id,
            "status": result,
            "status_label": STATUS_LABELS.get(result, result),
            "result": result,
            "result_label": ONBOARDING_RESULT_LABELS[result],
            "onboarding_date": application.onboarding_date,
            "note": note,
            "company_name": job.company.name if job.company else "",
        },
        f"onboarding:{application.id}:{result}",
    )

    db.commit()
    db.refresh(application)
    return application
