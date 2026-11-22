from tests.conftest import attach_resume, auth, create_job, register, standard_structured


def setup_application(client, suffix: str = "") -> tuple[dict, dict, dict, dict]:
    seeker = register(client, f"pipe-seeker{suffix}", "seeker")
    employer = register(client, f"pipe-hr{suffix}", "employer", company="星澜科技")
    attach_resume(seeker["user"]["id"], [0.1] * 8, standard_structured())
    job = create_job(client, employer["access_token"])
    applied = client.post(
        "/api/applications",
        json={"job_id": job["id"]},
        headers=auth(seeker["access_token"]),
    )
    assert applied.status_code == 200, applied.text
    return seeker, employer, job, applied.json()["data"]


def test_interview_invite_flow(client):
    seeker, employer, _, application = setup_application(client)

    created = client.post(
        f"/api/applications/{application['id']}/interview-invites",
        json={
            "scheduled_at": "2030-01-01T10:00:00",
            "duration_minutes": 60,
            "mode": "video",
            "location": "腾讯会议 123-456",
            "note": "技术二面",
        },
        headers=auth(employer["access_token"]),
    )
    assert created.status_code == 200, created.text
    invite = created.json()["data"]
    assert invite["status"] == "pending"

    mine = client.get("/api/applications/mine", headers=auth(seeker["access_token"]))
    item = mine.json()["data"]["items"][0]
    assert item["status"] == "interview"
    assert item["interview_invites"][0]["id"] == invite["id"]

    confirmed = client.post(
        f"/api/applications/{application['id']}/interview-invites/{invite['id']}/respond",
        json={"action": "confirm", "note": "准时参加"},
        headers=auth(seeker["access_token"]),
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["data"]["status"] == "confirmed"

    employer_notes = client.get(
        "/api/notifications", headers=auth(employer["access_token"])
    ).json()["data"]["items"]
    assert any(item["type"] == "interview_response" for item in employer_notes)

    seeker_notes = client.get(
        "/api/notifications", headers=auth(seeker["access_token"])
    ).json()["data"]["items"]
    assert any(item["type"] == "interview_invite" for item in seeker_notes)

    # 取消邀约
    second = client.post(
        f"/api/applications/{application['id']}/interview-invites",
        json={"scheduled_at": "2030-01-05T14:00:00", "mode": "onsite", "location": "会议室 A"},
        headers=auth(employer["access_token"]),
    )
    second_invite = second.json()["data"]
    cancelled = client.post(
        f"/api/applications/{application['id']}/interview-invites/{second_invite['id']}/cancel",
        json={"note": "面试官临时有安排"},
        headers=auth(employer["access_token"]),
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["data"]["status"] == "cancelled"


def test_interview_invite_permissions(client):
    seeker, employer, _, application = setup_application(client)
    outsider = register(client, "pipe-outsider", "seeker")

    created = client.post(
        f"/api/applications/{application['id']}/interview-invites",
        json={"scheduled_at": "2030-01-01T10:00:00"},
        headers=auth(employer["access_token"]),
    )
    invite_id = created.json()["data"]["id"]

    # 求职者不能自己发邀约
    forbidden_create = client.post(
        f"/api/applications/{application['id']}/interview-invites",
        json={"scheduled_at": "2030-01-01T10:00:00"},
        headers=auth(seeker["access_token"]),
    )
    assert forbidden_create.status_code == 403

    # 其他求职者不能响应
    forbidden_respond = client.post(
        f"/api/applications/{application['id']}/interview-invites/{invite_id}/respond",
        json={"action": "confirm"},
        headers=auth(outsider["access_token"]),
    )
    assert forbidden_respond.status_code == 403


def test_offer_accept_flow(client):
    seeker, employer, _, application = setup_application(client)

    created = client.post(
        f"/api/applications/{application['id']}/offer",
        json={
            "salary_min": 30,
            "salary_max": 38,
            "start_date": "2030-02-01",
            "expires_at": "2030-01-10T23:59:59",
            "note": "期权另议",
        },
        headers=auth(employer["access_token"]),
    )
    assert created.status_code == 200, created.text
    assert created.json()["data"]["status"] == "pending"

    mine = client.get("/api/applications/mine", headers=auth(seeker["access_token"]))
    item = mine.json()["data"]["items"][0]
    assert item["status"] == "offer"
    assert item["offer"]["salary_min"] == 30

    accepted = client.post(
        f"/api/applications/{application['id']}/offer/respond",
        json={"action": "accept", "note": "接受"},
        headers=auth(seeker["access_token"]),
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["data"]["status"] == "accepted"

    # 不能重复响应
    again = client.post(
        f"/api/applications/{application['id']}/offer/respond",
        json={"action": "decline"},
        headers=auth(seeker["access_token"]),
    )
    assert again.status_code == 400

    employer_notes = client.get(
        "/api/notifications", headers=auth(employer["access_token"])
    ).json()["data"]["items"]
    assert any(item["type"] == "offer_response" for item in employer_notes)


def test_offer_decline_ends_application(client):
    seeker, employer, _, application = setup_application(client, "-2")

    created = client.post(
        f"/api/applications/{application['id']}/offer",
        json={"salary_min": 20, "salary_max": 22},
        headers=auth(employer["access_token"]),
    )
    assert created.status_code == 200

    declined = client.post(
        f"/api/applications/{application['id']}/offer/respond",
        json={"action": "decline", "note": "已接受其他机会"},
        headers=auth(seeker["access_token"]),
    )
    assert declined.status_code == 200
    assert declined.json()["data"]["status"] == "declined"

    mine = client.get("/api/applications/mine", headers=auth(seeker["access_token"]))
    item = mine.json()["data"]["items"][0]
    assert item["status"] == "rejected"
    assert item["events"][-1]["to_status"] == "rejected"

    # 投递结束后不能再发 Offer
    again = client.post(
        f"/api/applications/{application['id']}/offer",
        json={"salary_min": 20, "salary_max": 22},
        headers=auth(employer["access_token"]),
    )
    assert again.status_code == 400


def test_offer_permissions(client):
    seeker, employer, _, application = setup_application(client, "-3")
    other_employer = register(client, "pipe-hr-other", "employer", company="别家公司")
    outsider = register(client, "pipe-seeker-other", "seeker")

    forbidden_create = client.post(
        f"/api/applications/{application['id']}/offer",
        json={"salary_min": 10, "salary_max": 12},
        headers=auth(other_employer["access_token"]),
    )
    assert forbidden_create.status_code == 403

    created = client.post(
        f"/api/applications/{application['id']}/offer",
        json={"salary_min": 10, "salary_max": 12},
        headers=auth(employer["access_token"]),
    )
    assert created.status_code == 200

    forbidden_respond = client.post(
        f"/api/applications/{application['id']}/offer/respond",
        json={"action": "accept"},
        headers=auth(outsider["access_token"]),
    )
    assert forbidden_respond.status_code == 403


def test_interview_invite_time_validation_and_complete(client):
    seeker, employer, _, application = setup_application(client, "-4")

    past = client.post(
        f"/api/applications/{application['id']}/interview-invites",
        json={"scheduled_at": "2000-01-01T10:00:00"},
        headers=auth(employer["access_token"]),
    )
    assert past.status_code == 400
    assert "晚于当前时间" in past.json()["message"]

    first = client.post(
        f"/api/applications/{application['id']}/interview-invites",
        json={"scheduled_at": "2030-01-01T10:00:00", "duration_minutes": 60},
        headers=auth(employer["access_token"]),
    )
    assert first.status_code == 200, first.text
    invite_id = first.json()["data"]["id"]

    conflict = client.post(
        f"/api/applications/{application['id']}/interview-invites",
        json={"scheduled_at": "2030-01-01T10:30:00", "duration_minutes": 45},
        headers=auth(employer["access_token"]),
    )
    assert conflict.status_code == 400
    assert "冲突" in conflict.json()["message"]

    client.post(
        f"/api/applications/{application['id']}/interview-invites/{invite_id}/respond",
        json={"action": "confirm"},
        headers=auth(seeker["access_token"]),
    )
    completed = client.post(
        f"/api/applications/{application['id']}/interview-invites/{invite_id}/complete",
        json={"note": "一面通过"},
        headers=auth(employer["access_token"]),
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["data"]["status"] == "completed"

    # 重复标记为幂等
    again = client.post(
        f"/api/applications/{application['id']}/interview-invites/{invite_id}/complete",
        json={},
        headers=auth(employer["access_token"]),
    )
    assert again.status_code == 200


def test_offer_expiry_is_presented_and_rejected(client):
    seeker, employer, _, application = setup_application(client, "-5")

    created = client.post(
        f"/api/applications/{application['id']}/offer",
        json={
            "salary_min": 20,
            "salary_max": 24,
            "expires_at": "2000-01-01T00:00:00",
        },
        headers=auth(employer["access_token"]),
    )
    assert created.status_code == 200, created.text
    assert created.json()["data"]["status"] == "expired"
    assert created.json()["data"]["status_label"] == "已过期"

    respond = client.post(
        f"/api/applications/{application['id']}/offer/respond",
        json={"action": "accept"},
        headers=auth(seeker["access_token"]),
    )
    assert respond.status_code == 400
    assert "过期" in respond.json()["message"]


def test_offer_accept_enters_onboarding_and_records_result(client):
    seeker, employer, _, application = setup_application(client, "-7")

    created = client.post(
        f"/api/applications/{application['id']}/offer",
        json={"salary_min": 30, "salary_max": 38, "start_date": "2030-02-01"},
        headers=auth(employer["access_token"]),
    )
    assert created.status_code == 200, created.text

    accepted = client.post(
        f"/api/applications/{application['id']}/offer/respond",
        json={"action": "accept", "note": "接受"},
        headers=auth(seeker["access_token"]),
    )
    assert accepted.status_code == 200, accepted.text

    mine = client.get("/api/applications/mine", headers=auth(seeker["access_token"]))
    item = mine.json()["data"]["items"][0]
    assert item["status"] == "onboarding"
    assert item["status_label"] == "待入职"
    assert item["onboarding"]["date"] == "2030-02-01"
    assert item["onboarding"]["confirmed"] is False
    assert item["events"][-1]["to_status"] == "onboarding"

    confirmed = client.post(
        f"/api/applications/{application['id']}/onboarding/confirm",
        json={"note": "会按时到岗"},
        headers=auth(seeker["access_token"]),
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["data"]["onboarding"]["confirmed"] is True

    employer_notes = client.get(
        "/api/notifications", headers=auth(employer["access_token"])
    ).json()["data"]["items"]
    assert any(item["type"] == "onboarding_confirmed" for item in employer_notes)

    result = client.post(
        f"/api/applications/{application['id']}/onboarding/result",
        json={"result": "hired", "note": "已按期到岗", "onboarding_date": "2030-02-03"},
        headers=auth(employer["access_token"]),
    )
    assert result.status_code == 200, result.text
    data = result.json()["data"]
    assert data["status"] == "hired"
    assert data["status_label"] == "已入职"
    assert data["onboarding"]["result"] == "hired"
    assert data["onboarding"]["date"] == "2030-02-03"
    assert data["events"][-1]["to_status"] == "hired"

    seeker_notes = client.get(
        "/api/notifications", headers=auth(seeker["access_token"])
    ).json()["data"]["items"]
    assert any(item["type"] == "onboarding_result" for item in seeker_notes)

    # 入职结果只能记录一次
    again = client.post(
        f"/api/applications/{application['id']}/onboarding/result",
        json={"result": "abandoned"},
        headers=auth(employer["access_token"]),
    )
    assert again.status_code == 400


def test_onboarding_abandon_and_permissions(client):
    seeker, employer, _, application = setup_application(client, "-8")

    created = client.post(
        f"/api/applications/{application['id']}/offer",
        json={"salary_min": 20, "salary_max": 24, "start_date": "2030-03-01"},
        headers=auth(employer["access_token"]),
    )
    assert created.status_code == 200
    accepted = client.post(
        f"/api/applications/{application['id']}/offer/respond",
        json={"action": "accept"},
        headers=auth(seeker["access_token"]),
    )
    assert accepted.status_code == 200

    outsider = register(client, "pipe-seeker-outsider", "seeker")
    forbidden_confirm = client.post(
        f"/api/applications/{application['id']}/onboarding/confirm",
        json={},
        headers=auth(outsider["access_token"]),
    )
    assert forbidden_confirm.status_code == 403

    other_employer = register(client, "pipe-hr-outsider", "employer", company="别家公司")
    forbidden_result = client.post(
        f"/api/applications/{application['id']}/onboarding/result",
        json={"result": "hired"},
        headers=auth(other_employer["access_token"]),
    )
    assert forbidden_result.status_code == 403

    abandoned = client.post(
        f"/api/applications/{application['id']}/onboarding/abandon",
        json={"note": "已接受其他机会"},
        headers=auth(seeker["access_token"]),
    )
    assert abandoned.status_code == 200, abandoned.text
    data = abandoned.json()["data"]
    assert data["status"] == "abandoned"
    assert data["onboarding"]["result"] == "abandoned"
    assert data["events"][-1]["to_status"] == "abandoned"

    employer_notes = client.get(
        "/api/notifications", headers=auth(employer["access_token"])
    ).json()["data"]["items"]
    assert any(item["type"] == "onboarding_result" for item in employer_notes)

    # 放弃后不能再确认或记录结果
    confirm_again = client.post(
        f"/api/applications/{application['id']}/onboarding/confirm",
        json={},
        headers=auth(seeker["access_token"]),
    )
    assert confirm_again.status_code == 400


def test_onboarding_requires_accepted_offer(client):
    seeker, employer, _, application = setup_application(client, "-9")

    confirm = client.post(
        f"/api/applications/{application['id']}/onboarding/confirm",
        json={},
        headers=auth(seeker["access_token"]),
    )
    assert confirm.status_code == 400

    result = client.post(
        f"/api/applications/{application['id']}/onboarding/result",
        json={"result": "hired"},
        headers=auth(employer["access_token"]),
    )
    assert result.status_code == 400

    offer = client.post(
        f"/api/applications/{application['id']}/offer",
        json={"salary_min": 20, "salary_max": 24, "start_date": "2030-04-01"},
        headers=auth(employer["access_token"]),
    )
    assert offer.status_code == 200
    accepted = client.post(
        f"/api/applications/{application['id']}/offer/respond",
        json={"action": "accept"},
        headers=auth(seeker["access_token"]),
    )
    assert accepted.status_code == 200

    # 已进入入职阶段，不能再重新发起 Offer
    again = client.post(
        f"/api/applications/{application['id']}/offer",
        json={"salary_min": 20, "salary_max": 24},
        headers=auth(employer["access_token"]),
    )
    assert again.status_code == 400
    assert "入职" in again.json()["message"]


def test_new_application_notifies_employer(client):
    _, employer, _, application = setup_application(client, "-6")

    notes = client.get(
        "/api/notifications", headers=auth(employer["access_token"])
    ).json()["data"]["items"]
    new_notes = [item for item in notes if item["type"] == "new_application"]
    assert len(new_notes) == 1
    assert new_notes[0]["payload"]["application_id"] == application["id"]
