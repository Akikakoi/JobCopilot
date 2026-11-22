"""站内通知写入：按 (user_id, type, dedupe_key) 去重，避免重复提醒。"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Notification


def notify_once(
    db: Session,
    user_id: int,
    ntype: str,
    title: str,
    payload: dict,
    dedupe_key: str,
) -> bool:
    """写入一条站内通知；同一用户同一类型同一去重键已存在时跳过。"""
    exists = db.scalar(
        select(Notification.id).where(
            Notification.user_id == user_id,
            Notification.type == ntype,
            Notification.dedupe_key == dedupe_key,
        )
    )
    if exists is not None:
        return False
    db.add(
        Notification(
            user_id=user_id,
            type=ntype,
            title=title,
            payload=payload,
            dedupe_key=dedupe_key,
        )
    )
    return True
