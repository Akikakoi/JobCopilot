import json

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.llm.client import embed_one
from app.models import AgentMemory


async def save_memory(db: Session, user_id: int, content: str) -> dict:
    content = content.strip()
    if not content:
        return {"saved": False, "reason": "内容为空"}
    vector = await embed_one(content)
    memories = list(db.scalars(select(AgentMemory).where(AgentMemory.user_id == user_id)))
    for memory in memories:
        if memory.embedding and _cosine(vector, memory.embedding) > 0.95:
            memory.content = content
            memory.embedding = vector
            db.commit()
            return {"saved": True, "updated": True}
    db.add(AgentMemory(user_id=user_id, content=content, embedding=vector))
    db.commit()
    return {"saved": True}


async def search_memory(db: Session, user_id: int, query: str, top_k: int = 5) -> list[dict]:
    memories = list(
        db.scalars(
            select(AgentMemory)
            .where(AgentMemory.user_id == user_id)
            .order_by(AgentMemory.id.desc())
        )
    )
    if not memories:
        return []
    if not query.strip():
        return [{"content": m.content, "similarity": None} for m in memories[:top_k]]
    vector = await embed_one(query)
    scored = [
        (m, _cosine(vector, m.embedding)) for m in memories if m.embedding
    ]
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return [
        {"content": m.content, "similarity": round(score, 3)} for m, score in scored[:top_k]
    ]


def _cosine(a: list[float], b: list[float]) -> float:
    va, vb = np.asarray(a, dtype=np.float32), np.asarray(b, dtype=np.float32)
    denom = float(np.linalg.norm(va) * np.linalg.norm(vb))
    return 0.0 if denom == 0 else float(np.dot(va, vb) / denom)


def dump_result(data) -> str:
    """工具返回值序列化并限长，避免撑爆上下文。"""
    text = json.dumps(data, ensure_ascii=False, default=str)
    return text if len(text) <= 6000 else text[:6000] + "...(已截断)"
