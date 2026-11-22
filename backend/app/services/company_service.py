"""公司资料与公司主页：招聘方维护本公司信息，求职者查看公司公开信息。"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Company, Job, User
from app.services.job_service import job_to_dict


def get_owned_company(db: Session, user: User) -> Company | None:
    return db.scalar(select(Company).where(Company.owner_user_id == user.id))


def ensure_company(db: Session, user: User) -> Company:
    company = get_owned_company(db, user)
    if company is not None:
        return company
    company = Company(
        owner_user_id=user.id,
        name=f"{user.display_name}的公司",
        industry="互联网",
        description="",
    )
    db.add(company)
    db.commit()
    db.refresh(company)
    return company


def company_to_dict(company: Company) -> dict:
    return {
        "id": company.id,
        "name": company.name,
        "industry": company.industry or "",
        "description": company.description or "",
    }


def update_company(db: Session, user: User, data: dict) -> Company:
    company = ensure_company(db, user)
    for key in ("name", "industry", "description"):
        if key in data and data[key] is not None:
            setattr(company, key, data[key])
    db.commit()
    db.refresh(company)
    return company


def company_detail(db: Session, company_id: int) -> dict | None:
    company = db.get(Company, company_id)
    if company is None:
        return None
    jobs = list(
        db.scalars(
            select(Job)
            .where(Job.company_id == company.id, Job.status == "open")
            .order_by(Job.id.desc())
        )
    )
    return {
        **company_to_dict(company),
        "open_job_count": len(jobs),
        "jobs": [job_to_dict(job) for job in jobs],
    }
