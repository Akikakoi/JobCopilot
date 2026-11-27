import asyncio

from app.db import SessionLocal
from app.models import Company, Job, User
from app.seed import seed_more as seed_more_module


def test_seed_more_creates_owner_for_new_company(client, tmp_path, monkeypatch):
    job_dir = tmp_path / "jobs"
    job_dir.mkdir()
    (job_dir / "new_job.md").write_text(
        "# 数据分析师\n\n"
        "- 公司: 新芽数据\n"
        "- 行业: 数据服务\n"
        "- 城市: 上海\n"
        "- 薪资: 15-20\n"
        "- 经验: 1-3\n"
        "- 类别: 技术研发\n"
        "- 性质: 全职\n"
        "- 状态: open\n\n"
        "## 岗位描述\n负责数据分析与报表。\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(seed_more_module, "JOBS_DIR", job_dir)

    async def fake_embed_texts(texts):
        return [[0.0] * 8 for _ in texts]

    monkeypatch.setattr(seed_more_module, "embed_texts", fake_embed_texts)

    created = asyncio.run(seed_more_module.seed_more())
    assert created == 1

    with SessionLocal() as db:
        company = db.query(Company).filter(Company.name == "新芽数据").one()
        assert company.owner_user_id is not None
        owner = db.get(User, company.owner_user_id)
        assert owner is not None
        assert owner.role == "employer"
        job = db.query(Job).filter(Job.company_id == company.id).one()
        assert job.title == "数据分析师"