from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_role
from app.matching import pipeline
from app.matching.rules import score_resume_job
from app.models import Application, Resume, User
from app.schemas.common import ok
from app.services import candidate_service, job_service

router = APIRouter(prefix="/match", tags=["match"])


def _require_resume(db: Session, user: User) -> Resume:
    resume = db.scalar(select(Resume).where(Resume.user_id == user.id))
    if resume is None:
        raise HTTPException(status_code=400, detail="请先上传简历")
    if not resume.embedding:
        raise HTTPException(status_code=400, detail="简历缺少向量，请重新解析简历")
    return resume


@router.get("/jobs-for-me")
async def jobs_for_me(
    top_n: int = Query(default=20, ge=1, le=50),
    limit: int = Query(default=20, ge=1, le=50),
    user: User = Depends(require_role("seeker")),
    db: Session = Depends(get_db),
):
    resume = _require_resume(db, user)
    items = await pipeline.match_jobs_for_resume(
        db, resume, top_n=top_n, max_results=limit, user=user
    )
    return ok({"items": items, "total": len(items), "resume_id": resume.id})


@router.get("/job/{job_id}")
async def job_match_detail(
    job_id: int,
    user: User = Depends(require_role("seeker")),
    db: Session = Depends(get_db),
):
    resume = _require_resume(db, user)
    job = job_service.get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="岗位不存在")

    scoring = score_resume_job(resume.structured or {}, job)
    application = db.scalar(
        select(Application).where(Application.user_id == user.id, Application.job_id == job_id)
    )
    if application and application.match_explanation:
        explanation = application.match_explanation
    else:
        explanation = await pipeline.explain_match(resume, job, scoring)
        if application:
            application.match_score = scoring["total"]
            application.match_explanation = explanation
            db.commit()

    return ok(
        {
            "job": job_service.job_to_dict(job),
            "match_score": scoring["total"],
            "breakdown": scoring["breakdown"],
            "explanation": explanation,
            "applied": application is not None,
            "application_id": application.id if application else None,
        }
    )


@router.get("/job/{job_id}/candidates")
async def job_candidates(
    job_id: int,
    user: User = Depends(require_role("employer")),
    db: Session = Depends(get_db),
):
    try:
        items = await candidate_service.rank_candidates(db, user, job_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return ok({"items": items, "total": len(items)})
