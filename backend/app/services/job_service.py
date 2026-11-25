from sqlalchemy import select
from sqlalchemy.orm import Session

from app.job_taxonomy import derive_subcategory
from app.llm.client import embed_texts
from app.models import Company, Job, User
from app.utils import cosine_similarity


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
        "district": job.district or "",
        "category": job.category or "",
        "subcategory": derive_subcategory(job.category or "", job.title),
        "job_type": job.job_type or "",
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
    district: str | None = None,
    salary_min: float | None = None,
    category: str | None = None,
    job_type: str | None = None,
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
    if district:
        jobs = [j for j in jobs if j.district == district]
    if salary_min:
        jobs = [j for j in jobs if (j.salary_max or 0) >= salary_min]
    if category:
        jobs = [j for j in jobs if j.category == category]
    if job_type:
        jobs = [j for j in jobs if j.job_type == job_type]
    return jobs


# ==================== 混合检索：关键词 + 语义 ====================
SEMANTIC_LIMIT = 12  # 语义补充结果上限
SEMANTIC_MIN_SIMILARITY = 0.40  # 低于该余弦相似度不补充
_QUERY_CACHE_SIZE = 200
_query_embedding_cache: dict[str, list[float]] = {}


async def _embed_query(text: str) -> list[float]:
    key = " ".join(text.lower().split())
    cached = _query_embedding_cache.get(key)
    if cached is not None:
        return cached
    vector = (await embed_texts([text]))[0]
    if len(_query_embedding_cache) >= _QUERY_CACHE_SIZE:
        _query_embedding_cache.pop(next(iter(_query_embedding_cache)))
    _query_embedding_cache[key] = vector
    return vector


def _lexical_rank(job: Job, kw: str) -> int:
    """关键词命中位置：标题 > 技能 > 描述/公司"""
    if kw in job.title.lower():
        return 3
    if any(kw in s.lower() for s in (job.required_skills or []) + (job.preferred_skills or [])):
        return 2
    if kw in (job.description or "").lower() or (job.company and kw in job.company.name.lower()):
        return 1
    return 0


async def search_jobs(
    db: Session,
    keywords: str | None = None,
    location: str | None = None,
    district: str | None = None,
    salary_min: float | None = None,
    category: str | None = None,
    job_type: str | None = None,
) -> list[Job]:
    """关键词精确命中优先，再用语义相似度补齐近义岗位（去重后追加）。"""
    filters = {
        "location": location,
        "district": district,
        "salary_min": salary_min,
        "category": category,
        "job_type": job_type,
    }
    matched = list_jobs(db, keywords=keywords, **filters)
    query = (keywords or "").strip()
    if len(query) < 2:
        return matched

    # 关键词结果按命中位置排序：标题命中优先，其次技能，最后描述/公司
    kw = query.lower()
    matched.sort(key=lambda job: (_lexical_rank(job, kw), job.id), reverse=True)

    pool = list_jobs(db, keywords=None, **filters)
    candidates = [job for job in pool if job.embedding]
    if not candidates:
        return matched

    try:
        vector = await _embed_query(query)
    except Exception:
        # embedding 不可用时退回纯关键词结果，不影响搜索
        return matched

    scored = [(cosine_similarity(vector, job.embedding), job) for job in candidates]
    scored.sort(key=lambda pair: pair[0], reverse=True)

    seen = {job.id for job in matched}
    extra = [
        job
        for similarity, job in scored
        if similarity >= SEMANTIC_MIN_SIMILARITY and job.id not in seen
    ][:SEMANTIC_LIMIT]
    return matched + extra


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
    "district",
    "category",
    "job_type",
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
