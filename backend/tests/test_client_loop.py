from tests.conftest import (
    attach_resume,
    auth,
    create_job,
    register,
    set_job_embedding,
    standard_structured,
)


def test_status_change_creates_event_and_notification(client):
    seeker = register(client, "seeker1", "seeker")
    other_seeker = register(client, "seeker2", "seeker")
    employer = register(client, "hr1", "employer", company="星澜科技")
    job = create_job(client, employer["access_token"])
    attach_resume(seeker["user"]["id"], [0.1] * 8, standard_structured())

    applied = client.post(
        "/api/applications",
        json={"job_id": job["id"]},
        headers=auth(seeker["access_token"]),
    )
    application_id = applied.json()["data"]["id"]

    advanced = client.patch(
        f"/api/applications/{application_id}/status",
        json={"status": "screening", "note": "简历通过初筛"},
        headers=auth(employer["access_token"]),
    )
    assert advanced.status_code == 200, advanced.text

    mine = client.get("/api/applications/mine", headers=auth(seeker["access_token"]))
    item = mine.json()["data"]["items"][0]
    assert len(item["events"]) == 1
    assert item["events"][0]["from_status"] == "submitted"
    assert item["events"][0]["to_status"] == "screening"
    assert item["events"][0]["note"] == "简历通过初筛"

    notifications = client.get(
        "/api/notifications", headers=auth(seeker["access_token"])
    ).json()["data"]["items"]
    status_notes = [n for n in notifications if n["type"] == "application_status"]
    assert len(status_notes) == 1
    assert status_notes[0]["payload"]["status"] == "screening"
    assert status_notes[0]["payload"]["application_id"] == application_id

    # 同状态只更新备注，不重复记事件/通知
    client.patch(
        f"/api/applications/{application_id}/status",
        json={"status": "screening", "note": "补充备注"},
        headers=auth(employer["access_token"]),
    )
    mine = client.get("/api/applications/mine", headers=auth(seeker["access_token"]))
    assert len(mine.json()["data"]["items"][0]["events"]) == 1

    # 再推进一个阶段，事件与通知各增加一条
    client.patch(
        f"/api/applications/{application_id}/status",
        json={"status": "interview"},
        headers=auth(employer["access_token"]),
    )
    mine = client.get("/api/applications/mine", headers=auth(seeker["access_token"]))
    assert len(mine.json()["data"]["items"][0]["events"]) == 2
    notifications = client.get(
        "/api/notifications", headers=auth(seeker["access_token"])
    ).json()["data"]["items"]
    assert len([n for n in notifications if n["type"] == "application_status"]) == 2

    # 其他求职者不能读取该投递的状态记录
    forbidden = client.get(
        f"/api/applications/{application_id}/events",
        headers=auth(other_seeker["access_token"]),
    )
    assert forbidden.status_code == 403


def test_candidate_detail_and_resume_download(client, monkeypatch):
    async def fake_extract(raw_text):  # noqa: ARG001
        return standard_structured()

    async def fake_embed(text):  # noqa: ARG001
        return [0.1] * 8

    monkeypatch.setattr("app.services.resume_service.extract_structured", fake_extract)
    monkeypatch.setattr("app.services.resume_service.embed_one", fake_embed)

    seeker = register(client, "seeker1", "seeker")
    employer = register(client, "hr1", "employer", company="星澜科技")
    other = register(client, "hr2", "employer", company="云枢智能")
    job = create_job(client, employer["access_token"])
    set_job_embedding(job["id"], [0.1] * 8)

    uploaded = client.post(
        "/api/resumes/upload",
        headers=auth(seeker["access_token"]),
        files={"file": ("resume.txt", b"python backend engineer", "text/plain")},
    )
    assert uploaded.status_code == 200, uploaded.text

    applied = client.post(
        "/api/applications",
        json={"job_id": job["id"], "cover_letter": "我很喜欢这个岗位"},
        headers=auth(seeker["access_token"]),
    )
    application_id = applied.json()["data"]["id"]

    candidates = client.get(
        f"/api/match/job/{job['id']}/candidates",
        headers=auth(employer["access_token"]),
    )
    assert candidates.status_code == 200, candidates.text
    candidate = candidates.json()["data"]["items"][0]
    assert candidate["cover_letter"] == "我很喜欢这个岗位"
    assert candidate["has_resume_file"] is True
    assert candidate["resume_file_name"] == "resume.txt"

    downloaded = client.get(
        f"/api/applications/{application_id}/resume-file",
        headers=auth(employer["access_token"]),
    )
    assert downloaded.status_code == 200
    assert downloaded.content == b"python backend engineer"
    assert "resume.txt" in downloaded.headers["content-disposition"]

    # 其他公司不能下载
    assert (
        client.get(
            f"/api/applications/{application_id}/resume-file",
            headers=auth(other["access_token"]),
        ).status_code
        == 403
    )
    # 求职者不能走招聘方下载接口
    assert (
        client.get(
            f"/api/applications/{application_id}/resume-file",
            headers=auth(seeker["access_token"]),
        ).status_code
        == 403
    )


def test_saved_jobs_profile_and_company_settings(client):
    seeker = register(client, "seeker1", "seeker")
    employer = register(client, "hr1", "employer", company="星澜科技")
    job = create_job(client, employer["access_token"])

    saved = client.post(
        f"/api/jobs/{job['id']}/feedback",
        json={"action": "save"},
        headers=auth(seeker["access_token"]),
    )
    assert saved.status_code == 200
    saved_list = client.get(
        "/api/jobs/mine/saved", headers=auth(seeker["access_token"])
    )
    assert saved_list.json()["data"]["total"] == 1
    assert saved_list.json()["data"]["items"][0]["id"] == job["id"]

    client.post(
        f"/api/jobs/{job['id']}/feedback",
        json={"action": "clear"},
        headers=auth(seeker["access_token"]),
    )
    assert (
        client.get(
            "/api/jobs/mine/saved", headers=auth(seeker["access_token"])
        ).json()["data"]["total"]
        == 0
    )

    updated = client.put(
        "/api/auth/me",
        json={"display_name": "新名字"},
        headers=auth(seeker["access_token"]),
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["display_name"] == "新名字"

    wrong = client.post(
        "/api/auth/change-password",
        json={"old_password": "wrong", "new_password": "newpass1"},
        headers=auth(seeker["access_token"]),
    )
    assert wrong.status_code == 400

    changed = client.post(
        "/api/auth/change-password",
        json={"old_password": "demo1234", "new_password": "newpass1"},
        headers=auth(seeker["access_token"]),
    )
    assert changed.status_code == 200
    relogin = client.post(
        "/api/auth/login", json={"username": "seeker1", "password": "newpass1"}
    )
    assert relogin.status_code == 200

    mine = client.get("/api/companies/mine", headers=auth(employer["access_token"]))
    company_id = mine.json()["data"]["id"]
    company_update = client.put(
        "/api/companies/mine",
        json={
            "name": "星澜科技（新）",
            "industry": "人工智能",
            "description": "专注企业级 AI 应用。",
        },
        headers=auth(employer["access_token"]),
    )
    assert company_update.status_code == 200

    detail = client.get(
        f"/api/companies/{company_id}", headers=auth(seeker["access_token"])
    )
    assert detail.status_code == 200
    data = detail.json()["data"]
    assert data["name"] == "星澜科技（新）"
    assert data["industry"] == "人工智能"
    assert data["open_job_count"] == 1
    assert data["jobs"][0]["id"] == job["id"]
