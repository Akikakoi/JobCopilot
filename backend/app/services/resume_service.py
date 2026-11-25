import json
from collections import Counter
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.job_taxonomy import derive_subcategory
from app.llm.client import chat_completion, embed_one, message_text
from app.models import Job, Resume, ResumeFile, ResumeVersion
from app.schemas.resume import ResumeOptimizeResult, ResumeStructured
from app.services.job_service import job_to_dict

EXTRACT_SYSTEM = """你是严格的简历结构化解析器。读取用户提供的简历原文，抽取为 JSON，只输出 JSON 对象，不要任何解释。

JSON 结构：
{
  "name": "姓名",
  "title": "当前/目标职位，如 后端开发工程师",
  "skills": ["技能1", "技能2"],
  "years_of_experience": 3,
  "education": [{"school": "学校", "degree": "本科/硕士", "major": "专业", "period": "2016-2020"}],
  "work_experience": [{"company": "公司", "role": "职位", "period": "2021-2023", "highlights": ["量化成果1"]}],
  "expectations": {"locations": ["上海"], "salary_min": 20, "salary_max": 35, "job_types": ["全职"], "target_title": "简历中体现的求职目标职位，没有则留空", "categories": ["从给定类别中选，如 技术研发"], "subcategories": ["从给定方向中选，如 后端开发"]}
}

可选类别（只能从中选）：技术研发、产品与项目、设计、运营、市场与销售、职能支持、生活服务、其他。
二级方向（只能从中选，且必须属于所选类别）：
- 技术研发：硬件与嵌入式、新能源与汽车、建筑工程、环保、制造与工艺、游戏开发、算法与人工智能、前端开发、移动端开发、测试、运维与云原生、数据开发、安全与合规、技术支持、后端开发
- 产品与项目：游戏策划、内容策划、项目管理、产品经理
- 设计：游戏美术、交互设计、空间设计、视觉与平面
- 运营：内容与新媒体、用户与增长、产品运营、电商运营、线下运营、游戏运营、数据运营
- 市场与销售：售前与解决方案、客户成功、商务拓展、市场与投放、销售
- 职能支持：人力资源、财务与税务、法务、行政
- 生活服务：餐饮、酒店、零售、物流、家政

规则：
- 薪资单位为「K/月」，只填数字；
- 缺失字段留空字符串、空数组或 null，不要编造；
- 技能只保留具体技术/工具/能力名词；
- target_title / categories / subcategories 仅在简历明确体现求职方向时才填，不确定就留空，不要根据技能猜测；
- 若原文不是简历（如乱码、无关文章），全部字段留空。"""


class ResumeExtractionError(ValueError):
    pass


VERSION_LABELS = {"upload": "文件上传", "paste": "文本解析"}

OPTIMIZE_SYSTEM = """你是资深简历顾问。基于目标岗位（具体岗位或岗位类别画像）与候选人的结构化简历，给出针对该目标的优化建议，只输出 JSON：
{
  "summary": "一句话结论",
  "missing_skills": ["岗位要求但简历未体现的技能"],
  "skills_to_add": ["建议补充进简历的技能关键词，最多 5 个"],
  "rewrites": [{"target": "工作经历", "original": "原文片段", "suggestion": "改写后的表达"}],
  "keywords": ["建议补充的关键词"],
  "suggestions": ["可执行建议 2-3 条"]
}

要求：
- 不得编造候选人没有的经历或技能；skills_to_add 必须可以从简历内容合理推断；
- rewrites 最多 2 条，必须基于简历原文；
- 中文，不要输出 JSON 以外的内容，不要使用 Markdown 表格。"""


