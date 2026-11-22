from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user, require_role
from app.models import User
from app.schemas.common import ok
from app.schemas.company import CompanyUpdateIn
from app.services import company_service

router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("/mine")
def my_company(
    user: User = Depends(require_role("employer")),
    db: Session = Depends(get_db),
):
    company = company_service.ensure_company(db, user)
    return ok(company_service.company_to_dict(company))


@router.put("/mine")
def update_my_company(
    payload: CompanyUpdateIn,
    user: User = Depends(require_role("employer")),
    db: Session = Depends(get_db),
):
    company = company_service.update_company(db, user, payload.model_dump())
    return ok(company_service.company_to_dict(company), message="公司资料已更新")


@router.get("/{company_id}")
def company_detail(
    company_id: int,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    detail = company_service.company_detail(db, company_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="公司不存在")
    return ok(detail)
