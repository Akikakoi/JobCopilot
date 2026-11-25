"""增量灌库：把 seed_data/jobs 下尚未入库的岗位追加进现有数据库。

与 app.seed.seed 的区别：不 drop、不重建、不动用户/简历/投递/会话，
只做「新岗位 → 找到/建对应公司 → 生成向量 → 入库」。
幂等：按（公司 + 标题 + 城市）去重，重复运行不会重复插入。

运行：cd backend && .venv/Scripts/python.exe -m app.seed.seed_more
"""

import asyncio
import sys

from app.db import SessionLocal, init_db
from app.llm.client import embed_texts
from app.models import Company, Job
from app.seed.seed import parse_job
from app.services.job_service import job_embedding_text
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
JOBS_DIR = ROOT / "seed_data" / "jobs"


def _job_key(row: dict) -> tuple[str, str, str]:
    return (row["company"], row["title"], row.get("location") or "")


async def seed_more() -> int:
    init_db()
    db = SessionLocal()
    try:
        all_rows = [parse_job(p) for p in sorted(JOBS_DIR.glob("*.md"))]
        existing_keys = {
            (
                job.company.name if job.company else "",
                job.title,
                job.location or "",
            )
            for job in db.query(Job).all()
        }

        # 需要新公司吗：按名字查现有公司，缺失的建新（行业取 md 里的 industry）
        existing_companies = {c.name: c for c in db.query(Company).all()}
        company_industries: dict[str, str] = {}
        pending_rows: list[dict] = []
        for row in all_rows:
            if _job_key(row) in existing_keys:
                continue
            pending_rows.append(row)
            company_name = row.get("company") or ""
            industry = row.get("industry") or "互联网"
            company_industries.setdefault(company_name, industry)

        new_companies: list[Company] = []
        for name, industry in company_industries.items():
            if name and name not in existing_companies:
                new_companies.append(Company(name=name, industry=industry))
        if new_companies:
            db.add_all(new_companies)
            db.commit()
            for c in new_companies:
                existing_companies[c.name] = c
            print(f"新公司 {len(new_companies)} 家：{[c.name for c in new_companies]}")

        if not pending_rows:
            print("没有待入库的新岗位")
            return 0

        jobs: list[Job] = []
        for row in pending_rows:
            company_name = row.pop("company")
            row.pop("industry", None)
            company = existing_companies[company_name]
            jobs.append(Job(company_id=company.id, **row))
        db.add_all(jobs)
        db.commit()

        vectors = await embed_texts([job_embedding_text(job) for job in jobs])
        for job, vector in zip(jobs, vectors, strict=True):
            job.embedding = vector
        db.commit()
        print(f"新增岗位 {len(jobs)} 个，当前总数 {db.query(Job).count()}")
        return len(jobs)
    finally:
        db.close()


if __name__ == "__main__":
    if "--force" not in sys.argv:
        pass  # 增量脚本本身就是幂等的，无需确认
    asyncio.run(seed_more())