async def extract_structured(raw_text: str) -> dict:
    messages: list[dict] = [
        {"role": "system", "content": EXTRACT_SYSTEM},
        {"role": "user", "content": raw_text[:12000]},
    ]
    last_error: Exception | None = None
    for _ in range(2):  # R2：DeepSeek JSON 抖动，重试 1 次
        reply = await chat_completion(
            messages,
            temperature=0,
            response_format={"type": "json_object"},
        )
        content = message_text(reply.get("content"))
        try:
            data = json.loads(content)
            parsed = ResumeStructured.model_validate(data)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            messages.append({"role": "assistant", "content": content})
            messages.append(
                {
                    "role": "user",
                    "content": f"上一次输出无法解析（{exc}）。请只输出合法 JSON，字段结构严格按约定。",
                }
            )
            continue

        if not parsed.skills and not parsed.work_experience and not parsed.education:
            raise ResumeExtractionError(
                "未能从内容中识别出简历信息，请确认上传的是简历，或改用文本粘贴"
            )
        return parsed.model_dump()

    raise ResumeExtractionError(f"简历结构化失败：{last_error}")


def build_resume_embedding_text(structured: dict) -> str:
    skills = "、".join(structured.get("skills") or [])
    works = "；".join(
        f"{w.get('role', '')}@{w.get('company', '')} {' '.join(w.get('highlights') or [])}"
        for w in structured.get("work_experience") or []
    )
    edu = "；".join(
        f"{e.get('school', '')} {e.get('major', '')} {e.get('degree', '')}"
        for e in structured.get("education") or []
    )
    exp = structured.get("expectations") or {}
    return "\n".join(
        p
        for p in [
            str(structured.get("title") or ""),
            f"技能：{skills}" if skills else "",
            f"经验：{structured.get('years_of_experience', 0)} 年",
            f"工作经历：{works}" if works else "",
            f"教育：{edu}" if edu else "",
            "期望地点：" + "、".join(exp.get("locations") or []) if exp.get("locations") else "",
            f"期望薪资：{exp.get('salary_min')}-{exp.get('salary_max')}K"
            if exp.get("salary_min") or exp.get("salary_max")
            else "",
            # 岗位定位：目标职位与方向进入向量，使定位影响召回
            f"目标职位：{exp.get('target_title')}" if exp.get("target_title") else "",
            "目标方向：" + "、".join(
                [*(exp.get("categories") or []), *(exp.get("subcategories") or [])]
            )
            if (exp.get("categories") or exp.get("subcategories"))
            else "",
            # 地点定位：区级偏好进入向量
            "期望区域："
            + "；".join(
                f"{city}{'/'.join(ds)}" for city, ds in (exp.get("districts") or {}).items()
            )
            if exp.get("districts")
            else "",
        ]
        if p
    )


async def save_resume(db: Session, user_id: int, raw_text: str, source: str) -> Resume:
    structured = await extract_structured(raw_text)
    # 已有的显式求职意向不丢：重新解析可能覆盖 expectations
    existing = db.scalar(select(Resume).where(Resume.user_id == user_id))
    prev_intent = (existing.structured or {}).get("expectations") if existing else None
    INTENT_KEYS = (
        "target_title",
        "categories",
        "subcategories",
        "locations",
        "districts",
        "salary_min",
        "salary_max",
        "job_types",
    )
    if prev_intent and any(prev_intent.get(k) not in (None, [], "") for k in INTENT_KEYS):
        # 用户存过显式意向（含 salary_max=None 的「X 以上」），整体保留，不让解析结果覆盖
        merged = dict(structured.get("expectations") or {})
        for key in INTENT_KEYS:
            if key in prev_intent:
                merged[key] = prev_intent[key]
        structured["expectations"] = merged
    embedding_text = build_resume_embedding_text(structured)
    embedding = await embed_one(embedding_text)

    resume = existing or Resume(user_id=user_id)
    db.add(resume)
    resume.raw_text = raw_text
    resume.structured = structured
    resume.embedding = embedding
    resume.source = source
    db.commit()
    db.refresh(resume)
    _snapshot(db, resume, VERSION_LABELS.get(source, source), f"来源：{source}")
    return resume


def resume_to_dict(resume: Resume) -> dict:
    upload = resume.upload_file
    return {
        "id": resume.id,
        "user_id": resume.user_id,
        "raw_text": resume.raw_text,
        "structured": resume.structured or {},
        "source": resume.source,
        "has_embedding": bool(resume.embedding),
        "updated_at": resume.updated_at,
        "file": (
            {
                "name": upload.file_name,
                "content_type": upload.content_type,
                "size": upload.size,
                "previewable": upload.content_type == "application/pdf",
            }
            if upload
            else None
        ),
    }


