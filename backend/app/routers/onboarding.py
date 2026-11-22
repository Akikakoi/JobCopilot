from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_role
from app.models import User
from app.schemas.common import ok
from app.schemas.onboarding import OnboardingNoteIn, OnboardingResultIn
from app.services import application_service, onboarding_service

router = APIRouter(prefix="/applications", tags=["onboarding"])


@router.post("/{application_id}/onboarding/confirm")
def confirm_onboarding(
    application_id: int,
    payload: OnboardingNoteIn,
    user: User = Depends(require_role("seeker")),
    db: Session = Depends(get_db),
):
    try:
        application = onboarding_service.confirm_onboarding(
            db, user, application_id, payload.note
        )
    except onboarding_service.OnboardingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    events = application_service.list_events(db, application.id)
    return ok(
        application_service.application_to_dict(application, events),
        message="已确认入职安排",
    )


@router.post("/{application_id}/onboarding/abandon")
def abandon_onboarding(
    application_id: int,
    payload: OnboardingNoteIn,
    user: User = Depends(require_role("seeker")),
    db: Session = Depends(get_db),
):
    try:
        application = onboarding_service.abandon_onboarding(
            db, user, application_id, payload.note
        )
    except onboarding_service.OnboardingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    events = application_service.list_events(db, application.id)
    return ok(
        application_service.application_to_dict(application, events),
        message="已放弃入职",
    )


@router.post("/{application_id}/onboarding/result")
def record_onboarding_result(
    application_id: int,
    payload: OnboardingResultIn,
    user: User = Depends(require_role("employer")),
    db: Session = Depends(get_db),
):
    try:
        application = onboarding_service.record_onboarding_result(
            db,
            user,
            application_id,
            payload.result,
            payload.note,
            payload.onboarding_date,
        )
    except onboarding_service.OnboardingError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    events = application_service.list_events(db, application.id)
    return ok(
        application_service.application_to_dict(application, events),
        message="入职结果已记录",
    )
