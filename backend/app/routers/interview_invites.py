from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_role
from app.models import User
from app.schemas.common import ok
from app.schemas.interview_invite import (
    InterviewInviteCancelIn,
    InterviewInviteIn,
    InterviewInviteRespondIn,
)
from app.services import application_service, interview_invite_service

router = APIRouter(prefix="/applications", tags=["interview-invites"])


@router.get("/{application_id}/interview-invites")
def list_invites(
    application_id: int,
    user: User = Depends(require_role("seeker", "employer")),
    db: Session = Depends(get_db),
):
    try:
        application_service.get_visible_application(db, user, application_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    items = interview_invite_service.list_for_application(db, application_id)
    return ok(
        {"items": [interview_invite_service.invite_to_dict(item) for item in items]}
    )


@router.post("/{application_id}/interview-invites")
def create_invite(
    application_id: int,
    payload: InterviewInviteIn,
    user: User = Depends(require_role("employer")),
    db: Session = Depends(get_db),
):
    try:
        invite = interview_invite_service.create_invite(
            db, user, application_id, payload.model_dump()
        )
    except interview_invite_service.InterviewInviteError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return ok(interview_invite_service.invite_to_dict(invite), message="面试邀约已发送")


@router.post("/{application_id}/interview-invites/{invite_id}/respond")
def respond_invite(
    application_id: int,
    invite_id: int,
    payload: InterviewInviteRespondIn,
    user: User = Depends(require_role("seeker")),
    db: Session = Depends(get_db),
):
    try:
        invite = interview_invite_service.respond_invite(
            db, user, application_id, invite_id, payload.action, payload.note
        )
    except interview_invite_service.InterviewInviteError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    message = "已确认面试" if payload.action == "confirm" else "已拒绝面试邀约"
    return ok(interview_invite_service.invite_to_dict(invite), message=message)


@router.post("/{application_id}/interview-invites/{invite_id}/complete")
def complete_invite(
    application_id: int,
    invite_id: int,
    payload: InterviewInviteCancelIn,
    user: User = Depends(require_role("employer")),
    db: Session = Depends(get_db),
):
    try:
        invite = interview_invite_service.complete_invite(
            db, user, application_id, invite_id, payload.note
        )
    except interview_invite_service.InterviewInviteError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return ok(interview_invite_service.invite_to_dict(invite), message="面试已标记完成")


@router.post("/{application_id}/interview-invites/{invite_id}/cancel")
def cancel_invite(
    application_id: int,
    invite_id: int,
    payload: InterviewInviteCancelIn,
    user: User = Depends(require_role("employer")),
    db: Session = Depends(get_db),
):
    try:
        invite = interview_invite_service.cancel_invite(
            db, user, application_id, invite_id, payload.note
        )
    except interview_invite_service.InterviewInviteError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return ok(interview_invite_service.invite_to_dict(invite), message="面试邀约已取消")
