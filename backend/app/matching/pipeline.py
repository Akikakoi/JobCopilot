import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.llm.client import chat_completion, embed_texts, message_text
from app.matching.rules import score_resume_job
from app.models import Job, Resume, User
from app.services import feedback_service
from app.services.job_service import job_embedding_text, job_to_dict
from app.utils import cosine_similarity

RECALL_TOP_N = 20

EXPLAIN_SYSTEM = """你是资深招聘顾问。基于「简历结构化数据」「岗位结构化数据」「规则评分明细」，
输出对这位候选人相对该岗位的匹配解读，只输出 JSON：
{
  "summary": "一句话结论，30 字以内",
  "reasons": ["匹配理由，最多 3 条"],
  "gaps": ["主要差距，最多 3 条"],
  "suggestions": ["可执行的补齐建议，最多 3 条"]
}
要求：结论必须基于给定数据，不得编造简历里没有的经历。"""


async def ensure_job_embeddings(db: Session, jobs: list[Job]) -> None:
    pending = [job for job in jobs if not job.embedding]
    if not pending:
        return
    vectors = await embed_texts([job_embedding_text(job) for job in pending])
    for job, vector in zip(pending, vectors, strict=True):
        job.embedding = vector
    db.commit()


async def match_jobs_for_resume(
    db: Session,
    resume: Resume,
    top_n: int = RECALL_TOP_N,
    max_results: int | None = None,
    user: User | None = None,
) -> list[dict]:
    if not resume.embedding:
        raise ValueError("简历尚未生成向量，请先重新解析简历")

    jobs = list(
        db.scalars(select(Job).where(Job.status == "open").order_by(Job.id.desc()))
    )
    if not jobs:
        return []
    await ensure_job_embeddings(db, jobs)

    # ① 向量召回
    scored_pairs = [
        (cosine_similarity(resume.embedding, job.embedding), job) for job in jobs if job.embedding
    ]
    scored_pairs.sort(key=lambda pair: pair[0], reverse=True)
    recalled = scored_pairs[:top_n]

    # ② 规则精排
    results: list[dict] = []
    for similarity, job in recalled:
        scoring = score_resume_job(resume.structured or {}, job)
        results.append(
            {
                **job_to_dict(job),
                "similarity": round(similarity, 4),
                "match_score": scoring["total"],
                "breakdown": scoring["breakdown"],
            }
        )
    results.sort(key=lambda item: item["match_score"], reverse=True)

    # 反馈闭环：仅调整展示排序，match_score 保持为原始规则分
    feedback = (
        feedback_service.actions_for(db, user.id, [item["id"] for item in results])
        if user
        else {}
    )
    saved_companies = {
        item["company_id"] for item in results if feedback.get(item["id"]) == "save"
    }
    for item in results:
        action = feedback.get(item["id"])
        if action == "dislike":
            adjust = -15.0
        elif action == "save":
            adjust = 10.0
        elif item["company_id"] in saved_companies:
            adjust = 5.0
        else:
            adjust = 0.0
        item["my_feedback"] = action
        # rank_score 仅用于排序，可以超过 100；展示仍用原始 match_score
        item["rank_score"] = round(max(0.0, item["match_score"] + adjust), 1)
    results.sort(key=lambda item: item["rank_score"], reverse=True)

    # ③ 解读由调用方按需触发（explain_match），避免列表页把 LLM 打满
    return results[:max_results] if max_results else results


async def explain_match(resume: Resume, job: Job, scoring: dict) -> dict:
    payload = {
        "简历": resume.structured or {},
        "岗位": job_to_dict(job),
        "规则评分明细": scoring,
    }
    reply = await chat_completion(
        [
            {"role": "system", "content": EXPLAIN_SYSTEM},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False, default=str)},
        ],
        temperature=0.3,
        response_format={"type": "json_object"},
    )
    content = message_text(reply.get("content"))
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return {
            "summary": "匹配解读生成失败，请重试",
            "reasons": [],
            "gaps": [],
            "suggestions": [],
        }
    return {
        "summary": data.get("summary") or "",
        "reasons": data.get("reasons") or [],
        "gaps": data.get("gaps") or [],
        "suggestions": data.get("suggestions") or [],
    }
