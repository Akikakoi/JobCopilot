from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_role
from app.models import InterviewInvite, Offer, User
from app.schemas.common import ok
from app.schemas.message import ConversationStartIn, MessageIn
from app.services import interview_invite_service, message_service, offer_service

router = APIRouter(prefix="/conversations", tags=["messages"])


def _attach_cards(db: Session, items: list[dict]) -> None:
    """卡片消息只存 kind + ref_id，读取时补全邀约 / Offer 的实时状态。"""
    invite_ids = {
        item["ref_id"]
        for item in items
        if item["kind"] == "interview_invite" and item["ref_id"]
    }
    offer_ids = {
        item["ref_id"] for item in items if item["kind"] == "offer" and item["ref_id"]
    }
    invites = (
        {
            invite.id: interview_invite_service.invite_to_dict(invite)
            for invite in db.scalars(
                select(InterviewInvite).where(InterviewInvite.id.in_(invite_ids))
            )
        }
        if invite_ids
        else {}
    )
    offers = (
        {
            offer.id: offer_service.offer_to_dict(offer)
            for offer in db.scalars(select(Offer).where(Offer.id.in_(offer_ids)))
        }
        if offer_ids
        else {}
    )
    for item in items:
        if item["kind"] == "interview_invite":
            item["card"] = invites.get(item["ref_id"])
        elif item["kind"] == "offer":
            item["card"] = offers.get(item["ref_id"])
        else:
            item["card"] = None


@router.post("")
def start_conversation(
    payload: ConversationStartIn,
    user: User = Depends(require_role("seeker", "employer")),
    db: Session = Depends(get_db),
):
    """发起沟通：求职者传 job_id / company_id，招聘方传 seeker_user_id（可带 job_id）。"""
    try:
        conversation, created = message_service.start_conversation(
            db,
            user,
            job_id=payload.job_id,
            company_id=payload.company_id,
            seeker_user_id=payload.seeker_user_id,
        )
    except message_service.MessageError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(
        {
            "id": conversation.id,
            "created": created,
            "application_id": conversation.application_id,
            "job_id": conversation.job_id,
        },
        message="已发起沟通" if created else "已存在会话",
    )


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
    _attach_cards(db, items)
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
