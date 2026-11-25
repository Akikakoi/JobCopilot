from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_role
from app.models import User
from app.schemas.common import ok
from app.schemas.message import MessageIn
from app.services import message_service

router = APIRouter(prefix="/conversations", tags=["messages"])


@router.get("")
def list_conversations(
    user: User = Depends(require_role("seeker", "employer")),
    db: Session = Depends(get_db),
):
    return ok(message_service.list_conversations(db, user))


@router.get("/unread-count")
def unread_count(
    user: User = Depends(require_role("seeker", "employer")),
    db: Session = Depends(get_db),
):
    return ok({"unread": message_service.unread_total(db, user)})


@router.get("/{conversation_id}/messages")
def list_messages(
    conversation_id: int,
    after_id: int | None = Query(default=None, ge=0),
    before_id: int | None = Query(default=None, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
    user: User = Depends(require_role("seeker", "employer")),
    db: Session = Depends(get_db),
):
    try:
        items, has_more = message_service.list_messages(
            db,
            user,
            conversation_id,
            after_id=after_id,
            before_id=before_id,
            limit=limit,
        )
    except message_service.MessageError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return ok({"items": items, "has_more": has_more})


@router.post("/{conversation_id}/messages")
def send_message(
    conversation_id: int,
    payload: MessageIn,
    user: User = Depends(require_role("seeker", "employer")),
    db: Session = Depends(get_db),
):
    try:
        message = message_service.send_message(db, user, conversation_id, payload.content)
    except message_service.MessageError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return ok(message, message="已发送")


@router.post("/{conversation_id}/read")
def mark_read(
    conversation_id: int,
    user: User = Depends(require_role("seeker", "employer")),
    db: Session = Depends(get_db),
):
    try:
        updated = message_service.mark_read(db, user, conversation_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return ok({"updated": updated})