# =========================== 原始文件（预览 / 下载） ===========================

CONTENT_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain; charset=utf-8",
    ".md": "text/markdown; charset=utf-8",
}


def save_resume_file(db: Session, resume: Resume, filename: str, data: bytes) -> ResumeFile:
    """把上传的原始文件落盘，并记录到 resume_files；重复上传覆盖旧文件。"""
    suffix = Path(filename).suffix.lower()
    upload_root = Path(settings.upload_dir)
    folder = upload_root / str(resume.user_id)
    folder.mkdir(parents=True, exist_ok=True)

    record = resume.upload_file
    if record and record.stored_path:
        (upload_root / record.stored_path).unlink(missing_ok=True)

    stored = folder / f"{uuid4().hex}{suffix}"
    stored.write_bytes(data)

    if record is None:
        record = ResumeFile(resume_id=resume.id)
        db.add(record)
    record.file_name = Path(filename).name or f"resume{suffix}"
    record.stored_path = stored.relative_to(upload_root).as_posix()
    record.content_type = CONTENT_TYPES.get(suffix, "application/octet-stream")
    record.size = len(data)
    db.commit()
    db.refresh(record)
    db.expire(resume, ["upload_file"])  # 让 resume_to_dict 读到最新文件
    return record


def get_resume_file(db: Session, user_id: int) -> ResumeFile | None:
    return db.scalar(
        select(ResumeFile)
        .join(Resume, ResumeFile.resume_id == Resume.id)
        .where(Resume.user_id == user_id)
    )


# =========================== 版本快照 / 回滚 ===========================


def _snapshot(db: Session, resume: Resume, label: str, note: str = "") -> ResumeVersion:
    version = ResumeVersion(
        resume_id=resume.id,
        structured=resume.structured or {},
        label=label,
        note=note,
    )
    db.add(version)
    db.commit()
    db.refresh(version)
    return version


def version_to_dict(version: ResumeVersion) -> dict:
    structured = version.structured or {}
    return {
        "id": version.id,
        "label": version.label,
        "note": version.note,
        "skills": structured.get("skills") or [],
        "title": structured.get("title") or "",
        "years_of_experience": structured.get("years_of_experience") or 0,
        "created_at": version.created_at,
    }


def list_versions(db: Session, user_id: int) -> list[ResumeVersion]:
    return list(
        db.scalars(
            select(ResumeVersion)
            .join(Resume, ResumeVersion.resume_id == Resume.id)
            .where(Resume.user_id == user_id)
            .order_by(ResumeVersion.id.desc())
        )
    )


def _owned_version(db: Session, user_id: int, version_id: int) -> ResumeVersion:
    version = db.scalar(
        select(ResumeVersion)
        .join(Resume, ResumeVersion.resume_id == Resume.id)
        .where(ResumeVersion.id == version_id, Resume.user_id == user_id)
    )
    if version is None:
        raise PermissionError("简历版本不存在或无权访问")
    return version


async def restore_version(db: Session, user_id: int, version_id: int) -> Resume:
    version = _owned_version(db, user_id, version_id)
    resume = db.get(Resume, version.resume_id)
    if resume is None:
        raise PermissionError("简历不存在")
    structured = dict(version.structured or {})
    # 快照若丢失显式意向（旧版本/意向后未重新解析），用当前意向补齐
    current_exp = (resume.structured or {}).get("expectations") or {}
    snap_exp = dict(structured.get("expectations") or {})
    for key in (
        "target_title",
        "categories",
        "subcategories",
        "locations",
        "districts",
        "salary_min",
        "salary_max",
        "job_types",
    ):
        if key not in snap_exp or snap_exp[key] in (None, [], ""):
            if key in current_exp and current_exp[key] not in (None, [], ""):
                snap_exp[key] = current_exp[key]
    structured["expectations"] = snap_exp
    resume.structured = structured
    resume.embedding = await embed_one(build_resume_embedding_text(resume.structured))
    db.commit()
    db.refresh(resume)
    _snapshot(db, resume, f"回滚至「{version.label}」", f"来源版本 #{version.id}")
    return resume


