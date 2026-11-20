from sqlalchemy.orm import Session

from app.matching import pipeline
from app.matching.rules import score_resume_job
from app.models import Job, Resume, User
from app.services import application_service


async def rank_candidates(db: Session, user: User, job_id: int) -> list[dict]:
    """候选人排序：规则分 + 向量相似度 + 已缓存的 agent 解读。"""
    applications = application_service.list_job_applications(db, user, job_id)
    job = db.get(Job, job_id)
    if job is None:
        return []
    await pipeline.ensure_job_embeddings(db, [job])

    items: list[dict] = []
    for application in applications:
        resume = db.get(Resume, application.resume_id)
        if resume is None:
            continue
        scoring = score_resume_job(resume.structured or {}, job)
        similarity = (
            pipeline.cosine_similarity(resume.embedding, job.embedding)
            if resume.embedding and job.embedding
            else 0.0
        )
        candidate = db.get(User, application.user_id)
        items.append(
            {
                "application_id": application.id,
                "user_id": application.user_id,
                "candidate_name": (resume.structured or {}).get("name")
                or (candidate.display_name if candidate else ""),
                "structured": resume.structured or {},
                "status": application.status,
                "match_score": scoring["total"],
                "similarity": round(similarity, 4),
                "breakdown": scoring["breakdown"],
                "match_explanation": application.match_explanation,
            }
        )
    items.sort(key=lambda item: item["match_score"], reverse=True)
    return items
