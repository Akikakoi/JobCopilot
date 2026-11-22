from sqlalchemy import select
from sqlalchemy.orm import Session

from app.matching import pipeline
from app.matching.rules import score_resume_job
from app.models import Application, Company, Job, Resume, User
from app.services import application_service, interview_invite_service, offer_service


def _candidate_item(db: Session, application: Application, job: Job | None) -> dict | None:
    if job is None:
        return None
    resume = db.get(Resume, application.resume_id)
    if resume is None:
        return None
    scoring = score_resume_job(resume.structured or {}, job)
    similarity = (
        pipeline.cosine_similarity(resume.embedding, job.embedding)
        if resume.embedding and job.embedding
        else 0.0
    )
    candidate = db.get(User, application.user_id)
    return {
        "application_id": application.id,
        "user_id": application.user_id,
        "job_id": job.id,
        "job_title": job.title,
        "candidate_name": (resume.structured or {}).get("name")
        or (candidate.display_name if candidate else ""),
        "structured": resume.structured or {},
        "status": application.status,
        "status_label": application_service.STATUS_LABELS.get(
            application.status, application.status
        ),
        "status_note": application.status_note or "",
        "onboarding": application_service.onboarding_to_dict(application),
        "cover_letter": application.cover_letter or "",
        "has_resume_file": bool(resume.upload_file),
        "resume_file_name": resume.upload_file.file_name if resume.upload_file else "",
        "match_score": scoring["total"],
        "similarity": round(similarity, 4),
        "breakdown": scoring["breakdown"],
        "match_explanation": application.match_explanation,
    }


def _attach_pipeline(db: Session, items: list[dict]) -> None:
    app_ids = [item["application_id"] for item in items]
    offers = offer_service.group_offers(db, app_ids)
    invites = interview_invite_service.group_invites(db, app_ids)
    for item in items:
        item["offer"] = offers.get(item["application_id"])
        item["interview_invites"] = invites.get(item["application_id"], [])


async def rank_candidates(db: Session, user: User, job_id: int) -> list[dict]:
    """候选人排序：规则分 + 向量相似度 + 已缓存的 agent 解读。"""
    applications = application_service.list_job_applications(db, user, job_id)
    job = db.get(Job, job_id)
    if job is None:
        return []
    await pipeline.ensure_job_embeddings(db, [job])

    items: list[dict] = []
    for application in applications:
        item = _candidate_item(db, application, job)
        if item is not None:
            items.append(item)
    items.sort(key=lambda item: item["match_score"], reverse=True)
    _attach_pipeline(db, items)
    return items


async def rank_all_candidates(db: Session, user: User) -> list[dict]:
    """本公司全部岗位的候选人，按匹配分统一排序（用于看板「全部岗位」）。"""
    applications = list(
        db.scalars(
            select(Application)
            .join(Job, Application.job_id == Job.id)
            .join(Company, Job.company_id == Company.id)
            .where(Company.owner_user_id == user.id)
            .order_by(Application.match_score.desc(), Application.id.desc())
        )
    )
    if not applications:
        return []

    job_ids = {application.job_id for application in applications}
    jobs = {
        job.id: job
        for job in db.scalars(select(Job).where(Job.id.in_(job_ids)))
    }
    await pipeline.ensure_job_embeddings(db, list(jobs.values()))

    items: list[dict] = []
    for application in applications:
        item = _candidate_item(db, application, jobs.get(application.job_id))
        if item is not None:
            items.append(item)
    items.sort(key=lambda item: item["match_score"], reverse=True)
    _attach_pipeline(db, items)
    return items
