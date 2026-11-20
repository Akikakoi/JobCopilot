from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Company, Job, User


def job_to_dict(job: Job) -> dict:
    company = job.company
    return {
        "id": job.id,
        "company_id": job.company_id,
        "company_name": company.name if company else "",
        "company_industry": company.industry if company else "",
        "title": job.title,
        "description": job.description,
        "required_skills": job.required_skills or [],
        "preferred_skills": job.preferred_skills or [],
        "experience_min": job.experience_min,
        "experience_max": job.experience_max,
        "location": job.location,
        "salary_min": job.salary_min,
        "salary_max": job.salary_max,
        "status": job.status,
        "created_at": job.created_at,
    }


def get_job(db: Session, job_id: int) -> Job | None:
    return db.get(Job, job_id)


def list_jobs(
    db: Session,
    keywords: str | None = None,
    location: str | None = None,
    salary_min: float | None = None,
    include_closed: bool = False,
) -> list[Job]:
    stmt = select(Job)
    if not include_closed:
        stmt = stmt.where(Job.status == "open")
    jobs = list(db.scalars(stmt.order_by(Job.id.desc())))

    if keywords:
        kw = keywords.lower().strip()
        jobs = [
            j
            for j in jobs
            if kw in j.title.lower()
            or kw in (j.description or "").lower()
            or any(kw in s.lower() for s in (j.required_skills or []) + (j.preferred_skills or []))
            or kw in (j.company.name.lower() if j.company else "")
        ]
    if location:
        loc = location.strip()
        jobs = [j for j in jobs if loc in j.location or j.location in ("不限", "远程")]
    if salary_min:
        jobs = [j for j in jobs if (j.salary_max or 0) >= salary_min]
    return jobs


def owned_company(db: Session, user: User) -> Company | None:
    return db.scalar(select(Company).where(Company.owner_user_id == user.id))


def create_job(db: Session, user: User, data: dict) -> Job:
    company = owned_company(db, user)
    if company is None:
        company = Company(owner_user_id=user.id, name=f"{user.display_name}的公司", industry="互联网")
        db.add(company)
        db.flush()

    job = Job(company_id=company.id, **data)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


EDITABLE_JOB_FIELDS = {
    "title",
    "description",
    "required_skills",
    "preferred_skills",
    "experience_min",
    "experience_max",
    "location",
    "salary_min",
    "salary_max",
    "status",
}


def update_job(db: Session, user: User, job_id: int, data: dict) -> Job:
    job = db.get(Job, job_id)
    if job is None or job.company is None or job.company.owner_user_id != user.id:
        raise PermissionError("岗位不存在或无权修改")
    for key, value in data.items():
        if value is not None and key in EDITABLE_JOB_FIELDS:
            setattr(job, key, value)
    if {"title", "description", "required_skills"} & data.keys():
        job.embedding = None  # 文案变更后向量失效，下次匹配时重算
    db.commit()
    db.refresh(job)
    return job


def list_my_jobs(db: Session, user: User) -> list[Job]:
    company = owned_company(db, user)
    if company is None:
        return []
    return list(
        db.scalars(select(Job).where(Job.company_id == company.id).order_by(Job.id.desc()))
    )


def job_embedding_text(job: Job) -> str:
    parts = [
        job.title,
        f"地点：{job.location}",
        f"经验：{job.experience_min}-{job.experience_max} 年",
        f"薪资：{job.salary_min}-{job.salary_max}K",
        "必需技能：" + "、".join(job.required_skills or []),
        "加分技能：" + "、".join(job.preferred_skills or []),
        job.description or "",
    ]
    return "\n".join(p for p in parts if p)
