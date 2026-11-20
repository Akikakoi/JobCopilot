from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import User
from app.schemas.common import ok
from app.services import subscription_service

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
def list_notifications(
    unread_only: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    items, unread = subscription_service.list_notifications(
        db, user, unread_only=unread_only, limit=limit
    )
    return ok(
        {
            "items": [subscription_service.notification_to_dict(item) for item in items],
            "unread": unread,
        }
    )


@router.post("/read-all")
def read_all(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    count = subscription_service.mark_all_read(db, user)
    return ok({"updated": count}, message="已全部标记为已读")


@router.post("/{notification_id}/read")
def read_one(
    notification_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        notification = subscription_service.mark_read(db, user, notification_id)
    except PermissionError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ok(subscription_service.notification_to_dict(notification))
