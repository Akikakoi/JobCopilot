import json

from app.db import SessionLocal
from app.models import Resume, ResumeVersion
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


def fake_optimize():
    async def fake_chat(messages, tools=None, tool_choice=None, temperature=None, response_format=None):  # noqa: ANN001, ARG001
        payload = {
            "summary": "建议补充容器编排经验，并强化核心模块的量化表达",
            "missing_skills": ["Kubernetes"],
            "skills_to_add": ["Kubernetes"],
            "rewrites": [
                {
                    "target": "工作经历",
                    "original": "负责核心模块开发",
                    "suggestion": "主导核心模块开发，支撑日均 10 万请求",
                }
            ],
            "keywords": ["K8s", "高并发"],
            "suggestions": ["补充 K8s 实践经验", "量化项目成果"],
        }
        return {"role": "assistant", "content": json.dumps(payload, ensure_ascii=False)}

    return fake_chat


def test_resume_versions_and_restore(client, monkeypatch):
    monkeypatch.setattr("app.services.resume_service.embed_one", fake_embed)
    seeker = register(client, "ver-seeker", "seeker")
    other = register(client, "ver-seeker2", "seeker")
    resume_id = attach_resume(seeker["user"]["id"], [0.1] * 8, standard_structured())

    with SessionLocal() as db:
        db.add(
            ResumeVersion(
                resume_id=resume_id,
                structured={"title": "旧版后端", "skills": ["Go", "MySQL"], "years_of_experience": 2},
                label="文件上传",
                note="历史版本",
            )
        )
        db.commit()
        version_id = db.query(ResumeVersion).one().id

    versions = client.get("/api/resumes/versions", headers=auth(seeker["access_token"]))
    assert versions.status_code == 200
    assert versions.json()["data"]["items"][0]["label"] == "文件上传"

    restored = client.post(
        f"/api/resumes/versions/{version_id}/restore", headers=auth(seeker["access_token"])
    )
    assert restored.status_code == 200, restored.text
    assert restored.json()["data"]["structured"]["skills"] == ["Go", "MySQL"]

    with SessionLocal() as db:
        resume = db.get(Resume, resume_id)
        assert resume is not None
        assert resume.structured["skills"] == ["Go", "MySQL"]
        labels = [row.label for row in db.query(ResumeVersion).all()]
    assert len(labels) >= 2  # 回滚会生成新快照

    stolen = client.post(
        f"/api/resumes/versions/{version_id}/restore", headers=auth(other["access_token"])
    )
    assert stolen.status_code == 404


def test_resume_optimize_and_apply(client, monkeypatch):
    monkeypatch.setattr("app.services.resume_service.chat_completion", fake_optimize())
    monkeypatch.setattr("app.services.resume_service.embed_one", fake_embed)
    employer = register(client, "opt-hr", "employer", company="星澜科技")
    seeker = register(client, "opt-seeker", "seeker")
    job = create_job(client, employer["access_token"])
    attach_resume(seeker["user"]["id"], [0.1] * 8, standard_structured())

    optimized = client.post(
        "/api/resumes/optimize",
        json={"job_id": job["id"]},
        headers=auth(seeker["access_token"]),
    )
    assert optimized.status_code == 200, optimized.text
    data = optimized.json()["data"]
    assert data["skills_to_add"] == ["Kubernetes"]
    assert data["rewrites"][0]["target"] == "工作经历"

    applied = client.post(
        "/api/resumes/optimize/apply",
        json={"job_id": job["id"], "skills_to_add": ["Kubernetes", "Python"]},
        headers=auth(seeker["access_token"]),
    )
    assert applied.status_code == 200, applied.text
    skills = applied.json()["data"]["structured"]["skills"]
    assert "Kubernetes" in skills
    assert skills.count("Python") == 1  # 大小写/重复去重

    versions = client.get("/api/resumes/versions", headers=auth(seeker["access_token"]))
    labels = [item["label"] for item in versions.json()["data"]["items"]]
    assert any(label.startswith("按岗优化") for label in labels)

    no_change = client.post(
        "/api/resumes/optimize/apply",
        json={"job_id": job["id"], "skills_to_add": ["Kubernetes"]},
        headers=auth(seeker["access_token"]),
    )
    assert no_change.status_code == 400

    no_resume = register(client, "opt-seeker2", "seeker")
    missing = client.post(
        "/api/resumes/optimize",
        json={"job_id": job["id"]},
        headers=auth(no_resume["access_token"]),
    )
    assert missing.status_code == 400


def test_feedback_bias_changes_ranking(client):
    employer = register(client, "fb-hr", "employer", company="星澜科技")
    seeker = register(client, "fb-seeker", "seeker")
    job_a = create_job(client, employer["access_token"], title="岗位 A")
    job_b = create_job(client, employer["access_token"], title="岗位 B")

    attach_resume(seeker["user"]["id"], [1.0, 0.0, 0.0, 0.0], standard_structured())
    set_job_embedding(job_a["id"], [1.0, 0.0, 0.0, 0.0])
    set_job_embedding(job_b["id"], [1.0, 0.0, 0.0, 0.0])

    def match_items():
        response = client.get("/api/match/jobs-for-me", headers=auth(seeker["access_token"]))
        assert response.status_code == 200, response.text
        return response.json()["data"]["items"]

    items = match_items()
    assert len(items) == 2
    assert all(item["my_feedback"] is None for item in items)
    assert all(item["rank_score"] == item["match_score"] for item in items)

    disliked = client.post(
        f"/api/jobs/{job_a['id']}/feedback",
        json={"action": "dislike", "reason": "地点不合适"},
        headers=auth(seeker["access_token"]),
    )
    assert disliked.status_code == 200
    items = {item["id"]: item for item in match_items()}
    assert items[job_a["id"]]["my_feedback"] == "dislike"
    assert items[job_a["id"]]["rank_score"] == items[job_a["id"]]["match_score"] - 15

    saved = client.post(
        f"/api/jobs/{job_a['id']}/feedback",
        json={"action": "save"},
        headers=auth(seeker["access_token"]),
    )
    assert saved.status_code == 200, saved.text
    ranked = match_items()
    assert ranked[0]["id"] == job_a["id"], [
        (item["id"], item["match_score"], item["rank_score"], item["my_feedback"])
        for item in ranked
    ]  # 收藏后回到第一
    assert ranked[0]["my_feedback"] == "save"

    action = client.get(
        f"/api/jobs/{job_a['id']}/feedback", headers=auth(seeker["access_token"])
    )
    assert action.json()["data"]["action"] == "save"

    cleared = client.post(
        f"/api/jobs/{job_a['id']}/feedback",
        json={"action": "clear"},
        headers=auth(seeker["access_token"]),
    )
    assert cleared.json()["data"]["action"] is None
    items = match_items()
    assert all(item["my_feedback"] is None for item in items)

    forbidden = client.post(
        f"/api/jobs/{job_a['id']}/feedback",
        json={"action": "save"},
        headers=auth(employer["access_token"]),
    )
    assert forbidden.status_code == 403
