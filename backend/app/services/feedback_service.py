"""岗位反馈：收藏 / 不感兴趣，用于推荐排序偏置（不改原始规则分）。"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Job, JobFeedback, User


def get_action(db: Session, user_id: int, job_id: int) -> str | None:
    row = db.scalar(
        select(JobFeedback).where(
            JobFeedback.user_id == user_id, JobFeedback.job_id == job_id
        )
    )
    return row.action if row else None


def actions_for(db: Session, user_id: int, job_ids: list[int]) -> dict[int, str]:
    if not job_ids:
        return {}
    rows = db.scalars(
        select(JobFeedback).where(
            JobFeedback.user_id == user_id, JobFeedback.job_id.in_(job_ids)
        )
    )
    return {row.job_id: row.action for row in rows}


def list_saved_jobs(db: Session, user_id: int) -> list[Job]:
    """按收藏时间倒序返回岗位（包含已关闭岗位，前端可展示状态）。"""
    rows = list(
        db.scalars(
            select(JobFeedback)
            .where(
                JobFeedback.user_id == user_id,
                JobFeedback.action == "save",
            )
            .order_by(JobFeedback.id.desc())
        )
    )
    if not rows:
        return []
    order = {row.job_id: index for index, row in enumerate(rows)}
    jobs = list(db.scalars(select(Job).where(Job.id.in_(order))))
    jobs.sort(key=lambda job: order[job.id])
    return jobs


def set_action(
    db: Session, user: User, job_id: int, action: str, reason: str = ""
) -> str | None:
    row = db.scalar(
        select(JobFeedback).where(
            JobFeedback.user_id == user.id, JobFeedback.job_id == job_id
        )
    )
    if action == "clear":
        if row is not None:
            db.delete(row)
            db.commit()
        return None

    if row is not None:
        row.action = action
        row.reason = reason
    else:
        db.add(
            JobFeedback(user_id=user.id, job_id=job_id, action=action, reason=reason)
        )
    db.commit()
    return action