# =========================== 按岗位优化 ===========================


def _owned_resume(db: Session, user_id: int) -> Resume:
    resume = db.scalar(select(Resume).where(Resume.user_id == user_id))
    if resume is None:
        raise ValueError("请先创建简历")
    return resume


async def _optimize_call(payload: dict) -> dict:
    messages: list[dict] = [
        {"role": "system", "content": OPTIMIZE_SYSTEM},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False, default=str)},
    ]
    last_error: Exception | None = None
    for _ in range(2):
        reply = await chat_completion(
            messages, temperature=0.3, response_format={"type": "json_object"}
        )
        content = message_text(reply.get("content"))
        try:
            parsed = ResumeOptimizeResult.model_validate(json.loads(content))
            return parsed.model_dump()
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            messages.append({"role": "assistant", "content": content})
            messages.append(
                {"role": "user", "content": f"输出不符合要求（{exc}），请只输出合法 JSON。"}
            )
    raise ValueError(f"优化建议生成失败：{last_error}")


def _category_profile(db: Session, category: str, subcategory: str | None = None) -> dict:
    """聚合目标岗位（类别或二级方向）下在招岗位的常见要求，供按岗优化使用。"""
    jobs = list(
        db.scalars(select(Job).where(Job.status == "open", Job.category == category))
    )
    if subcategory:
        jobs = [
            job
            for job in jobs
            if derive_subcategory(job.category or "", job.title) == subcategory
        ]
        if not jobs:
            raise ValueError("该岗位方向暂无在招岗位")
    elif not jobs:
        raise ValueError("该岗位类别暂无在招岗位")
    required: Counter[str] = Counter()
    preferred: Counter[str] = Counter()
    titles: Counter[str] = Counter()
    for job in jobs:
        titles[job.title] += 1
        required.update({s.strip() for s in job.required_skills or [] if s.strip()})
        preferred.update({s.strip() for s in job.preferred_skills or [] if s.strip()})
    profile = {
        "类别": category,
        "在招岗位数": len(jobs),
        "代表职位": [title for title, _ in titles.most_common(8)],
        "高频要求技能": [skill for skill, _ in required.most_common(15)],
        "常见加分技能": [skill for skill, _ in preferred.most_common(10)],
    }
    if subcategory:
        profile["方向"] = subcategory
    return profile


async def optimize_resume(
    db: Session,
    user_id: int,
    job_id: int | None = None,
    category: str | None = None,
    subcategory: str | None = None,
) -> dict:
    resume = _owned_resume(db, user_id)
    if job_id:
        job = db.get(Job, job_id)
        if job is None:
            raise ValueError("岗位不存在")
        target = {"岗位": job_to_dict(job)}
    elif category:
        target = {"岗位类别画像": _category_profile(db, category, subcategory)}
    else:
        raise ValueError("请选择目标岗位类别")
    payload = {**target, "简历": resume.structured or {}}
    return await _optimize_call(payload)


async def apply_optimization(
    db: Session,
    user_id: int,
    skills_to_add: list[str],
    job_id: int | None = None,
    category: str | None = None,
    subcategory: str | None = None,
) -> Resume:
    resume = _owned_resume(db, user_id)
    if job_id:
        job = db.get(Job, job_id)
        if job is None:
            raise ValueError("岗位不存在")
        label = job.title
    elif category:
        label = f"{category} · {subcategory}" if subcategory else category
    else:
        raise ValueError("请选择目标岗位类别")

    structured = dict(resume.structured or {})
    skills = list(structured.get("skills") or [])
    existing = {skill.strip().lower() for skill in skills}
    added: list[str] = []
    for skill in skills_to_add:
        cleaned = skill.strip()
        if cleaned and cleaned.lower() not in existing:
            skills.append(cleaned)
            existing.add(cleaned.lower())
            added.append(cleaned)
    if not added:
        raise ValueError("没有可应用的新技能")

    structured["skills"] = skills
    # structured 是浅拷贝，直接改 skills 可能已写到 resume；
    # 保留当前意向，避免优化后丢定位
    structured["expectations"] = (resume.structured or {}).get("expectations") or {}
    resume.structured = structured
    resume.embedding = await embed_one(build_resume_embedding_text(structured))
    db.commit()
    db.refresh(resume)
    _snapshot(
        db,
        resume,
        f"按岗优化 · {label}",
        "补充技能：" + "、".join(added),
    )
    return resume


