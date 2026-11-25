"""Offer：招聘方发出、候选人接受/拒绝，并同步投递状态与站内通知。"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Application, ApplicationEvent, Job, Offer, User
from app.services.notification_service import notify_once
from app.utils import to_utc_naive, utcnow

STATUS_LABELS = {
    "pending": "待候选人确认",
    "accepted": "已接受",
    "declined": "已拒绝",
    "expired": "已过期",
    "withdrawn": "已撤回",
}


class OfferError(ValueError):
    pass


def _effective_status(offer: Offer) -> str:
    if (
        offer.status == "pending"
        and offer.expires_at is not None
        and offer.expires_at < utcnow()
    ):
        return "expired"
    return offer.status


def offer_to_dict(offer: Offer) -> dict:
    status = _effective_status(offer)
    return {
        "id": offer.id,
        "application_id": offer.application_id,
        "job_id": offer.job_id,
        "salary_min": offer.salary_min,
        "salary_max": offer.salary_max,
        "start_date": offer.start_date,
        "expires_at": offer.expires_at,
        "note": offer.note,
        "status": status,
        "status_label": STATUS_LABELS.get(status, status),
        "response_note": offer.response_note,
        "responded_at": offer.responded_at,
        "created_at": offer.created_at,
    }


def get_offer(db: Session, application_id: int) -> Offer | None:
    return db.scalar(select(Offer).where(Offer.application_id == application_id))


def _application_for_employer(
    db: Session, user: User, application_id: int
) -> tuple[Application, Job]:
    application = db.get(Application, application_id)
    if application is None:
        raise OfferError("投递记录不存在")
    job = db.get(Job, application.job_id)
    if job is None or job.company is None or job.company.owner_user_id != user.id:
        raise PermissionError("仅该岗位所属公司的招聘方可以操作")
    return application, job


def _application_for_candidate(
    db: Session, user: User, application_id: int
) -> tuple[Application, Job]:
    application = db.get(Application, application_id)
    if application is None or application.user_id != user.id:
        raise PermissionError("投递记录不存在")
    job = db.get(Job, application.job_id)
    if job is None:
        raise OfferError("岗位不存在")
    return application, job


def create_offer(db: Session, user: User, application_id: int, data: dict) -> Offer:
    application, job = _application_for_employer(db, user, application_id)
    if application.status == "rejected":
        raise OfferError("该投递已结束，无法发起 Offer")
    if application.status in ("onboarding", "hired", "abandoned"):
        raise OfferError("候选人已进入入职阶段，无法重新发起 Offer")

    offer = get_offer(db, application_id)
    created = offer is None
    if offer is not None and offer.status != "pending":
        raise OfferError("Offer 已结束（已响应/已撤回/已过期），无法修改；如需重新沟通请先更新投递状态")

    if offer is None:
        offer = Offer(
            application_id=application_id,
            job_id=job.id,
            user_id=application.user_id,
            created_by_user_id=user.id,
        )
        db.add(offer)

    offer.salary_min = float(data.get("salary_min") or 0)
    offer.salary_max = float(data.get("salary_max") or 0)
    offer.start_date = (data.get("start_date") or "").strip()
    offer.expires_at = to_utc_naive(data.get("expires_at"))
    offer.note = (data.get("note") or "").strip()
    offer.status = "pending"

    if application.status != "offer":
        previous = application.status
        application.status = "offer"
        db.add(
            ApplicationEvent(
                application_id=application.id,
                from_status=previous,
                to_status="offer",
                note="招聘方发出 Offer",
                actor_user_id=user.id,
            )
        )

    db.flush()
    if created:
        notify_once(
            db,
            application.user_id,
            "offer",
            f"收到 Offer：{job.title} · {job.company.name if job.company else ''}",
            {
                "application_id": application.id,
                "job_id": job.id,
                "title": job.title,
                "company_name": job.company.name if job.company else "",
                "salary_min": offer.salary_min,
                "salary_max": offer.salary_max,
                "start_date": offer.start_date,
                "expires_at": offer.expires_at.isoformat() if offer.expires_at else None,
            },
            f"offer:{offer.id}:pending",
        )
    db.commit()
    db.refresh(offer)
    return offer


def respond_offer(
    db: Session, user: User, application_id: int, action: str, note: str = ""
) -> Offer:
    application, job = _application_for_candidate(db, user, application_id)
    offer = get_offer(db, application_id)
    if offer is None:
        raise OfferError("该投递还没有 Offer")
    if application.status == "rejected":
        raise OfferError("该投递已结束，无法响应 Offer")
    if offer.status == "expired":
        raise OfferError("Offer 已过期")
    if offer.status != "pending":
        raise OfferError("Offer 已响应，请勿重复操作")
    if offer.expires_at is not None and offer.expires_at < utcnow():
        offer.status = "expired"
        db.commit()
        raise OfferError("Offer 已过期，请联系招聘方重新发起")

    note = (note or "").strip()
    offer.responded_at = utcnow()
    offer.response_note = note

    if action == "accept":
        offer.status = "accepted"
        previous = application.status
        application.status = "onboarding"
        application.onboarding_date = offer.start_date or application.onboarding_date
        application.status_note = note or "候选人已接受 Offer，进入待入职"
        db.add(
            ApplicationEvent(
                application_id=application.id,
                from_status=previous,
                to_status="onboarding",
                note=note or "候选人已接受 Offer，进入待入职",
                actor_user_id=user.id,
            )
        )
    else:
        offer.status = "declined"
        previous = application.status
        application.status = "rejected"
        application.status_note = note or "候选人拒绝了 Offer"
        db.add(
            ApplicationEvent(
                application_id=application.id,
                from_status=previous,
                to_status="rejected",
                note=note or "候选人拒绝了 Offer",
                actor_user_id=user.id,
            )
        )

    if job.company is not None:
        notify_once(
            db,
            job.company.owner_user_id,
            "offer_response",
            f"候选人{'接受' if action == 'accept' else '拒绝'}了 Offer：{job.title}",
            {
                "application_id": application.id,
                "job_id": job.id,
                "title": job.title,
                "candidate_name": (user.display_name or user.username),
                "action": action,
                "note": note,
            },
            f"offer:{offer.id}:{action}",
        )

    db.commit()
    db.refresh(offer)
    return offer


def group_offers(db: Session, application_ids: list[int]) -> dict[int, dict]:
    if not application_ids:
        return {}
    rows = db.scalars(select(Offer).where(Offer.application_id.in_(application_ids)))
    return {row.application_id: offer_to_dict(row) for row in rows}
