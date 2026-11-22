from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import Company, User
from app.schemas.auth import LoginIn, PasswordChangeIn, ProfileUpdateIn, RegisterIn
from app.schemas.common import ok
from app.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


def _user_out(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "display_name": user.display_name,
        "company_name": user.company.name if user.company else None,
        "created_at": user.created_at,
    }


@router.get("/demo-accounts")
def demo_accounts(db: Session = Depends(get_db)):
    """演示用：返回公司拼音账号与中文公司名，供登录页弹窗选择（学习项目，不做账号隐私保护）。"""
    rows = db.execute(
        select(Company, User)
        .join(User, Company.owner_user_id == User.id)
        .order_by(Company.name)
    ).all()
    employers = [
        {"username": owner.username, "company_name": company.name}
        for company, owner in rows
    ]
    return ok({"password": "123456", "employers": employers})


@router.post("/register")
def register(payload: RegisterIn, db: Session = Depends(get_db)):
    exists = db.scalar(select(User).where(User.username == payload.username))
    if exists:
        raise HTTPException(status_code=409, detail="用户名已存在")

    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        role=payload.role,
        display_name=payload.display_name,
    )
    db.add(user)
    db.flush()

    if payload.role == "employer":
        db.add(
            Company(
                owner_user_id=user.id,
                name=payload.company_name or f"{payload.display_name}的公司",
                industry="互联网",
                description="",
            )
        )

    db.commit()
    db.refresh(user)
    token = create_access_token(user.id, user.role)
    return ok({"access_token": token, "token_type": "bearer", "user": _user_out(user)})


@router.post("/login")
def login(payload: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == payload.username))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token = create_access_token(user.id, user.role)
    return ok({"access_token": token, "token_type": "bearer", "user": _user_out(user)})


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return ok(_user_out(user))


@router.put("/me")
def update_me(
    payload: ProfileUpdateIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user.display_name = payload.display_name
    db.commit()
    db.refresh(user)
    return ok(_user_out(user), message="资料已更新")


@router.post("/change-password")
def change_password(
    payload: PasswordChangeIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(payload.old_password, user.password_hash):
        raise HTTPException(status_code=400, detail="原密码不正确")
    user.password_hash = hash_password(payload.new_password)
    db.commit()
    return ok(message="密码已修改")
