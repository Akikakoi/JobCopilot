import hashlib
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.llm.client import chat_completion, embed_texts, message_text
from app.matching.rules import score_resume_job
from app.models import Job, MatchExplanation, Resume, User
from app.services import feedback_service
from app.services.job_service import job_embedding_text, job_to_dict
from app.utils import cosine_similarity as _cosine_similarity

RECALL_TOP_N = 20

# 兼容旧引用：candidate_service 等模块从 pipeline 取 cosine_similarity
cosine_similarity = _cosine_similarity

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

    structured = resume.structured or {}
    expectations = structured.get("expectations") or {}
    intent_cities = [c for c in (expectations.get("locations") or []) if str(c).strip()]

    # ① 向量召回 + 意向城市配额
    # 先按意向城市分桶，每个城市保底名额，避免同城岗位被纯相似度挤出窗口；
    # 剩余名额给全局最高相似度岗位。城市匹配与 rules._location_score 同口径。
    def _city_of(job: Job) -> str | None:
        if not intent_cities:
            return None
        loc = (job.location or "").replace("市", "").strip()
        if loc in ("不限", "远程", "全国"):
            return "__open__"
        for city in intent_cities:
            city_n = str(city).replace("市", "").strip()
            if city_n and (city_n == loc or city_n in loc or loc in city_n):
                return "__intent__"
        return None

    scored_pairs = [
        (cosine_similarity(resume.embedding, job.embedding), job) for job in jobs if job.embedding
    ]
    scored_pairs.sort(key=lambda pair: pair[0], reverse=True)

    if intent_cities:
        intent_quota = max(6, top_n // 2)  # 意向城市保底名额
        open_quota = max(2, top_n // 10)  # 不限/远程/全国保底名额
        buckets: dict[str, list[tuple[float, Job]]] = {"__intent__": [], "__open__": [], "__rest__": []}
        for pair in scored_pairs:
            key = _city_of(pair[1]) or "__rest__"
            buckets[key].append(pair)
        picked: list[tuple[float, Job]] = []
        for key, quota in (("__intent__", intent_quota), ("__open__", open_quota)):
            picked.extend(buckets[key][:quota])
        remaining = top_n - len(picked)
        if remaining > 0:
            rest = buckets["__rest__"][:remaining]
            picked.extend(rest)
            if len(rest) < remaining:
                # 某桶没取满时，用另一桶补齐
                leftover = buckets["__intent__"][intent_quota:] + buckets["__open__"][open_quota:]
                leftover.sort(key=lambda p: p[0], reverse=True)
                picked.extend(leftover[: remaining - len(rest)])
        else:
            # 意向+开放位已满时，仍补全局最高相似度，避免丢掉头部相关岗位
            leftover = buckets["__intent__"][intent_quota:] + buckets["__open__"][open_quota:] + buckets["__rest__"]
            leftover.sort(key=lambda p: p[0], reverse=True)
            picked.extend(leftover[: -remaining])
        picked.sort(key=lambda p: p[0], reverse=True)
        recalled = picked[:top_n]
    else:
        recalled = scored_pairs[:top_n]

    # ①½ 薪资下限硬过滤：岗位上限完全够不到期望下限的岗位不进精排。
    salary_min = expectations.get("salary_min")
    if salary_min is not None:
        floor = float(salary_min or 0)
        recalled = [
            (sim, job)
            for sim, job in recalled
            if (job.salary_max or 0) >= floor
        ]

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
        breakdown = item.get("breakdown") or {}
        direction = breakdown.get("direction") or {}
        # 地点意向量权：用户明确设了城市时，非目标城市的岗位按比例降权；
        # 设了区则区命中再小量加权。不改动 match_score，只影响推荐顺序。
        location = breakdown.get("location") or {}
        intent_cities = location.get("resume_locations") or []
        location_adjust = 0.0
        if intent_cities:
            loc_score = location.get("score") or 0
            if loc_score <= 0:
                # 城市完全不符：按比例扣减，技能分越高扣得越多，避免高技能岗位绕过地点意愿
                location_adjust = -round(item["match_score"] * 0.25, 1)
            elif loc_score < 15:
                location_adjust = -4.0  # 同城但区不符
            if location.get("district_hit") is True:
                location_adjust += 5.0  # 区命中额外提权
        # rank_score 仅用于排序，可以超过 100；展示仍用原始 match_score
        item["rank_score"] = round(
            max(0.0, item["match_score"] + adjust + location_adjust), 1
        )
        # 方向作为同分破缺主键：rank_score 相同且设了方向时，方向分高的在前。
        # 不再折半加进 rank_score——消融显示 ×0.5 后对 top-10 零影响。
        direction_sort = (direction.get("score") or 0) if (
            direction.get("intent_categories") or direction.get("intent_subcategories")
        ) else -1.0  # 未设方向的排在设了方向的后面（仅同分时）
        item["direction_sort"] = direction_sort
        item["_similarity"] = float(similarity)  # 次级破缺：召回相似度
        item["_job_id"] = job.id  # 末级：id 稳定排序
    results.sort(
        key=lambda item: (
            item["rank_score"],
            item["direction_sort"],
            item["_similarity"],
            item["_job_id"],
        ),
        reverse=True,
    )

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


# =========================== 解读缓存 ===========================


def explanation_fingerprint(resume: Resume, job: Job) -> str:
    """简历结构化内容 + 岗位关键字段的短哈希，变更后缓存自动失效。"""
    payload = {
        "resume": resume.structured or {},
        "job": {
            "title": job.title,
            "required_skills": job.required_skills or [],
            "preferred_skills": job.preferred_skills or [],
            "experience_min": job.experience_min,
            "experience_max": job.experience_max,
            "location": job.location,
            "district": job.district or "",
            "salary_min": job.salary_min,
            "salary_max": job.salary_max,
            "description": (job.description or "")[:2000],
        },
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


async def get_cached_explanation(db: Session, resume: Resume, job: Job, scoring: dict) -> dict:
    """读取解读：指纹命中直接返回，否则生成后落库。与投递状态无关。"""
    fp = explanation_fingerprint(resume, job)
    cached = db.scalar(
        select(MatchExplanation).where(
            MatchExplanation.resume_id == resume.id, MatchExplanation.job_id == job.id
        )
    )
    # 空指纹 = 旧库回填行，视为有效，顺便补上指纹避免每次都走判断
    if cached and (cached.fingerprint == fp or (not cached.fingerprint and cached.explanation)):
        if not cached.fingerprint:
            cached.fingerprint = fp
            db.commit()
        return cached.explanation

    explanation = await explain_match(resume, job, scoring)
    if cached:
        cached.fingerprint = fp
        cached.match_score = scoring["total"]
        cached.explanation = explanation
    else:
        cached = MatchExplanation(
            resume_id=resume.id,
            job_id=job.id,
            fingerprint=fp,
            match_score=scoring["total"],
            explanation=explanation,
        )
        db.add(cached)
    db.commit()
    return explanation
