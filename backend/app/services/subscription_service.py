"""订阅与站内通知：订阅 CRUD + 增量扫描新岗位 + 通知读写。"""

import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.matching.rules import score_resume_job
from app.models import Job, Notification, Resume, Subscription, User

SCAN_THROTTLE_SECONDS = 600
# 订阅上次扫描时间：进程内节流即可（单机演示，重启后允许立即再扫）
_last_scan: dict[int, float] = {}


class SubscriptionError(ValueError):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def subscription_to_dict(subscription: Subscription) -> dict:
    return {
        "id": subscription.id,
        "name": subscription.name,
        "filters": subscription.filters or {},
        "active": bool(subscription.active),
        "last_checked_at": subscription.last_checked_at,
        "created_at": subscription.created_at,
    }


def list_subscriptions(db: Session, user: User) -> list[Subscription]:
    return list(
        db.scalars(
            select(Subscription)
            .where(Subscription.user_id == user.id)
            .order_by(Subscription.id.desc())
        )
    )


def create_subscription(db: Session, user: User, name: str, filters: dict, active: bool) -> Subscription:
    subscription = Subscription(
        user_id=user.id,
        name=name.strip(),
        filters=filters,
        active=active,
        # 留 60 秒宽限，避免与「刚发布的岗位」在同一秒被时间精度吞掉
        last_checked_at=_utcnow() - timedelta(seconds=60),
    )
    db.add(subscription)
    db.commit()
    db.refresh(subscription)
    return subscription


def get_owned(db: Session, user: User, subscription_id: int) -> Subscription:
    subscription = db.get(Subscription, subscription_id)
    if subscription is None or subscription.user_id != user.id:
        raise PermissionError("订阅不存在或无权操作")
    return subscription


def update_subscription(
    db: Session, user: User, subscription_id: int, data: dict
) -> Subscription:
    subscription = get_owned(db, user, subscription_id)
    if "name" in data and data["name"] is not None:
        subscription.name = data["name"].strip()
    if "filters" in data and data["filters"] is not None:
        subscription.filters = data["filters"]
    if "active" in data and data["active"] is not None:
        subscription.active = bool(data["active"])
    db.commit()
    db.refresh(subscription)
    return subscription


def delete_subscription(db: Session, user: User, subscription_id: int) -> None:
    subscription = get_owned(db, user, subscription_id)
    db.delete(subscription)
    db.commit()


def _matches(job: Job, filters: dict) -> bool:
    if not filters:
        return True

    location = (filters.get("location") or "").strip()
    if location and location not in job.location and job.location not in ("不限", "远程"):
        return False

    salary_min = filters.get("salary_min")
    if salary_min is not None and (job.salary_max or 0) < float(salary_min):
        return False

    keywords = (filters.get("keywords") or "").strip().lower()
    if keywords:
        haystack = [
            job.title.lower(),
            (job.description or "").lower(),
            (job.company.name.lower() if job.company else ""),
            *[skill.lower() for skill in (job.required_skills or []) + (job.preferred_skills or [])],
        ]
        if not any(keywords in text for text in haystack):
            return False

    skills = [skill.strip().lower() for skill in filters.get("skills") or [] if skill.strip()]
    if skills:
        job_skills = [skill.lower() for skill in (job.required_skills or []) + (job.preferred_skills or [])]
        if not any(
            wanted in job_skill or job_skill in wanted
            for wanted in skills
            for job_skill in job_skills
        ):
            return False
    return True


def _resume_of(db: Session, user_id: int) -> Resume | None:
    return db.scalar(select(Resume).where(Resume.user_id == user_id))


def scan_for_user(db: Session, user: User) -> dict:
    """扫描新增岗位并写入站内通知。同一用户 10 分钟内只真正扫一次。"""
    now = _utcnow()
    last = _last_scan.get(user.id)
    if last is not None and (time.time() - last) < SCAN_THROTTLE_SECONDS:
        return {"skipped": True, "created": 0, "scanned": 0}

    subscriptions = [item for item in list_subscriptions(db, user) if item.active]
    if not subscriptions:
        return {"skipped": False, "created": 0, "scanned": 0}

    _last_scan[user.id] = time.time()
    window_start = min(
        (item.last_checked_at for item in subscriptions if item.last_checked_at),
        default=None,
    ) or (now - timedelta(days=14))

    jobs = list(
        db.scalars(
            select(Job)
            .where(Job.status == "open", Job.created_at > window_start)
            .order_by(Job.id.desc())
        )
    )
    resume = _resume_of(db, user.id)
    existing_keys = set(
        db.scalars(
            select(Notification.dedupe_key).where(
                Notification.user_id == user.id,
                Notification.type == "job_recommendation",
            )
        )
    )

    created = 0
    for job in jobs:
        for subscription in subscriptions:
            filters = subscription.filters or {}
            if not _matches(job, filters):
                continue

            score = None
            if resume is not None:
                score = score_resume_job(resume.structured or {}, job)["total"]
            threshold = filters.get("match_score_min")
            if threshold is not None and (score is None or score < float(threshold)):
                continue

            dedupe_key = f"job:{job.id}"
            if dedupe_key in existing_keys:
                break  # 该岗位已提醒过（跨订阅去重）

            db.add(
                Notification(
                    user_id=user.id,
                    type="job_recommendation",
                    title=f"新岗位推荐：{job.title} · {job.company.name if job.company else ''}",
                    payload={
                        "job_id": job.id,
                        "title": job.title,
                        "company_name": job.company.name if job.company else "",
                        "location": job.location,
                        "salary_min": job.salary_min,
                        "salary_max": job.salary_max,
                        "match_score": score,
                        "subscription_id": subscription.id,
                        "subscription_name": subscription.name,
                    },
                    dedupe_key=dedupe_key,
                )
            )
            existing_keys.add(dedupe_key)
            created += 1
            break

    for subscription in subscriptions:
        # 回退 5 秒作为下一次扫描的水位，避免 SQLite 秒级精度漏掉同秒发布的岗位
        subscription.last_checked_at = now - timedelta(seconds=5)
    db.commit()
    return {"skipped": False, "created": created, "scanned": len(jobs)}


def notification_to_dict(notification: Notification) -> dict:
    return {
        "id": notification.id,
        "type": notification.type,
        "title": notification.title,
        "payload": notification.payload or {},
        "read": notification.read_at is not None,
        "created_at": notification.created_at,
    }


def list_notifications(
    db: Session, user: User, unread_only: bool = False, limit: int = 50
) -> tuple[list[Notification], int]:
    stmt = select(Notification).where(Notification.user_id == user.id)
    if unread_only:
        stmt = stmt.where(Notification.read_at.is_(None))
    items = list(db.scalars(stmt.order_by(Notification.id.desc()).limit(limit)))
    unread = int(
        db.scalar(
            select(func.count(Notification.id)).where(
                Notification.user_id == user.id, Notification.read_at.is_(None)
            )
        )
        or 0
    )
    return items, unread


def mark_read(db: Session, user: User, notification_id: int) -> Notification:
    notification = db.get(Notification, notification_id)
    if notification is None or notification.user_id != user.id:
        raise PermissionError("通知不存在或无权操作")
    if notification.read_at is None:
        notification.read_at = _utcnow()
        db.commit()
        db.refresh(notification)
    return notification


def mark_all_read(db: Session, user: User) -> int:
    notifications, _ = list_notifications(db, user, unread_only=True, limit=500)
    now = _utcnow()
    for notification in notifications:
        notification.read_at = now
    db.commit()
    return len(notifications)

