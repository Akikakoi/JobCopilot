from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_role
from app.models import User
from app.schemas.common import ok
from app.schemas.interview import InterviewAnswerIn, InterviewCreateIn
from app.services import interview_service

router = APIRouter(prefix="/interviews", tags=["interviews"])


@router.post("")
async def create_interview(
    payload: InterviewCreateIn,
    user: User = Depends(require_role("seeker")),
    db: Session = Depends(get_db),
):
    try:
        interview = await interview_service.create_interview(db, user, payload.job_id)
    except interview_service.InterviewError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(interview_service.interview_to_dict(interview), message="面试已生成")


@router.get("/mine")
def my_interviews(
    user: User = Depends(require_role("seeker")),
    db: Session = Depends(get_db),
):
    interviews = interview_service.list_my_interviews(db, user)
    return ok(
        {
            "items": [
                {
                    "id": item.id,
                    "job_id": item.job_id,
                    "job_title": item.job.title if item.job else "",
                    "company_name": item.job.company.name if item.job and item.job.company else "",
                    "status": item.status,
                    "overall_score": (item.report or {}).get("overall_score")
                    if item.report
                    else None,
                    "question_count": len((item.plan or {}).get("questions") or []),
                    "answered_count": len(item.answers or []),
                    "created_at": item.created_at,
                }
                for item in interviews
            ]
        }
    )


@router.get("/application/{application_id}")
def application_report(
    application_id: int,
    user: User = Depends(require_role("employer")),
    db: Session = Depends(get_db),
):
    try:
        interview = interview_service.application_report(db, user, application_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if interview is None:
        return ok(None)
    return ok(interview_service.interview_to_dict(interview))


@router.get("/{interview_id}")
def interview_detail(
    interview_id: int,
    user: User = Depends(require_role("seeker")),
    db: Session = Depends(get_db),
):
    try:
        owned = interview_service.get_owned_interview(db, user, interview_id)
    except PermissionError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ok(interview_service.interview_to_dict(owned))


@router.post("/{interview_id}/answers")
def submit_answer(
    interview_id: int,
    payload: InterviewAnswerIn,
    user: User = Depends(require_role("seeker")),
    db: Session = Depends(get_db),
):
    try:
        interview = interview_service.submit_answer(
            db, user, interview_id, payload.question_id, payload.answer
        )
    except PermissionError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except interview_service.InterviewError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(interview_service.interview_to_dict(interview), message="回答已保存")


@router.post("/{interview_id}/complete")
async def complete_interview(
    interview_id: int,
    user: User = Depends(require_role("seeker")),
    db: Session = Depends(get_db),
):
    try:
        interview = await interview_service.complete_interview(db, user, interview_id)
    except PermissionError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except interview_service.InterviewError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ok(interview_service.interview_to_dict(interview), message="面试报告已生成")
