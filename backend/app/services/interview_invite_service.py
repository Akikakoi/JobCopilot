"""面试邀约：招聘方发起，候选人确认或拒绝，并联动投递状态与站内通知。"""

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Application,
    ApplicationEvent,
    InterviewInvite,
    Job,
    User,
)
from app.services.notification_service import notify_once
from app.utils import to_utc_naive, utcnow

STATUS_LABELS = {
    "pending": "待候选人确认",
    "confirmed": "已确认",
    "declined": "已拒绝",
    "cancelled": "已取消",
    "completed": "已完成",
}
MODE_LABELS = {"onsite": "现场面试", "video": "视频面试", "phone": "电话面试"}
ACTIVE_STATUSES = ("pending", "confirmed")


class InterviewInviteError(ValueError):
    pass


def _validate_schedule(
    invites: list[InterviewInvite], scheduled_at: datetime, duration: int
) -> None:
    if scheduled_at < utcnow() - timedelta(minutes=1):
        raise InterviewInviteError("面试时间必须晚于当前时间")
    new_end = scheduled_at + timedelta(minutes=duration)
    for item in invites:
        if item.status not in ACTIVE_STATUSES:
            continue
        other_start = item.scheduled_at
        other_end = other_start + timedelta(minutes=item.duration_minutes or 45)
        if scheduled_at < other_end and new_end > other_start:
            raise InterviewInviteError(f"与第 {item.round} 轮面试时间冲突，请调整时间")


def invite_to_dict(invite: InterviewInvite) -> dict:
    return {
        "id": invite.id,
        "application_id": invite.application_id,
        "job_id": invite.job_id,
        "round": invite.round,
        "scheduled_at": invite.scheduled_at,
        "duration_minutes": invite.duration_minutes,
        "mode": invite.mode,
        "mode_label": MODE_LABELS.get(invite.mode, invite.mode),
        "location": invite.location,
        "note": invite.note,
        "status": invite.status,
        "status_label": STATUS_LABELS.get(invite.status, invite.status),
        "candidate_note": invite.candidate_note,
        "created_at": invite.created_at,
    }


def list_for_application(db: Session, application_id: int) -> list[InterviewInvite]:
    return list(
        db.scalars(
            select(InterviewInvite)
            .where(InterviewInvite.application_id == application_id)
            .order_by(InterviewInvite.round.asc(), InterviewInvite.id.asc())
        )
    )


def group_invites(db: Session, application_ids: list[int]) -> dict[int, list[dict]]:
    if not application_ids:
        return {}
    rows = db.scalars(
        select(InterviewInvite)
        .where(InterviewInvite.application_id.in_(application_ids))
        .order_by(InterviewInvite.round.asc(), InterviewInvite.id.asc())
    )
    grouped: dict[int, list[dict]] = {}
    for row in rows:
        grouped.setdefault(row.application_id, []).append(invite_to_dict(row))
    return grouped


def _application_for_employer(
    db: Session, user: User, application_id: int
) -> tuple[Application, Job]:
    application = db.get(Application, application_id)
    if application is None:
        raise InterviewInviteError("投递记录不存在")
    job = db.get(Job, application.job_id)
    if job is None or job.company is None or job.company.owner_user_id != user.id:
        raise PermissionError("仅该岗位所属公司的招聘方可以操作")
    return application, job


def create_invite(
    db: Session, user: User, application_id: int, data: dict
) -> InterviewInvite:
    application, job = _application_for_employer(db, user, application_id)
    if application.status == "rejected":
        raise InterviewInviteError("该投递已结束，无法安排面试")
    if application.status in ("offer", "onboarding", "hired", "abandoned"):
        raise InterviewInviteError("该投递已进入 Offer / 入职阶段")

    invites = list_for_application(db, application_id)
    duration = int(data.get("duration_minutes") or 45)
    if duration < 15 or duration > 240:
        raise InterviewInviteError("面试时长需在 15-240 分钟之间")
    mode = data.get("mode") or "video"
    if mode not in MODE_LABELS:
        raise InterviewInviteError("面试方式不合法")
    scheduled_at = to_utc_naive(data["scheduled_at"])
    _validate_schedule(invites, scheduled_at, duration)

    next_round = max((item.round for item in invites), default=0) + 1
    invite = InterviewInvite(
        application_id=application_id,
        job_id=job.id,
        user_id=application.user_id,
        created_by_user_id=user.id,
        round=next_round,
        scheduled_at=scheduled_at,
        duration_minutes=duration,
        mode=mode,
        location=(data.get("location") or "").strip(),
        note=(data.get("note") or "").strip(),
    )
    db.add(invite)

    if application.status in ("submitted", "screening"):
        previous = application.status
        application.status = "interview"
        db.add(
            ApplicationEvent(
                application_id=application.id,
                from_status=previous,
                to_status="interview",
                note=f"安排第 {invite.round} 轮面试",
                actor_user_id=user.id,
            )
        )

    db.flush()
    notify_once(
        db,
        application.user_id,
        "interview_invite",
        f"面试邀约：{job.title} · {job.company.name if job.company else ''}",
        {
            "application_id": application.id,
            "job_id": job.id,
            "title": job.title,
            "company_name": job.company.name if job.company else "",
            "round": invite.round,
            "scheduled_at": invite.scheduled_at.isoformat(),
            "mode": invite.mode,
            "mode_label": MODE_LABELS.get(invite.mode, invite.mode),
            "location": invite.location,
        },
        f"invite:{invite.id}:created",
    )
    db.commit()
    db.refresh(invite)
    return invite