# =========================== 岗位定位（求职意向） ===========================

INTENT_CATEGORIES = (
    "技术研发",
    "产品与项目",
    "设计",
    "运营",
    "市场与销售",
    "职能支持",
    "生活服务",
    "其他",
)


def _intent_of(resume: Resume | None) -> dict:
    if resume is None:
        return {}
    return dict((resume.structured or {}).get("expectations") or {})


async def save_job_intent(
    db: Session,
    user_id: int,
    target_title: str = "",
    categories: list[str] | None = None,
    subcategories: list[str] | None = None,
    locations: list[str] | None = None,
    districts: dict[str, list[str]] | None = None,
    salary_min: float | None = None,
    salary_max: float | None = None,
    job_types: list[str] | None = None,
) -> Resume:
    """显式保存求职意向（岗位定位），写入 structured.expectations 并重算向量。

    没有简历时允许先建一条「仅意向」的简历占位，用户后续再补简历内容。
    """
    categories = [c for c in (categories or []) if c in INTENT_CATEGORIES][:3]
    subcategories = [s.strip() for s in (subcategories or []) if s.strip()][:3]
    locations = [l.strip() for l in (locations or []) if l.strip()][:5]
    job_types = [j.strip() for j in (job_types or []) if j.strip()][:3]

    # 区映射清洗：只保留有区的城市，并自动把城市补进 locations
    clean_districts: dict[str, list[str]] = {}
    for city, ds in (districts or {}).items():
        city = str(city or "").strip()
        ds_clean = [str(d).strip() for d in (ds or []) if str(d).strip()]
        ds_clean = list(dict.fromkeys(ds_clean))[:8]
        if city and ds_clean:
            clean_districts[city] = ds_clean
            if city not in locations:
                locations.append(city)

    if salary_min is not None and salary_max is not None and salary_min > salary_max:
        salary_min, salary_max = salary_max, salary_min

    resume = db.scalar(select(Resume).where(Resume.user_id == user_id))
    if resume is None:
        resume = Resume(user_id=user_id, raw_text="", structured={}, source="paste")
        db.add(resume)
        db.flush()

    structured = dict(resume.structured or {})
    expectations = dict(structured.get("expectations") or {})
    expectations.update(
        {
            "target_title": (target_title or "").strip()[:64],
            "categories": categories,
            "subcategories": subcategories,
            "locations": locations,
            "districts": clean_districts,
            "salary_min": salary_min,
            "salary_max": salary_max,
            "job_types": job_types,
        }
    )
    structured["expectations"] = expectations
    resume.structured = structured
    # 意向变化会影响向量召回，重算 embedding；同时刷新最新快照，
    # 避免回滚到旧版本时丢掉刚存的意向
    resume.embedding = await embed_one(build_resume_embedding_text(structured))
    db.commit()
    db.refresh(resume)
    latest = (
        db.query(ResumeVersion)
        .filter(ResumeVersion.resume_id == resume.id)
        .order_by(ResumeVersion.id.desc())
        .first()
    )
    if latest is not None:
        snap = dict(latest.structured or {})
        snap["expectations"] = expectations
        latest.structured = snap
        db.commit()
    _snapshot(db, resume, "更新求职意向", _intent_summary(expectations))
    return resume


def _intent_summary(exp: dict) -> str:
    parts = []
    if exp.get("target_title"):
        parts.append(f"目标 {exp['target_title']}")
    if exp.get("categories"):
        parts.append(" / ".join(exp["categories"]))
    if exp.get("locations"):
        parts.append("地点 " + "、".join(exp["locations"]))
    if exp.get("districts"):
        parts.append(
            "区域 "
            + "；".join(
                f"{city}({'/'.join(ds)})" for city, ds in exp["districts"].items()
            )
        )
    if exp.get("salary_min") or exp.get("salary_max"):
        parts.append(f"薪资 {exp.get('salary_min')}-{exp.get('salary_max')}K")
    return "；".join(parts) or "清空求职意向"


