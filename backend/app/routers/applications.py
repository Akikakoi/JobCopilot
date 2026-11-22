from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.deps import require_role
from app.models import User
from app.schemas.application import ApplicationCreate, ApplicationStatusIn
from app.schemas.common import ok
from app.services import application_service, interview_invite_service, offer_service

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
    app_ids = [a.id for a in apps]
    events = application_service.events_for_applications(db, app_ids)
    offers = offer_service.group_offers(db, app_ids)
    invites = interview_invite_service.group_invites(db, app_ids)
    return ok(
        {
            "items": [
                application_service.application_to_dict(
                    a,
                    events.get(a.id, []),
                    offer=offers.get(a.id),
                    invites=invites.get(a.id, []),
                )
                for a in apps
            ]
        }
    )


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


@router.get("/{application_id}/events")
def application_events(
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
    events = application_service.list_events(db, application_id)
    return ok(
        {"items": [application_service.event_to_dict(item) for item in events]}
    )


@router.get("/{application_id}/resume-file")
def candidate_resume_file(
    application_id: int,
    user: User = Depends(require_role("employer")),
    db: Session = Depends(get_db),
):
    try:
        record = application_service.get_candidate_resume_file(db, user, application_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if record is None:
        raise HTTPException(status_code=404, detail="该候选人没有上传原始简历文件")
    path = Path(settings.upload_dir) / record.stored_path
    if not path.exists():
        raise HTTPException(status_code=404, detail="候选人原简历文件已丢失")
    return FileResponse(path, media_type=record.content_type, filename=record.file_name)


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
