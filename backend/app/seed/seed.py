"""种子脚本：解析 seed_data/*.md → 建表灌库 → 生成向量 → 预置演示账号。

运行：cd backend && .venv/Scripts/python.exe -m app.seed.seed
幂等：先 drop_all 再 create_all。
"""

import asyncio
from pathlib import Path

from app.config import BASE_DIR
from app.db import Base, SessionLocal, engine, init_db
from app.llm.client import embed_texts
from app.matching import pipeline
from app.models import Application, Company, Job, Resume, User
from app.security import hash_password
from app.services.job_service import job_embedding_text
from app.services.resume_service import build_resume_embedding_text

ROOT = BASE_DIR.parent
JOBS_DIR = ROOT / "seed_data" / "jobs"
RESUMES_DIR = ROOT / "seed_data" / "resumes"
DEMO_PASSWORD = "demo1234"

STATUS_CYCLE = ["submitted", "screening", "interview", "submitted", "rejected", "screening", "offer"]


def _parse_sections(text: str) -> tuple[str, dict[str, str], dict[str, list[str]]]:
    title = ""
    meta: dict[str, str] = {}
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("## "):
            current = line[3:].strip()
            sections[current] = []
        elif line.startswith("# ") and not title:
            title = line[2:].strip()
        elif line.startswith("- ") and current is None:
            key, _, value = line[2:].partition(":")
            meta[key.strip()] = value.strip()
        elif current:
            sections[current].append(line)
    return title, meta, sections


def _range(value: str, cast=float) -> tuple:
    left, _, right = value.partition("-")
    try:
        return cast(left.strip() or 0), cast(right.strip() or left.strip() or 0)
    except ValueError:
        return cast(0), cast(0)


def parse_job(path: Path) -> dict:
    title, meta, sections = _parse_sections(path.read_text(encoding="utf-8"))
    smin, smax = _range(meta.get("薪资", "0-0"))
    emin, emax = _range(meta.get("经验", "0-10"), int)
    return {
        "title": title,
        "company": meta.get("公司", ""),
        "industry": meta.get("行业", "互联网"),
        "location": meta.get("城市", "不限"),
        "salary_min": smin,
        "salary_max": smax,
        "experience_min": emin,
        "experience_max": emax,
        "status": meta.get("状态", "open"),
        "required_skills": [s.strip() for s in ",".join(sections.get("必需技能", [])).split(",") if s.strip()],
        "preferred_skills": [s.strip() for s in ",".join(sections.get("加分技能", [])).split(",") if s.strip()],
        "description": "\n".join(sections.get("岗位描述", [])),
    }


def parse_resume(path: Path) -> tuple[dict, dict]:
    name, meta, sections = _parse_sections(path.read_text(encoding="utf-8"))
    smin, smax = _range(meta.get("期望薪资", "0-0").replace("K", ""))
    skills = [s.strip() for s in ",".join(sections.get("技能", [])).split(",") if s.strip()]

    education = []
    for line in sections.get("教育经历", []):
        parts = [p.strip() for p in line.lstrip("- ").split("|")]
        if len(parts) >= 4:
            education.append(
                {"school": parts[0], "degree": parts[1], "major": parts[2], "period": parts[3]}
            )

    work: list[dict] = []
    for line in sections.get("工作经历", []):
        if line.startswith("### "):
            parts = [p.strip() for p in line[4:].split("|")]
            work.append(
                {
                    "company": parts[0] if parts else "",
                    "role": parts[1] if len(parts) > 1 else "",
                    "period": parts[2] if len(parts) > 2 else "",
                    "highlights": [],
                }
            )
        elif line.startswith("- ") and work:
            work[-1]["highlights"].append(line[2:].strip())

    structured = {
        "name": name,
        "title": meta.get("目标职位", ""),
        "skills": skills,
        "years_of_experience": float(meta.get("工作年限", 0) or 0),
        "education": education,
        "work_experience": work,
        "expectations": {
            "locations": [meta.get("期望城市", "")] if meta.get("期望城市") else [],
            "salary_min": smin or None,
            "salary_max": smax or None,
            "job_types": ["全职"],
        },
    }
    return structured, {"raw_text": path.read_text(encoding="utf-8")}