def job_intent_to_dict(resume: Resume | None) -> dict:
    exp = _intent_of(resume)
    return {
        "target_title": exp.get("target_title") or "",
        "categories": exp.get("categories") or [],
        "subcategories": exp.get("subcategories") or [],
        "locations": exp.get("locations") or [],
        "districts": exp.get("districts") or {},
        "salary_min": exp.get("salary_min"),
        "salary_max": exp.get("salary_max"),
        "job_types": exp.get("job_types") or [],
        "has_resume": bool(resume and resume.raw_text),
    }


DIAGNOSE_SYSTEM = """你是资深职业定位顾问。基于候选人画像与可选的意向，判断 TA 适合哪些岗位方向。
只输出 JSON：
{
  "positioning": "一句话定位结论，含最匹配的方向与理由",
  "fits": [
    {
      "category": "岗位类别",
      "subcategory": "二级方向",
      "fit_score": 0-100 的整数,
      "reason": "为什么适合，基于简历中的具体技能/经历",
      "gap": "还差什么，没有就写空字符串"
    }
  ],
  "risks": ["定位风险 1-3 条，如年限不足/方向跨度过大/薪资预期错位"],
  "next_steps": ["可执行的下一步 2-4 条"]
}

要求：
- fits 给 2-4 个方向，fit_score 按匹配度从高到低；
- category 只能从给定类别中选，subcategory 必须属于该类别；
- 必须基于简历真实内容，不要编造经历；某方向明显不适合就不要列；
- 中文，不要输出 JSON 以外的内容。"""


def _category_options(db: Session) -> list[dict]:
    """按在招岗位统计出可选的「类别 → 方向」树，供诊断 prompt 约束输出。"""
    jobs = list(db.scalars(select(Job).where(Job.status == "open")))
    tree: dict[str, set[str]] = {}
    for job in jobs:
        cat = job.category or "其他"
        tree.setdefault(cat, set()).add(derive_subcategory(cat, job.title))
    return [
        {"category": cat, "subcategories": sorted(subs)} for cat, subs in sorted(tree.items())
    ]


async def diagnose_job_fit(
    db: Session,
    user_id: int,
    category: str | None = None,
    subcategory: str | None = None,
) -> dict:
    """岗位定位诊断：我适合什么方向，差距在哪，下一步怎么走。"""
    resume = _owned_resume(db, user_id)
    structured = resume.structured or {}
    if not structured.get("skills") and not structured.get("work_experience"):
        raise ValueError("简历内容不足以做定位诊断，请先完善简历")

    payload = {
        "候选人画像": structured,
        "当前求职意向": structured.get("expectations") or {},
        "可选岗位方向": _category_options(db),
    }
    if category:
        payload["重点关注"] = {"category": category, "subcategory": subcategory or ""}

    reply = await chat_completion(
        [
            {"role": "system", "content": DIAGNOSE_SYSTEM},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False, default=str)},
        ],
        temperature=0.3,
        response_format={"type": "json_object"},
    )
    content = message_text(reply.get("content"))
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError("定位诊断生成失败，请重试") from exc

    fits = []
    for item in data.get("fits") or []:
        cat = str(item.get("category") or "").strip()
        if cat not in INTENT_CATEGORIES:
            continue
        try:
            score = int(item.get("fit_score") or 0)
        except (TypeError, ValueError):
            score = 0
        fits.append(
            {
                "category": cat,
                "subcategory": str(item.get("subcategory") or "").strip(),
                "fit_score": max(0, min(100, score)),
                "reason": str(item.get("reason") or ""),
                "gap": str(item.get("gap") or ""),
            }
        )
    fits.sort(key=lambda f: f["fit_score"], reverse=True)
    return {
        "positioning": str(data.get("positioning") or ""),
        "fits": fits[:4],
        "risks": [str(r) for r in data.get("risks") or []][:3],
        "next_steps": [str(s) for s in data.get("next_steps") or []][:4],
    }