def _get_invite(
    db: Session, user: User, application_id: int, invite_id: int
) -> InterviewInvite:
    invite = db.get(InterviewInvite, invite_id)
    if invite is None or invite.application_id != application_id:
        raise InterviewInviteError("面试邀约不存在")
    application = db.get(Application, application_id)
    if application is None:
        raise InterviewInviteError("投递记录不存在")
    job = db.get(Job, application.job_id)
    is_candidate = application.user_id == user.id
    is_employer = bool(job and job.company and job.company.owner_user_id == user.id)
    if not is_candidate and not is_employer:
        raise PermissionError("无权操作该面试邀约")
    return invite


def respond_invite(
    db: Session,
    user: User,
    application_id: int,
    invite_id: int,
    action: str,
    note: str = "",
) -> InterviewInvite:
    invite = _get_invite(db, user, application_id, invite_id)
    if invite.user_id != user.id:
        raise PermissionError("只有候选人可以响应邀约")
    if invite.status == "completed":
        raise InterviewInviteError("面试已完成，无法再响应")
    if invite.status in ("declined", "cancelled"):
        raise InterviewInviteError("该邀约已结束，请等待招聘方重新安排")
    if invite.status == "confirmed" and action == "confirm":
        return invite

    invite.status = "confirmed" if action == "confirm" else "declined"
    invite.candidate_note = (note or "").strip()

    application = db.get(Application, application_id)
    job = db.get(Job, application.job_id) if application else None
    if job is not None and job.company is not None:
        notify_once(
            db,
            job.company.owner_user_id,
            "interview_response",
            f"候选人{'确认' if action == 'confirm' else '拒绝'}了面试邀约：{job.title}",
            {
                "application_id": application.id,
                "job_id": job.id,
                "title": job.title,
                "candidate_name": user.display_name or user.username,
                "round": invite.round,
                "action": action,
                "note": invite.candidate_note,
            },
            f"invite:{invite.id}:{action}",
        )
    db.commit()
    db.refresh(invite)
    return invite


def complete_invite(
    db: Session, user: User, application_id: int, invite_id: int, note: str = ""
) -> InterviewInvite:
    invite = _get_invite(db, user, application_id, invite_id)
    application, job = _application_for_employer(db, user, application_id)
    if invite.status == "completed":
        return invite
    if invite.status not in ACTIVE_STATUSES:
        raise InterviewInviteError("只有待确认或已确认的邀约可以标记完成")

    invite.status = "completed"
    if note:
        invite.note = f"{invite.note}\n完成备注：{note.strip()}".strip()

    notify_once(
        db,
        application.user_id,
        "interview_invite",
        f"面试已完成：{job.title}",
        {
            "application_id": application.id,
            "job_id": job.id,
            "title": job.title,
            "company_name": job.company.name if job.company else "",
            "round": invite.round,
            "action": "completed",
            "note": note,
        },
        f"invite:{invite.id}:completed",
    )
    db.commit()
    db.refresh(invite)
    return invite


def cancel_invite(
    db: Session, user: User, application_id: int, invite_id: int, note: str = ""
) -> InterviewInvite:
    invite = _get_invite(db, user, application_id, invite_id)
    application, job = _application_for_employer(db, user, application_id)
    if invite.status == "completed":
        raise InterviewInviteError("面试已完成，无法取消")
    if invite.status in ("declined", "cancelled"):
        raise InterviewInviteError("该邀约已结束，无需取消")

    invite.status = "cancelled"
    invite.note = (invite.note or "").strip()
    if note:
        invite.note = f"{invite.note}\n取消原因：{note.strip()}".strip()

    notify_once(
        db,
        application.user_id,
        "interview_invite",
        f"面试邀约已取消：{job.title}",
        {
            "application_id": application.id,
            "job_id": job.id,
            "title": job.title,
            "company_name": job.company.name if job.company else "",
            "round": invite.round,
            "action": "cancelled",
            "note": note,
        },
        f"invite:{invite.id}:cancelled",
    )
    db.commit()
    db.refresh(invite)
    return invite
