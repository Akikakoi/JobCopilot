from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.deps import require_role
from app.models import Resume, User
from app.schemas.common import ok
from app.schemas.resume import (
    DiagnoseIn,
    JobIntentIn,
    OptimizeApplyIn,
    OptimizeIn,
    ResumePasteIn,
)
from app.services import resume_parser, resume_service

router = APIRouter(prefix="/resumes", tags=["resumes"])

MAX_FILE_SIZE = 5 * 1024 * 1024


class ReparseIn(BaseModel):
    text: str | None = None


@router.get("/mine")
def get_my_resume(
    user: User = Depends(require_role("seeker")),
    db: Session = Depends(get_db),
):
    resume = db.scalar(select(Resume).where(Resume.user_id == user.id))
    return ok(resume_service.resume_to_dict(resume) if resume else None)


@router.post("/upload")
async def upload_resume(
    file: UploadFile = File(...),
    user: User = Depends(require_role("seeker")),
    db: Session = Depends(get_db),
):
    if file.size and file.size > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="文件超过 5MB 限制")
    data = await file.read()
    if len(data) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="文件超过 5MB 限制")
    try:
        raw_text = resume_parser.extract_text(file.filename or "", data)
        resume = await resume_service.save_resume(db, user.id, raw_text, "upload")
    except resume_parser.ResumeParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except resume_service.ResumeExtractionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    resume_service.save_resume_file(db, resume, file.filename or "", data)
    return ok(resume_service.resume_to_dict(resume), message="简历解析完成")


@router.get("/mine/file")
def get_my_resume_file(
    user: User = Depends(require_role("seeker")),
    db: Session = Depends(get_db),
):
    record = resume_service.get_resume_file(db, user.id)
    if record is None:
        raise HTTPException(status_code=404, detail="还没有上传过简历文件")
    path = Path(settings.upload_dir) / record.stored_path
    if not path.exists():
        raise HTTPException(status_code=404, detail="简历原文件已丢失，请重新上传")
    return FileResponse(path, media_type=record.content_type, filename=record.file_name)


@router.post("/paste")
async def paste_resume(
    payload: ResumePasteIn,
    user: User = Depends(require_role("seeker")),
    db: Session = Depends(get_db),
):
    try:
        resume = await resume_service.save_resume(db, user.id, payload.text.strip(), "paste")
    except resume_service.ResumeExtractionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ok(resume_service.resume_to_dict(resume), message="简历解析完成")


@router.get("/versions")
def list_versions(
    user: User = Depends(require_role("seeker")),
    db: Session = Depends(get_db),
):
    versions = resume_service.list_versions(db, user.id)
    return ok({"items": [resume_service.version_to_dict(item) for item in versions]})


@router.post("/versions/{version_id}/restore")
async def restore_version(
    version_id: int,
    user: User = Depends(require_role("seeker")),
    db: Session = Depends(get_db),
):
    try:
        resume = await resume_service.restore_version(db, user.id, version_id)
    except PermissionError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(resume_service.resume_to_dict(resume), message="已回滚到该版本")


@router.post("/optimize")
async def optimize(
    payload: OptimizeIn,
    user: User = Depends(require_role("seeker")),
    db: Session = Depends(get_db),
):
    try:
        result = await resume_service.optimize_resume(
            db,
            user.id,
            job_id=payload.job_id,
            category=payload.category,
            subcategory=payload.subcategory,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(result)


@router.post("/optimize/apply")
async def apply_optimization(
    payload: OptimizeApplyIn,
    user: User = Depends(require_role("seeker")),
    db: Session = Depends(get_db),
):
    try:
        resume = await resume_service.apply_optimization(
            db,
            user.id,
            payload.skills_to_add,
            job_id=payload.job_id,
            category=payload.category,
            subcategory=payload.subcategory,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(resume_service.resume_to_dict(resume), message="已应用优化并生成新版本")


@router.get("/intent")
def get_job_intent(
    user: User = Depends(require_role("seeker")),
    db: Session = Depends(get_db),
):
    resume = db.scalar(select(Resume).where(Resume.user_id == user.id))
    return ok(resume_service.job_intent_to_dict(resume))


@router.put("/intent")
async def put_job_intent(
    payload: JobIntentIn,
    user: User = Depends(require_role("seeker")),
    db: Session = Depends(get_db),
):
    try:
        resume = await resume_service.save_job_intent(
            db,
            user.id,
            target_title=payload.target_title,
            categories=payload.categories,
            subcategories=payload.subcategories,
            locations=payload.locations,
            districts=payload.districts,
            salary_min=payload.salary_min,
            salary_max=payload.salary_max,
            job_types=payload.job_types,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(resume_service.job_intent_to_dict(resume), message="求职意向已更新")


@router.post("/diagnose")
async def diagnose(
    payload: DiagnoseIn,
    user: User = Depends(require_role("seeker")),
    db: Session = Depends(get_db),
):
    try:
        result = await resume_service.diagnose_job_fit(
            db,
            user.id,
            category=payload.category,
            subcategory=payload.subcategory,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(result)


@router.put("/mine")
async def reparse_resume(
    payload: ReparseIn,
    user: User = Depends(require_role("seeker")),
    db: Session = Depends(get_db),
):
    resume = db.scalar(select(Resume).where(Resume.user_id == user.id))
    text = (payload.text or (resume.raw_text if resume else "") or "").strip()
    if len(text) < 20:
        raise HTTPException(status_code=400, detail="简历内容过短，无法重新解析")
    try:
        resume = await resume_service.save_resume(db, user.id, text, resume.source if resume else "paste")
    except resume_service.ResumeExtractionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ok(resume_service.resume_to_dict(resume), message="重新解析完成")
