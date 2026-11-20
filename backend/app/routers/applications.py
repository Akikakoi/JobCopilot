from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_role
from app.models import User
from app.schemas.application import ApplicationCreate, ApplicationStatusIn
from app.schemas.common import ok
from app.services import application_service

router = APIRouter(prefix="/applications", tags=["applications"])


@router.post("")
def create_application(
    payload: ApplicationCreate,
    user: User = Depends(require_role("seeker")),
    db: Session = Depends(get_db),
):
    try:
        application = application_service.apply_to_job(
            db, user, payload.job_id, payload.cover_letter, payload.resume_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(
        application_service.application_to_dict(application), message="投递成功"
    )


@router.get("/mine")
def my_applications(
    user: User = Depends(require_role("seeker")),
    db: Session = Depends(get_db),
):
    apps = application_service.list_my_applications(db, user)
    return ok({"items": [application_service.application_to_dict(a) for a in apps]})


@router.get("/job/{job_id}")
def job_applications(
    job_id: int,
    user: User = Depends(require_role("employer")),
    db: Session = Depends(get_db),
):
    try:
        apps = application_service.list_job_applications(db, user, job_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return ok({"items": [application_service.application_to_dict(a) for a in apps]})


@router.patch("/{application_id}/status")
def update_application_status(
    application_id: int,
    payload: ApplicationStatusIn,
    user: User = Depends(require_role("employer")),
    db: Session = Depends(get_db),
):
    try:
        application = application_service.update_status(
            db, user, application_id, payload.status, payload.note
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return ok(application_service.application_to_dict(application), message="状态已更新")