def _build_employers(db, company_industries: dict[str, str]) -> dict[str, Company]:
    """每家公司配一个招聘方账号；星澜科技为演示账号 hr-li。"""
    companies: dict[str, Company] = {}
    for index, (name, industry) in enumerate(company_industries.items()):
        is_demo = name == "星澜科技"
        owner = User(
            username="hr-li" if is_demo else f"hr-{index:02d}",
            password_hash=hash_password(DEMO_PASSWORD),
            role="employer",
            display_name="李 HR" if is_demo else f"HR-{index:02d}",
        )
        db.add(owner)
        db.flush()
        company = Company(owner_user_id=owner.id, name=name, industry=industry, description="")
        db.add(company)
        db.flush()
        companies[name] = company
    return companies


async def seed() -> None:
    Base.metadata.drop_all(bind=engine)
    init_db()
    db = SessionLocal()
    try:
        job_rows = [parse_job(p) for p in sorted(JOBS_DIR.glob("*.md"))]
        company_industries: dict[str, str] = {}
        for row in job_rows:
            company_industries.setdefault(row["company"], row.get("industry", "互联网"))
        # 演示公司排在最前，保证 hr-li 一定是星澜科技
        company_industries = {
            "星澜科技": company_industries.get("星澜科技", "互联网"),
            **{k: v for k, v in company_industries.items() if k != "星澜科技"},
        }
        companies = _build_employers(db, company_industries)

        # ---- 岗位 ----
        jobs: list[Job] = []
        for row in job_rows:
            company_name = row.pop("company")
            row.pop("industry", None)
            company = companies[company_name]
            jobs.append(Job(company_id=company.id, **row))
        db.add_all(jobs)
        db.commit()

        vectors = await embed_texts([job_embedding_text(job) for job in jobs])
        for job, vector in zip(jobs, vectors, strict=True):
            job.embedding = vector
        db.commit()
        print(f"岗位写入完成：{len(jobs)} 个")

        # ---- 简历 + 求职者 ----
        demo_created: list[tuple[User, Resume, int]] = []
        resume_paths = sorted(RESUMES_DIR.glob("*.md"))
        structured_list = []
        for index, path in enumerate(resume_paths):
            structured, extra = parse_resume(path)
            structured_list.append((structured, extra, path))

        resume_vectors = await embed_texts(
            [build_resume_embedding_text(item[0]) for item in structured_list]
        )

        for index, (structured, extra, _path) in enumerate(structured_list):
            is_demo = index == 0
            user = User(
                username="zhangsan" if is_demo else f"cand{index + 1:02d}",
                password_hash=hash_password(DEMO_PASSWORD),
                role="seeker",
                display_name=structured["name"],
            )
            db.add(user)
            db.flush()
            resume = Resume(
                user_id=user.id,
                raw_text=extra["raw_text"],
                structured=structured,
                embedding=resume_vectors[index],
                source="upload",
            )
            db.add(resume)
            db.flush()
            demo_created.append((user, resume, index))
        db.commit()
        print(f"简历写入完成：{len(demo_created)} 份（演示账号 zhangsan / demo1234）")

        # ---- 预置投递（让 HR 端有候选人可看） ----
        app_count = 0
        for user, resume, index in demo_created:
            if index == 0:
                continue  # 演示求职者 zhangsan 保持零投递，便于完整演示「找岗位 → 投递」链路
            matches = await pipeline.match_jobs_for_resume(db, resume, max_results=3)
            for rank, item in enumerate(matches):
                app = Application(
                    job_id=item["id"],
                    resume_id=resume.id,
                    user_id=user.id,
                    status=STATUS_CYCLE[(index + rank) % len(STATUS_CYCLE)],
                    match_score=item["match_score"],
                )
                db.add(app)
                app_count += 1
        db.commit()
        print(f"投递记录写入完成：{app_count} 条")

        demo_company = companies.get("星澜科技")
        hr_count = max(len(companies) - 1, 0)
        print("\n演示账号：")
        print("  求职者 zhangsan / demo1234")
        print("  招聘方 hr-li   / demo1234" + (f"（公司：{demo_company.name}）" if demo_company else ""))
        print(f"  其余 HR 账号 hr-01 ~ hr-{hr_count:02d} / demo1234")
        print(f"  其余求职者 cand02 ~ cand{len(demo_created):02d} / demo1234")
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(seed())
