import json
import logging
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent.duel import stream_duel
from app.agent.runtime import AgentRuntime
from app.db import SessionLocal, get_db
from app.deps import get_current_user, require_role
from app.models import AgentMessage, AgentSession, Application, Job, User
from app.schemas.common import ok

router = APIRouter(prefix="/agent", tags=["agent"])
logger = logging.getLogger(__name__)


class SessionCreate(BaseModel):
    agent_type: str | None = Field(default=None, description="seeker / employer，缺省取用户角色")
    title: str | None = None


class ChatIn(BaseModel):
    content: str = Field(min_length=1)


class DuelIn(BaseModel):
    job_id: int
    application_id: int
    rounds: int = Field(default=2, ge=1, le=3)


def _session_of(db: Session, user: User, session_id: int) -> AgentSession:
    session = db.get(AgentSession, session_id)
    if session is None or session.user_id != user.id:
        raise HTTPException(status_code=404, detail="会话不存在")
    return session


@router.post("/sessions")
def create_session(
    payload: SessionCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    agent_type = payload.agent_type or user.role
    if agent_type != user.role:
        raise HTTPException(status_code=403, detail="当前角色无法创建该类型会话")
    session = AgentSession(
        user_id=user.id, agent_type=agent_type, title=payload.title or "新会话"
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return ok(
        {
            "id": session.id,
            "agent_type": session.agent_type,
            "title": session.title,
            "created_at": session.created_at,
        }
    )


@router.get("/sessions")
def list_sessions(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sessions = list(
        db.scalars(
            select(AgentSession)
            .where(AgentSession.user_id == user.id)
            .order_by(AgentSession.id.desc())
        )
    )
    return ok(
        {
            "items": [
                {
                    "id": s.id,
                    "agent_type": s.agent_type,
                    "title": s.title,
                    "created_at": s.created_at,
                }
                for s in sessions
            ]
        }
    )


@router.get("/sessions/{session_id}/messages")
def session_messages(
    session_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _session_of(db, user, session_id)
    messages = list(
        db.scalars(
            select(AgentMessage)
            .where(AgentMessage.session_id == session_id)
            .order_by(AgentMessage.id.asc())
        )
    )
    return ok(
        {
            "items": [
                {
                    "id": m.id,
                    "role": m.role,
                    "content": m.content,
                    "tool_calls": m.tool_calls,
                    "tool_call_id": m.tool_call_id,
                    "created_at": m.created_at,
                }
                for m in messages
            ]
        }
    )


@router.post("/duel")
def duel(
    payload: DuelIn,
    user: User = Depends(require_role("employer")),
    db: Session = Depends(get_db),
):
    """彩蛋：求职者 Agent × 招聘方 Agent 自主对谈（SSE 流式）。"""
    job = db.get(Job, payload.job_id)
    application = db.get(Application, payload.application_id)
    if job is None or application is None or application.job_id != job.id:
        raise HTTPException(status_code=404, detail="岗位或投递记录不存在")
    if job.company is None or job.company.owner_user_id != user.id:
        raise HTTPException(status_code=403, detail="无权对该候选人发起对谈")

    employer_id = user.id
    job_id = payload.job_id
    application_id = payload.application_id
    rounds = payload.rounds

    async def event_stream() -> AsyncIterator[str]:
        stream_db = SessionLocal()
        try:
            employer = stream_db.get(User, employer_id)
            job_row = stream_db.get(Job, job_id)
            application_row = stream_db.get(Application, application_id)
            if employer is None or job_row is None or application_row is None:
                yield f"data: {json.dumps({'type': 'error', 'message': '数据已失效'}, ensure_ascii=False)}\n\n"
                return
            async for event in stream_duel(
                stream_db, employer, job_row, application_row, rounds=rounds
            ):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception:  # noqa: BLE001
            logger.exception("duel 对谈异常 job=%s application=%s", job_id, application_id)
            yield f"data: {json.dumps({'type': 'error', 'message': '对谈服务异常，请稍后再试'}, ensure_ascii=False)}\n\n"
        finally:
            stream_db.close()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/sessions/{session_id}/chat")
def chat(
    session_id: int,
    payload: ChatIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = _session_of(db, user, session_id)
    if session.agent_type != user.role:
        raise HTTPException(status_code=403, detail="会话类型与当前角色不符")

    user_id = user.id
    content = payload.content

    async def event_stream() -> AsyncIterator[str]:
        stream_db = SessionLocal()
        try:
            stream_user = stream_db.get(User, user_id)
            stream_session = stream_db.get(AgentSession, session_id)
            if stream_user is None or stream_session is None:
                yield f"data: {json.dumps({'type': 'error', 'message': '会话已失效'}, ensure_ascii=False)}\n\n"
                return
            runtime = AgentRuntime(stream_db, stream_user, stream_session)
            async for event in runtime.stream(content):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception:  # noqa: BLE001
            logger.exception("agent 流式对话异常 session=%s", session_id)
            yield f"data: {json.dumps({'type': 'error', 'message': '对话服务异常，请稍后再试'}, ensure_ascii=False)}\n\n"
        finally:
            stream_db.close()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
