import asyncio

import pytest
from sqlalchemy import select

from app.agent.tools import _search_jobs
from app.db import SessionLocal
from app.models import User
from app.services import job_service
from tests.conftest import create_job, register, set_job_embedding

QUERY_VECTOR = [1.0, 0.0, 0.0]


@pytest.fixture(autouse=True)
def _clear_query_cache():
    """每个用例前清空查询向量缓存，避免用例之间互相影响"""
    job_service._query_embedding_cache.clear()
    yield
    job_service._query_embedding_cache.clear()


def _fake_embed(monkeypatch, vector=None, calls=None, error: Exception | None = None):
    vector = vector or QUERY_VECTOR

    async def _embed(texts, batch_size: int = 10):
        if calls is not None:
            calls.extend(texts)
        if error is not None:
            raise error
        return [list(vector) for _ in texts]

    monkeypatch.setattr(job_service, "embed_texts", _embed)


def test_hybrid_ranks_keyword_hits_then_appends_semantic(client, monkeypatch):
    employer = register(client, "hr1", "employer", company="星澜科技")
    token = employer["access_token"]

    title_hit = create_job(
        client, token, title="Python 后端工程师", required_skills=["Java"], description="负责服务开发"
    )
    skills_hit = create_job(
        client, token, title="后端工程师", required_skills=["Python"], description="负责服务开发"
    )
    desc_hit = create_job(
        client, token, title="服务端工程师", required_skills=["Java"], description="熟悉 Python 生态"
    )
    semantic_only = create_job(
        client, token, title="数据平台工程师", required_skills=["SQL"], description="数据开发"
    )
    below_threshold = create_job(
        client, token, title="运维工程师", required_skills=["Linux"], description="系统维护"
    )

    # 分别给 4 个岗位设置与查询向量的相似度；最后一个低于阈值
    set_job_embedding(title_hit["id"], [0.0, 0.0, 1.0])
    set_job_embedding(skills_hit["id"], [1.0, 0.0, 0.0])
    set_job_embedding(desc_hit["id"], [0.0, 1.0, 0.0])
    set_job_embedding(semantic_only["id"], [0.9, 0.1, 0.0])
    set_job_embedding(below_threshold["id"], [0.2, 0.98, 0.0])

    _fake_embed(monkeypatch)

    with SessionLocal() as db:
        results = asyncio.run(job_service.search_jobs(db, keywords="Python"))

    assert [job.id for job in results] == [
        title_hit["id"],  # 标题命中
        skills_hit["id"],  # 技能命中
        desc_hit["id"],  # 描述命中
        semantic_only["id"],  # 语义补充
    ]
    # 低相似度岗位不应被语义召回
    assert below_threshold["id"] not in {job.id for job in results}


def test_hybrid_deduplicates_semantic_and_keyword_hits(client, monkeypatch):
    employer = register(client, "hr1", "employer", company="星澜科技")
    token = employer["access_token"]
    job = create_job(client, token, title="Python 后端工程师", required_skills=["Python"])
    set_job_embedding(job["id"], [1.0, 0.0, 0.0])

    _fake_embed(monkeypatch)

    with SessionLocal() as db:
        results = asyncio.run(job_service.search_jobs(db, keywords="Python"))

    assert [item.id for item in results] == [job["id"]]


def test_short_keyword_skips_embedding(client, monkeypatch):
    employer = register(client, "hr1", "employer", company="星澜科技")
    create_job(client, employer["access_token"], title="Python 后端工程师")

    calls: list[str] = []
    _fake_embed(monkeypatch, calls=calls)

    with SessionLocal() as db:
        results = asyncio.run(job_service.search_jobs(db, keywords="P"))

    assert calls == []
    assert results


def test_embedding_failure_falls_back_to_keyword_results(client, monkeypatch):
    employer = register(client, "hr1", "employer", company="星澜科技")
    token = employer["access_token"]
    lexical = create_job(client, token, title="Python 后端工程师")
    semantic_only = create_job(client, token, title="数据平台工程师", required_skills=["SQL"])
    set_job_embedding(semantic_only["id"], [1.0, 0.0, 0.0])

    _fake_embed(monkeypatch, error=RuntimeError("embedding 服务不可用"))

    with SessionLocal() as db:
        results = asyncio.run(job_service.search_jobs(db, keywords="Python"))

    assert [job.id for job in results] == [lexical["id"]]


def test_semantic_results_respect_location_and_category_filters(client, monkeypatch):
    employer = register(client, "hr1", "employer", company="星澜科技")
    token = employer["access_token"]
    shanghai_tech = create_job(
        client, token, title="数据平台工程师", location="上海", category="技术研发"
    )
    beijing_tech = create_job(
        client, token, title="算法平台工程师", location="北京", category="技术研发"
    )
    shanghai_hr = create_job(
        client, token, title="员工关系专员", location="上海", category="职能支持"
    )
    for job in (shanghai_tech, beijing_tech, shanghai_hr):
        set_job_embedding(job["id"], [1.0, 0.0, 0.0])

    _fake_embed(monkeypatch)

    with SessionLocal() as db:
        by_location = asyncio.run(
            job_service.search_jobs(db, keywords="写代码的", location="上海", category="技术研发")
        )
        by_category = asyncio.run(
            job_service.search_jobs(db, keywords="写代码的", category="职能支持")
        )

    assert [job.id for job in by_location] == [shanghai_tech["id"]]
    assert [job.id for job in by_category] == [shanghai_hr["id"]]


def test_query_embedding_is_cached(client, monkeypatch):
    employer = register(client, "hr1", "employer", company="星澜科技")
    job = create_job(client, employer["access_token"], title="数据平台工程师")
    set_job_embedding(job["id"], [1.0, 0.0, 0.0])

    calls: list[str] = []
    _fake_embed(monkeypatch, calls=calls)

    with SessionLocal() as db:
        first = asyncio.run(job_service.search_jobs(db, keywords="写代码的"))
        second = asyncio.run(job_service.search_jobs(db, keywords="写代码的"))

    assert calls == ["写代码的"]
    assert [job.id for job in first] == [job.id for job in second] == [job["id"]]


def test_jobs_api_returns_semantic_matches(client, monkeypatch):
    employer = register(client, "hr1", "employer", company="星澜科技")
    job = create_job(client, employer["access_token"], title="员工关系专员")
    set_job_embedding(job["id"], [1.0, 0.0, 0.0])

    _fake_embed(monkeypatch)

    response = client.get("/api/jobs", params={"keywords": "写代码的"})
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] == 1
    assert data["items"][0]["title"] == "员工关系专员"


def test_agent_search_tool_uses_hybrid_search(client, monkeypatch):
    register(client, "seeker1", "seeker")
    employer = register(client, "hr1", "employer", company="星澜科技")
    job = create_job(client, employer["access_token"], title="员工关系专员")
    set_job_embedding(job["id"], [1.0, 0.0, 0.0])

    _fake_embed(monkeypatch)

    with SessionLocal() as db:
        seeker = db.scalar(select(User).where(User.username == "seeker1"))
        result = asyncio.run(_search_jobs(db, seeker, keywords="写代码的"))

    assert result["total"] == 1
    assert result["jobs"][0]["id"] == job["id"]
