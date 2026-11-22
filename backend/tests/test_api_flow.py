from tests.conftest import (
    attach_resume,
    auth,
    create_job,
    register,
    set_job_embedding,
    standard_structured,
)


def test_register_login_and_me(client):
    user = register(client, "seeker1", "seeker")
    assert user["user"]["role"] == "seeker"

    duplicate = client.post(
        "/api/auth/register",
        json={"username": "seeker1", "password": "demo1234", "role": "seeker", "display_name": "x"},
    )
    assert duplicate.status_code == 409

    wrong = client.post("/api/auth/login", json={"username": "seeker1", "password": "bad-pass"})
    assert wrong.status_code == 401

    me = client.get("/api/auth/me", headers=auth(user["access_token"]))
    assert me.status_code == 200
    assert me.json()["data"]["username"] == "seeker1"

    anonymous = client.get("/api/auth/me")
    assert anonymous.status_code == 401


def test_role_guards(client):
    seeker = register(client, "seeker1", "seeker")
    employer = register(client, "hr1", "employer", company="星澜科技")

    # 求职者不能发岗位
    forbidden = client.post("/api/jobs", json={"title": "x"}, headers=auth(seeker["access_token"]))
    assert forbidden.status_code == 403

    # 招聘方不能访问求职者简历
    forbidden_resume = client.get("/api/resumes/mine", headers=auth(employer["access_token"]))
    assert forbidden_resume.status_code == 403

    # 招聘方不能创建求职者类型的 agent 会话
    session = client.post(
        "/api/agent/sessions",
        json={"agent_type": "seeker"},
        headers=auth(employer["access_token"]),
    )
    assert session.status_code == 403


