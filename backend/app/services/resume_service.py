import json
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
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
  "expectations": {"locations": ["上海"], "salary_min": 20, "salary_max": 35, "job_types": ["全职"]}
}

规则：
- 薪资单位为「K/月」，只填数字；
- 缺失字段留空字符串、空数组或 null，不要编造；
- 技能只保留具体技术/工具/能力名词；
- 若原文不是简历（如乱码、无关文章），全部字段留空。"""


class ResumeExtractionError(ValueError):
    pass


VERSION_LABELS = {"upload": "文件上传", "paste": "文本解析"}

OPTIMIZE_SYSTEM = """你是资深简历顾问。基于岗位与候选人的结构化简历，给出针对该岗位的优化建议，只输出 JSON：
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
        ]
        if p
    )


async def save_resume(db: Session, user_id: int, raw_text: str, source: str) -> Resume:
    structured = await extract_structured(raw_text)
    embedding_text = build_resume_embedding_text(structured)
    embedding = await embed_one(embedding_text)

    resume = db.scalar(select(Resume).where(Resume.user_id == user_id))
    if resume is None:
        resume = Resume(user_id=user_id)
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
    resume.structured = version.structured or {}
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


async def optimize_resume(db: Session, user_id: int, job_id: int) -> dict:
    resume = _owned_resume(db, user_id)
    job = db.get(Job, job_id)
    if job is None:
        raise ValueError("岗位不存在")
    payload = {"岗位": job_to_dict(job), "简历": resume.structured or {}}
    return await _optimize_call(payload)


async def apply_optimization(
    db: Session, user_id: int, job_id: int, skills_to_add: list[str]
) -> Resume:
    resume = _owned_resume(db, user_id)
    job = db.get(Job, job_id)
    if job is None:
        raise ValueError("岗位不存在")

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
    resume.structured = structured
    resume.embedding = await embed_one(build_resume_embedding_text(structured))
    db.commit()
    db.refresh(resume)
    _snapshot(
        db,
        resume,
        f"按岗优化 · {job.title}",
        "补充技能：" + "、".join(added),
    )
    return resume
