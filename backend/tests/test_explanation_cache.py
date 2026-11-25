"""匹配解读缓存测试：未投递岗位的解读不再每次重调 LLM。"""

import json

from app.db import SessionLocal
from app.models import MatchExplanation
from app.matching.pipeline import explanation_fingerprint
from tests.conftest import (
    attach_resume,
    auth,
    create_job,
    register,
    set_job_embedding,
    standard_structured,
)


async def fake_embed(text: str) -> list[float]:  # noqa: ARG001
    return [0.2] * 8


class ExplainCounter:
    def __init__(self):
        self.calls = 0

    async def explain(self, resume, job, scoring):  # noqa: ANN001
        self.calls += 1
        return {
            "summary": f"第 {self.calls} 次生成的解读",
            "reasons": ["技能全中"],
            "gaps": [],
            "suggestions": [],
        }


def setup_seeker_with_job(client):
    seeker = register(client, "cache-seeker", "seeker")
    employer = register(client, "cache-emp", "employer", company="缓存科技")
    job = create_job(client, employer["access_token"])
    attach_resume(seeker["user"]["id"], [1.0, 0.0, 0.0, 0.0], standard_structured())
    set_job_embedding(job["id"], [1.0, 0.0, 0.0, 0.0])
    return seeker, job


def test_explanation_cached_for_unapplied_job(client, monkeypatch):
    """未投递岗位：两次请求只调一次 LLM，返回同一条解读。"""
    monkeypatch.setattr("app.services.resume_service.embed_one", fake_embed)
    counter = ExplainCounter()
    monkeypatch.setattr("app.matching.pipeline.explain_match", counter.explain)

    seeker, job = setup_seeker_with_job(client)

    first = client.get(f"/api/match/job/{job['id']}", headers=auth(seeker["access_token"]))
    assert first.status_code == 200, first.text
    assert first.json()["data"]["explanation"]["summary"] == "第 1 次生成的解读"
    assert first.json()["data"]["applied"] is False

    second = client.get(f"/api/match/job/{job['id']}", headers=auth(seeker["access_token"]))
    assert second.status_code == 200
    assert second.json()["data"]["explanation"]["summary"] == "第 1 次生成的解读"
    assert counter.calls == 1  # 缓存命中，LLM 没被再调


def test_explanation_invalidated_on_resume_change(client, monkeypatch):
    """简历更新后指纹变化，解读重新生成。"""
    monkeypatch.setattr("app.services.resume_service.embed_one", fake_embed)
    counter = ExplainCounter()
    monkeypatch.setattr("app.matching.pipeline.explain_match", counter.explain)

    seeker, job = setup_seeker_with_job(client)

    first = client.get(f"/api/match/job/{job['id']}", headers=auth(seeker["access_token"]))
    assert first.json()["data"]["explanation"]["summary"] == "第 1 次生成的解读"

    # 直接改简历结构化内容（模拟用户更新简历）
    with SessionLocal() as db:
        from app.models import Resume
        from sqlalchemy import select

        resume = db.scalar(select(Resume).where(Resume.user_id == seeker["user"]["id"]))
        structured = dict(resume.structured or {})
        structured["skills"] = ["Python", "FastAPI", "MySQL", "Redis", "Docker", "Kubernetes"]
        resume.structured = structured
        db.commit()

    second = client.get(f"/api/match/job/{job['id']}", headers=auth(seeker["access_token"]))
    assert second.json()["data"]["explanation"]["summary"] == "第 2 次生成的解读"
    assert counter.calls == 2  # 指纹失效，重新调了 LLM


def test_explanation_invalidated_on_job_change(client, monkeypatch):
    """岗位关键信息变更后指纹变化，解读重新生成。"""
    monkeypatch.setattr("app.services.resume_service.embed_one", fake_embed)
    counter = ExplainCounter()
    monkeypatch.setattr("app.matching.pipeline.explain_match", counter.explain)

    seeker, job = setup_seeker_with_job(client)

    first = client.get(f"/api/match/job/{job['id']}", headers=auth(seeker["access_token"]))
    assert counter.calls == 1

    # 招聘方更新岗位描述
    employer = register(client, "cache-emp2", "employer", company="缓存科技")
    # 用同一个 employer 账号（setup 里已注册）更新岗位
    # 直接改库更直接
    with SessionLocal() as db:
        from app.models import Job

        job_row = db.get(Job, job["id"])
        job_row.description = "岗位描述已更新，新增要求：分布式系统经验"
        db.commit()

    second = client.get(f"/api/match/job/{job['id']}", headers=auth(seeker["access_token"]))
    assert counter.calls == 2


def test_backfilled_empty_fingerprint_is_valid(client, monkeypatch):
    """旧库回填的空指纹行：视为有效，读后补指纹。"""
    monkeypatch.setattr("app.services.resume_service.embed_one", fake_embed)
    counter = ExplainCounter()
    monkeypatch.setattr("app.matching.pipeline.explain_match", counter.explain)

    seeker, job = setup_seeker_with_job(client)

    # 第一次生成缓存
    first = client.get(f"/api/match/job/{job['id']}", headers=auth(seeker["access_token"]))
    assert counter.calls == 1

    # 模拟旧库回填：清空指纹
    with SessionLocal() as db:
        from sqlalchemy import select

        row = db.scalar(
            select(MatchExplanation).where(
                MatchExplanation.resume_id == 1, MatchExplanation.job_id == job["id"]
            )
        )
        row.fingerprint = ""
        db.commit()

    # 读取仍然命中（不重调 LLM），且指纹被补上
    second = client.get(f"/api/match/job/{job['id']}", headers=auth(seeker["access_token"]))
    assert counter.calls == 1
    with SessionLocal() as db:
        db.expire_all()
        row = db.scalar(
            select(MatchExplanation).where(
                MatchExplanation.resume_id == 1, MatchExplanation.job_id == job["id"]
            )
        )
        assert row.fingerprint != ""


def test_fingerprint_stable_and_sensitive():
    """指纹：同一输入稳定，简历变化后改变。"""
    from app.models import Job, Resume

    job = Job(
        title="Python 后端工程师",
        description="",
        required_skills=["Python", "FastAPI", "MySQL"],
        preferred_skills=["Docker"],
        experience_min=3,
        experience_max=5,
        location="上海",
        district="徐汇区",
        salary_min=25,
        salary_max=35,
        status="open",
        category="技术研发",
    )
    resume = Resume(
        user_id=1, raw_text="", structured=standard_structured(), source="paste"
    )
    fp1 = explanation_fingerprint(resume, job)
    fp2 = explanation_fingerprint(resume, job)
    assert fp1 == fp2

    structured = dict(resume.structured or {})
    structured["skills"] = ["Go", "MySQL"]
    resume2 = Resume(user_id=1, raw_text="", structured=structured, source="paste")
    assert explanation_fingerprint(resume2, job) != fp1