def test_job_crud_and_company_isolation(client):
    employer = register(client, "hr1", "employer", company="星澜科技")
    other = register(client, "hr2", "employer", company="云枢智能")

    job = create_job(client, employer["access_token"])
    assert job["company_name"] == "星澜科技"

    public = client.get("/api/jobs")
    assert public.json()["data"]["total"] == 1

    mine = client.get("/api/jobs/mine", headers=auth(employer["access_token"]))
    assert mine.json()["data"]["items"][0]["applicant_count"] == 0

    # 其他公司不能改本公司的岗位
    forbidden = client.put(
        f"/api/jobs/{job['id']}",
        json={"title": "被篡改"},
        headers=auth(other["access_token"]),
    )
    assert forbidden.status_code == 403

    updated = client.put(
        f"/api/jobs/{job['id']}",
        json={"status": "closed"},
        headers=auth(employer["access_token"]),
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["status"] == "closed"


def test_application_flow_and_isolation(client):
    seeker = register(client, "seeker1", "seeker")
    employer = register(client, "hr1", "employer", company="星澜科技")
    other = register(client, "hr2", "employer", company="云枢智能")
    job = create_job(client, employer["access_token"])

    attach_resume(seeker["user"]["id"], [0.1] * 8, standard_structured())

    applied = client.post(
        "/api/applications",
        json={"job_id": job["id"], "cover_letter": "你好"},
        headers=auth(seeker["access_token"]),
    )
    assert applied.status_code == 200, applied.text
    application = applied.json()["data"]
    assert application["match_score"] > 0

    duplicate = client.post(
        "/api/applications",
        json={"job_id": job["id"]},
        headers=auth(seeker["access_token"]),
    )
    assert duplicate.status_code == 400

    candidates = client.get(
        f"/api/applications/job/{job['id']}", headers=auth(employer["access_token"])
    )
    assert candidates.json()["data"]["items"][0]["user_id"] == seeker["user"]["id"]

    # 其他公司看不到本公司投递
    forbidden = client.get(
        f"/api/applications/job/{job['id']}", headers=auth(other["access_token"])
    )
    assert forbidden.status_code == 403

    # 越权推进状态
    forbidden_status = client.patch(
        f"/api/applications/{application['id']}/status",
        json={"status": "offer"},
        headers=auth(other["access_token"]),
    )
    assert forbidden_status.status_code == 403

    # 求职者不能自行推进自己的投递状态
    seeker_status = client.patch(
        f"/api/applications/{application['id']}/status",
        json={"status": "offer"},
        headers=auth(seeker["access_token"]),
    )
    assert seeker_status.status_code == 403

    advanced = client.patch(
        f"/api/applications/{application['id']}/status",
        json={"status": "interview", "note": "约技术面"},
        headers=auth(employer["access_token"]),
    )
    assert advanced.status_code == 200
    assert advanced.json()["data"]["status"] == "interview"

    # 不允许回退到更早阶段
    backward = client.patch(
        f"/api/applications/{application['id']}/status",
        json={"status": "submitted"},
        headers=auth(employer["access_token"]),
    )
    assert backward.status_code == 400

    invalid = client.patch(
        f"/api/applications/{application['id']}/status",
        json={"status": "hired"},
        headers=auth(employer["access_token"]),
    )
    assert invalid.status_code == 400


def test_match_pipeline_offline(client, monkeypatch):
    seeker = register(client, "seeker1", "seeker")
    employer = register(client, "hr1", "employer", company="星澜科技")
    job = create_job(client, employer["access_token"])
    attach_resume(seeker["user"]["id"], [1.0, 0.0, 0.0, 0.0], standard_structured())
    set_job_embedding(job["id"], [1.0, 0.0, 0.0, 0.0])

    matches = client.get("/api/match/jobs-for-me", headers=auth(seeker["access_token"]))
    assert matches.status_code == 200, matches.text
    item = matches.json()["data"]["items"][0]
    assert item["id"] == job["id"]
    assert item["similarity"] == 1.0
    assert item["match_score"] >= 90
    assert item["breakdown"]["skills_required"]["score"] == 40

    async def fake_explain(resume, job_obj, scoring):  # noqa: ANN001
        return {"summary": "很匹配", "reasons": ["技能全中"], "gaps": [], "suggestions": []}

    monkeypatch.setattr("app.matching.pipeline.explain_match", fake_explain)
    detail = client.get(f"/api/match/job/{job['id']}", headers=auth(seeker["access_token"]))
    assert detail.status_code == 200
    assert detail.json()["data"]["explanation"]["summary"] == "很匹配"


def test_agent_session_permissions(client):
    seeker = register(client, "seeker1", "seeker")
    seeker2 = register(client, "seeker2", "seeker")
    employer = register(client, "hr1", "employer", company="星澜科技")

    created = client.post("/api/agent/sessions", json={}, headers=auth(seeker["access_token"]))
    assert created.status_code == 200
    session_id = created.json()["data"]["id"]

    own = client.get(
        f"/api/agent/sessions/{session_id}/messages", headers=auth(seeker["access_token"])
    )
    assert own.status_code == 200

    # 其他用户访问不到该会话
    other = client.get(
        f"/api/agent/sessions/{session_id}/messages", headers=auth(seeker2["access_token"])
    )
    assert other.status_code == 404

    # 角色不匹配的会话无法对话
    chat = client.post(
        f"/api/agent/sessions/{session_id}/chat",
        json={"content": "你好"},
        headers=auth(employer["access_token"]),
    )
    assert chat.status_code == 404


def test_resume_upload_rejects_unsupported_type(client):
    seeker = register(client, "seeker1", "seeker")
    response = client.post(
        "/api/resumes/upload",
        headers=auth(seeker["access_token"]),
        files={"file": ("virus.exe", b"not a resume", "application/octet-stream")},
    )
    assert response.status_code == 400
    assert "不支持" in response.json()["message"]


def test_resume_upload_keeps_file_for_preview(client, monkeypatch):
    async def fake_extract(raw_text):  # noqa: ARG001
        return standard_structured()

    async def fake_embed(text):  # noqa: ARG001
        return [0.1] * 8

    monkeypatch.setattr("app.services.resume_service.extract_structured", fake_extract)
    monkeypatch.setattr("app.services.resume_service.embed_one", fake_embed)
    seeker = register(client, "file-seeker", "seeker")
    other = register(client, "file-seeker2", "seeker")

    assert client.get("/api/resumes/mine/file", headers=auth(seeker["access_token"])).status_code == 404

    uploaded = client.post(
        "/api/resumes/upload",
        headers=auth(seeker["access_token"]),
        files={"file": ("resume.txt", b"zhangsan python backend engineer", "text/plain")},
    )
    assert uploaded.status_code == 200, uploaded.text
    info = uploaded.json()["data"]["file"]
    assert info["name"] == "resume.txt"
    assert info["previewable"] is False

    fetched = client.get("/api/resumes/mine/file", headers=auth(seeker["access_token"]))
    assert fetched.status_code == 200
    assert "resume.txt" in fetched.headers["content-disposition"]
    assert fetched.content == b"zhangsan python backend engineer"

    # 其他用户读不到别人的原文件
    assert client.get("/api/resumes/mine/file", headers=auth(other["access_token"])).status_code == 404

    # 重新上传覆盖旧文件，resume_files 只保留一条
    again = client.post(
        "/api/resumes/upload",
        headers=auth(seeker["access_token"]),
        files={"file": ("resume_v2.txt", b"python backend v2", "text/plain")},
    )
    assert again.status_code == 200, again.text
    assert again.json()["data"]["file"]["name"] == "resume_v2.txt"

    from app.db import SessionLocal
    from app.models import ResumeFile

    with SessionLocal() as db:
        assert db.query(ResumeFile).count() == 1


def test_demo_accounts_endpoint(client):
    register(client, "demo-hr", "employer", company="星澜科技")

    response = client.get("/api/auth/demo-accounts")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["password"] == "123456"
    assert {
        "username": "demo-hr",
        "company_name": "星澜科技",
    } in data["employers"]


def test_all_candidates_endpoint(client):
    employer = register(client, "all-hr", "employer", company="星澜科技")
    seeker1 = register(client, "all-seeker1", "seeker")
    seeker2 = register(client, "all-seeker2", "seeker")
    job1 = create_job(client, employer["access_token"], title="Python 后端")
    job2 = create_job(client, employer["access_token"], title="数据工程师")

    for seeker in (seeker1, seeker2):
        attach_resume(seeker["user"]["id"], [0.1] * 8, standard_structured())
    set_job_embedding(job1["id"], [0.1] * 8)
    set_job_embedding(job2["id"], [0.1] * 8)

    for seeker, job in ((seeker1, job1), (seeker2, job2)):
        applied = client.post(
            "/api/applications",
            json={"job_id": job["id"]},
            headers=auth(seeker["access_token"]),
        )
        assert applied.status_code == 200, applied.text

    all_items = client.get(
        "/api/match/candidates", headers=auth(employer["access_token"])
    ).json()["data"]["items"]
    assert len(all_items) == 2
    assert {item["job_title"] for item in all_items} == {"Python 后端", "数据工程师"}
    assert all_items[0]["match_score"] >= all_items[-1]["match_score"]

    filtered = client.get(
        f"/api/match/candidates?job_id={job1['id']}",
        headers=auth(employer["access_token"]),
    ).json()["data"]["items"]
    assert len(filtered) == 1
    assert filtered[0]["job_id"] == job1["id"]

    # 求职者不能访问该接口
    forbidden = client.get("/api/match/candidates", headers=auth(seeker1["access_token"]))
    assert forbidden.status_code == 403
