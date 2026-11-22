from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_role
from app.models import User
from app.schemas.common import ok
from app.schemas.subscription import SubscriptionIn, SubscriptionUpdate
from app.services import subscription_service

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


@router.get("")
def list_subscriptions(
    user: User = Depends(require_role("seeker")),
    db: Session = Depends(get_db),
):
    items = subscription_service.list_subscriptions(db, user)
    return ok(
        {"items": [subscription_service.subscription_to_dict(item) for item in items]}
    )


@router.post("")
def create_subscription(
    payload: SubscriptionIn,
    user: User = Depends(require_role("seeker")),
    db: Session = Depends(get_db),
):
    try:
        subscription = subscription_service.create_subscription(
            db, user, payload.name, payload.filters.model_dump(), payload.active
        )
    except subscription_service.SubscriptionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(
        subscription_service.subscription_to_dict(subscription), message="订阅已创建"
    )


@router.post("/scan")
def scan_subscriptions(
    user: User = Depends(require_role("seeker")),
    db: Session = Depends(get_db),
):
    result = subscription_service.scan_for_user(db, user)
    return ok(result)


@router.put("/{subscription_id}")
def update_subscription(
    subscription_id: int,
    payload: SubscriptionUpdate,
    user: User = Depends(require_role("seeker")),
    db: Session = Depends(get_db),
):
    data = payload.model_dump(exclude_unset=True)
    if data.get("filters") is not None:
        data["filters"] = {
            key: value for key, value in data["filters"].items() if value is not None
        }
    try:
        subscription = subscription_service.update_subscription(db, user, subscription_id, data)
    except subscription_service.SubscriptionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ok(
        subscription_service.subscription_to_dict(subscription), message="订阅已更新"
    )


@router.delete("/{subscription_id}")
def delete_subscription(
    subscription_id: int,
    user: User = Depends(require_role("seeker")),
    db: Session = Depends(get_db),
):
    try:
        subscription_service.delete_subscription(db, user, subscription_id)
    except PermissionError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ok(None, message="订阅已删除")
