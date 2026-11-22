from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_role
from app.models import Application, User
from app.schemas.common import ok
from app.schemas.job import JobCreate, JobFeedbackIn, JobUpdate
from app.services import feedback_service, job_service

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("")
async def list_jobs(
    keywords: str | None = Query(default=None),
    location: str | None = Query(default=None),
    district: str | None = Query(default=None),
    salary_min: float | None = Query(default=None),
    category: str | None = Query(default=None),
    job_type: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    jobs = await job_service.search_jobs(
        db,
        keywords=keywords,
        location=location,
        district=district,
        salary_min=salary_min,
        category=category,
        job_type=job_type,
    )
    return ok({"items": [job_service.job_to_dict(j) for j in jobs], "total": len(jobs)})


@router.get("/mine")
def my_jobs(
    user: User = Depends(require_role("employer")),
    db: Session = Depends(get_db),
):
    jobs = job_service.list_my_jobs(db, user)
    items = []
    for job in jobs:
        data = job_service.job_to_dict(job)
        data["applicant_count"] = int(
            db.scalar(select(func.count(Application.id)).where(Application.job_id == job.id)) or 0
        )
        items.append(data)
    return ok({"items": items, "total": len(items)})


@router.get("/mine/saved")
def my_saved_jobs(
    user: User = Depends(require_role("seeker")),
    db: Session = Depends(get_db),
):
    jobs = feedback_service.list_saved_jobs(db, user.id)
    items = [
        {**job_service.job_to_dict(job), "my_feedback": "save"} for job in jobs
    ]
    return ok({"items": items, "total": len(items)})


@router.get("/{job_id}/feedback")
def get_job_feedback(
    job_id: int,
    user: User = Depends(require_role("seeker")),
    db: Session = Depends(get_db),
):
    if job_service.get_job(db, job_id) is None:
        raise HTTPException(status_code=404, detail="岗位不存在")
    return ok({"job_id": job_id, "action": feedback_service.get_action(db, user.id, job_id)})


@router.post("/{job_id}/feedback")
def set_job_feedback(
    job_id: int,
    payload: JobFeedbackIn,
    user: User = Depends(require_role("seeker")),
    db: Session = Depends(get_db),
):
    if job_service.get_job(db, job_id) is None:
        raise HTTPException(status_code=404, detail="岗位不存在")
    action = feedback_service.set_action(db, user, job_id, payload.action, payload.reason)
    return ok({"job_id": job_id, "action": action}, message="反馈已记录")


@router.get("/{job_id}")
def job_detail(job_id: int, db: Session = Depends(get_db)):
    job = job_service.get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="岗位不存在")
    return ok(job_service.job_to_dict(job))


@router.post("")
def create_job(
    payload: JobCreate,
    user: User = Depends(require_role("employer")),
    db: Session = Depends(get_db),
):
    job = job_service.create_job(db, user, payload.model_dump())
    return ok(job_service.job_to_dict(job), message="岗位已发布")


@router.put("/{job_id}")
def update_job(
    job_id: int,
    payload: JobUpdate,
    user: User = Depends(require_role("employer")),
    db: Session = Depends(get_db),
):
    try:
        job = job_service.update_job(db, user, job_id, payload.model_dump(exclude_none=True))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return ok(job_service.job_to_dict(job), message="岗位已更新")
