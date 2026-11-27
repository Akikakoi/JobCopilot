from app.db import SessionLocal
from app.models import Conversation
from tests.conftest import attach_resume, auth, create_job, register, standard_structured


def setup_application(client) -> tuple[dict, dict, dict]:
    seeker = register(client, "msg-seeker", "seeker")
    employer = register(client, "msg-hr", "employer", company="星澜科技")
    attach_resume(seeker["user"]["id"], [0.1] * 8, standard_structured())
    job = create_job(client, employer["access_token"])
    application = client.post(
        "/api/applications",
        json={"job_id": job["id"]},
        headers=auth(seeker["access_token"]),
    ).json()["data"]
    return seeker, employer, application


def test_conversation_created_with_application(client):
    seeker, employer, _ = setup_application(client)

    seeker_list = client.get("/api/conversations", headers=auth(seeker["access_token"]))
    assert seeker_list.status_code == 200
    items = seeker_list.json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["other_name"] == "星澜科技"
    assert items[0]["unread"] == 0

    employer_list = client.get(
        "/api/conversations", headers=auth(employer["access_token"])
    )
    assert len(employer_list.json()["data"]["items"]) == 1


def test_send_message_and_read_flow(client):
    seeker, employer, application = setup_application(client)

    conversation_id = client.get(
        "/api/conversations", headers=auth(seeker["access_token"])
    ).json()["data"]["items"][0]["id"]

    sent = client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={"content": "  你好，想了解一下团队的 tech stack。 "},
        headers=auth(seeker["access_token"]),
    )
    assert sent.status_code == 200, sent.text
    assert sent.json()["data"]["content"] == "你好，想了解一下团队的 tech stack。"
    assert sent.json()["data"]["mine"] is True

    employer_list = client.get(
        "/api/conversations", headers=auth(employer["access_token"])
    ).json()["data"]
    assert employer_list["items"][0]["unread"] == 1
    assert "tech stack" in employer_list["items"][0]["last_message"]["content"]
    assert employer_list["unread"] == 1

    messages = client.get(
        f"/api/conversations/{conversation_id}/messages",
        headers=auth(employer["access_token"]),
    ).json()["data"]["items"]
    assert len(messages) == 1
    assert messages[0]["mine"] is False

    read = client.post(
        f"/api/conversations/{conversation_id}/read",
        headers=auth(employer["access_token"]),
    )
    assert read.status_code == 200
    assert read.json()["data"]["updated"] == 1

    unread = client.get(
        "/api/conversations/unread-count", headers=auth(employer["access_token"])
    ).json()["data"]["unread"]
    assert unread == 0

    reply = client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={"content": "我们主要用 FastAPI 和 MySQL。"},
        headers=auth(employer["access_token"]),
    )
    assert reply.status_code == 200
    assert reply.json()["data"]["mine"] is True

    seeker_unread = client.get(
        "/api/conversations/unread-count", headers=auth(seeker["access_token"])
    ).json()["data"]["unread"]
    assert seeker_unread == 1

    # 增量拉取
    incremental = client.get(
        f"/api/conversations/{conversation_id}/messages?after_id={sent.json()['data']['id']}",
        headers=auth(seeker["access_token"]),
    ).json()["data"]["items"]
    assert len(incremental) == 1
    assert incremental[0]["mine"] is False


def test_conversation_permissions_and_validation(client):
    seeker, employer, _ = setup_application(client)
    other_seeker = register(client, "msg-seeker2", "seeker")
    other_employer = register(client, "msg-hr2", "employer", company="云枢智能")

    conversation_id = client.get(
        "/api/conversations", headers=auth(seeker["access_token"])
    ).json()["data"]["items"][0]["id"]

    for token in (other_seeker["access_token"], other_employer["access_token"]):
        forbidden_read = client.get(
            f"/api/conversations/{conversation_id}/messages", headers=auth(token)
        )
        assert forbidden_read.status_code == 403
        forbidden_send = client.post(
            f"/api/conversations/{conversation_id}/messages",
            json={"content": "hi"},
            headers=auth(token),
        )
        assert forbidden_send.status_code == 403

    blank = client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={"content": "   "},
        headers=auth(seeker["access_token"]),
    )
    assert blank.status_code == 400
    assert "不能为空" in blank.json()["message"]

    too_long = client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={"content": "x" * 2001},
        headers=auth(seeker["access_token"]),
    )
    assert too_long.status_code == 422


def test_message_pagination(client):
    seeker, employer, _ = setup_application(client)
    conversation_id = client.get(
        "/api/conversations", headers=auth(seeker["access_token"])
    ).json()["data"]["items"][0]["id"]

    ids = []
    for index in range(12):
        sent = client.post(
            f"/api/conversations/{conversation_id}/messages",
            json={"content": f"消息 {index}"},
            headers=auth(seeker["access_token"]),
        )
        assert sent.status_code == 200, sent.text
        ids.append(sent.json()["data"]["id"])

    latest = client.get(
        f"/api/conversations/{conversation_id}/messages?limit=5",
        headers=auth(seeker["access_token"]),
    ).json()["data"]
    assert [item["id"] for item in latest["items"]] == ids[-5:]
    assert latest["has_more"] is True

    older = client.get(
        f"/api/conversations/{conversation_id}/messages"
        f"?limit=5&before_id={latest['items'][0]['id']}",
        headers=auth(seeker["access_token"]),
    ).json()["data"]
    assert [item["id"] for item in older["items"]] == ids[2:7]
    assert older["has_more"] is True

    oldest = client.get(
        f"/api/conversations/{conversation_id}/messages"
        f"?before_id={older['items'][0]['id']}",
        headers=auth(seeker["access_token"]),
    ).json()["data"]
    assert [item["id"] for item in oldest["items"]] == ids[:2]
    assert oldest["has_more"] is False

    conflict = client.get(
        f"/api/conversations/{conversation_id}/messages?after_id=1&before_id=2",
        headers=auth(seeker["access_token"]),
    )
    assert conflict.status_code == 400


def test_legacy_application_conversation_is_created_lazily(client):
    seeker, employer, application = setup_application(client)

    with SessionLocal() as db:
        conversation = db.query(Conversation).one()
        db.delete(conversation)
        db.commit()

    items = client.get(
        "/api/conversations", headers=auth(employer["access_token"])
    ).json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["application_id"] == application["id"]


def test_seeker_starts_conversation_before_applying(client):
    seeker = register(client, "direct-seeker", "seeker")
    employer = register(client, "direct-hr", "employer", company="星澜科技")
    attach_resume(seeker["user"]["id"], [0.1] * 8, standard_structured())
    job = create_job(client, employer["access_token"])

    started = client.post(
        "/api/conversations",
        json={"job_id": job["id"]},
        headers=auth(seeker["access_token"]),
    )
    assert started.status_code == 200, started.text
    conversation_id = started.json()["data"]["id"]
    assert started.json()["data"]["created"] is True
    assert started.json()["data"]["application_id"] is None

    items = client.get(
        "/api/conversations", headers=auth(seeker["access_token"])
    ).json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["id"] == conversation_id
    assert items[0]["application_id"] is None
    assert items[0]["job_title"] == job["title"]
    assert items[0]["other_name"] == "星澜科技"
    assert items[0]["source"] == "direct"

    sent = client.post(
        f"/api/conversations/{conversation_id}/messages",
        json={"content": "你好，想先了解一下这个岗位。"},
        headers=auth(seeker["access_token"]),
    )
    assert sent.status_code == 200, sent.text

    employer_items = client.get(
        "/api/conversations", headers=auth(employer["access_token"])
    ).json()["data"]["items"]
    assert len(employer_items) == 1
    assert employer_items[0]["unread"] == 1
    assert employer_items[0]["other_name"] == standard_structured()["name"]

    # 重复发起返回同一个会话，不产生碎片
    again = client.post(
        "/api/conversations",
        json={"job_id": job["id"]},
        headers=auth(seeker["access_token"]),
    )
    assert again.json()["data"]["id"] == conversation_id
    assert again.json()["data"]["created"] is False


def test_apply_after_chatting_reuses_direct_conversation(client):
    seeker = register(client, "reuse-seeker", "seeker")
    employer = register(client, "reuse-hr", "employer", company="星澜科技")
    attach_resume(seeker["user"]["id"], [0.1] * 8, standard_structured())
    job = create_job(client, employer["access_token"])

    conversation_id = client.post(
        "/api/conversations",
        json={"job_id": job["id"]},
        headers=auth(seeker["access_token"]),
    ).json()["data"]["id"]

    application = client.post(
        "/api/applications",
        json={"job_id": job["id"]},
        headers=auth(seeker["access_token"]),
    ).json()["data"]

    items = client.get(
        "/api/conversations", headers=auth(seeker["access_token"])
    ).json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["id"] == conversation_id
    assert items[0]["application_id"] == application["id"]

    # 投递后再点「立即沟通」仍然命中同一会话
    again = client.post(
        "/api/conversations",
        json={"job_id": job["id"]},
        headers=auth(seeker["access_token"]),
    ).json()["data"]
    assert again["id"] == conversation_id
    assert again["created"] is False


def test_chat_about_another_job_does_not_reuse_bound_application_conversation(client):
    seeker = register(client, "cross-seeker", "seeker")
    employer = register(client, "cross-hr", "employer", company="星澜科技")
    attach_resume(seeker["user"]["id"], [0.1] * 8, standard_structured())
    job_a = create_job(client, employer["access_token"], title="后端工程师 A")
    job_b = create_job(client, employer["access_token"], title="后端工程师 B")

    application = client.post(
        "/api/applications",
        json={"job_id": job_a["id"]},
        headers=auth(seeker["access_token"]),
    ).json()["data"]

    items = client.get(
        "/api/conversations", headers=auth(seeker["access_token"])
    ).json()["data"]["items"]
    bound = next(item for item in items if item["application_id"] == application["id"])
    assert bound["job_title"] == job_a["title"]

    started = client.post(
        "/api/conversations",
        json={"job_id": job_b["id"]},
        headers=auth(seeker["access_token"]),
    ).json()["data"]
    assert started["created"] is True
    assert started["application_id"] is None
    assert started["job_id"] == job_b["id"]
    assert started["id"] != bound["id"]

    items = client.get(
        "/api/conversations", headers=auth(seeker["access_token"])
    ).json()["data"]["items"]
    assert len(items) == 2
    by_id = {item["id"]: item for item in items}
    assert by_id[started["id"]]["job_title"] == job_b["title"]
    assert by_id[started["id"]]["source"] == "direct"
    assert by_id[bound["id"]]["job_title"] == job_a["title"]

    again = client.post(
        "/api/conversations",
        json={"job_id": job_b["id"]},
        headers=auth(seeker["access_token"]),
    ).json()["data"]
    assert again["id"] == started["id"]
    assert again["created"] is False


def test_direct_conversation_keeps_initial_job_until_application_binding(client):
    seeker = register(client, "bind-seeker", "seeker")
    employer = register(client, "bind-hr", "employer", company="星澜科技")
    attach_resume(seeker["user"]["id"], [0.1] * 8, standard_structured())
    job_a = create_job(client, employer["access_token"], title="岗位 A")
    job_b = create_job(client, employer["access_token"], title="岗位 B")

    first = client.post(
        "/api/conversations",
        json={"job_id": job_a["id"]},
        headers=auth(seeker["access_token"]),
    ).json()["data"]
    second = client.post(
        "/api/conversations",
        json={"job_id": job_b["id"]},
        headers=auth(seeker["access_token"]),
    ).json()["data"]
    assert second["id"] == first["id"]
    assert second["created"] is False

    items = client.get(
        "/api/conversations", headers=auth(seeker["access_token"])
    ).json()["data"]["items"]
    conversation = next(item for item in items if item["id"] == first["id"])
    assert conversation["job_title"] == job_a["title"]
    assert conversation["application_id"] is None

    application = client.post(
        "/api/applications",
        json={"job_id": job_b["id"]},
        headers=auth(seeker["access_token"]),
    ).json()["data"]

    items = client.get(
        "/api/conversations", headers=auth(seeker["access_token"])
    ).json()["data"]["items"]
    conversation = next(item for item in items if item["id"] == first["id"])
    assert conversation["application_id"] == application["id"]
    assert conversation["job_title"] == job_b["title"]


def test_employer_can_start_conversation_and_scope_is_enforced(client):
    seeker = register(client, "reach-seeker", "seeker")
    employer = register(client, "reach-hr", "employer", company="星澜科技")
    other_employer = register(client, "reach-hr2", "employer", company="云枢智能")
    attach_resume(seeker["user"]["id"], [0.1] * 8, standard_structured())
    job = create_job(client, employer["access_token"])

    started = client.post(
        "/api/conversations",
        json={"seeker_user_id": seeker["user"]["id"], "job_id": job["id"]},
        headers=auth(employer["access_token"]),
    )
    assert started.status_code == 200, started.text
    conversation_id = started.json()["data"]["id"]

    items = client.get(
        "/api/conversations", headers=auth(seeker["access_token"])
    ).json()["data"]["items"]
    assert len(items) == 1
    assert items[0]["id"] == conversation_id
    assert items[0]["other_name"] == "星澜科技"

    foreign_job = client.post(
        "/api/conversations",
        json={"seeker_user_id": seeker["user"]["id"], "job_id": job["id"]},
        headers=auth(other_employer["access_token"]),
    )
    assert foreign_job.status_code == 400

    spoof = client.post(
        "/api/conversations",
        json={"job_id": job["id"], "seeker_user_id": seeker["user"]["id"]},
        headers=auth(seeker["access_token"]),
    )
    assert spoof.status_code == 400


def test_messages_carry_invite_and_offer_cards(client):
    seeker, employer, application = setup_application(client)
    app_id = application["id"]

    conversation_id = client.get(
        "/api/conversations", headers=auth(seeker["access_token"])
    ).json()["data"]["items"][0]["id"]

    invite = client.post(
        f"/api/applications/{app_id}/interview-invites",
        json={
            "scheduled_at": "2030-01-01T10:00:00",
            "duration_minutes": 60,
            "mode": "video",
            "location": "腾讯会议 123-456",
        },
        headers=auth(employer["access_token"]),
    ).json()["data"]

    items = client.get(
        f"/api/conversations/{conversation_id}/messages",
        headers=auth(seeker["access_token"]),
    ).json()["data"]["items"]
    cards = [item for item in items if item["kind"] == "interview_invite"]
    assert len(cards) == 1
    card = cards[0]
    assert card["ref_id"] == invite["id"]
    assert card["mine"] is False
    assert "面试邀约" in card["content"]
    assert card["card"]["status"] == "pending"
    assert card["card"]["mode_label"] == "视频面试"

    # 候选人确认后卡片状态实时更新，不新增消息
    confirmed = client.post(
        f"/api/applications/{app_id}/interview-invites/{invite['id']}/respond",
        json={"action": "confirm", "note": "准时参加"},
        headers=auth(seeker["access_token"]),
    )
    assert confirmed.status_code == 200, confirmed.text
    items = client.get(
        f"/api/conversations/{conversation_id}/messages",
        headers=auth(seeker["access_token"]),
    ).json()["data"]["items"]
    assert len([item for item in items if item["kind"] == "interview_invite"]) == 1
    assert items[-1]["card"]["status"] == "confirmed"

    # Offer 也以卡片形式进入同一会话
    offer = client.post(
        f"/api/applications/{app_id}/offer",
        json={
            "salary_min": 30,
            "salary_max": 40,
            "start_date": "2030-02-01",
            "expires_at": "2030-01-20T00:00:00",
            "note": "期待加入",
        },
        headers=auth(employer["access_token"]),
    )
    assert offer.status_code == 200, offer.text
    offer_id = offer.json()["data"]["id"]

    items = client.get(
        f"/api/conversations/{conversation_id}/messages",
        headers=auth(employer["access_token"]),
    ).json()["data"]["items"]
    offer_cards = [item for item in items if item["kind"] == "offer"]
    assert len(offer_cards) == 1
    assert offer_cards[0]["mine"] is True
    assert offer_cards[0]["card"]["salary_min"] == 30

    # 修改 Offer 只更新原卡片，不刷屏
    client.post(
        f"/api/applications/{app_id}/offer",
        json={"salary_min": 32, "salary_max": 42, "start_date": "2030-02-01"},
        headers=auth(employer["access_token"]),
    )
    items = client.get(
        f"/api/conversations/{conversation_id}/messages",
        headers=auth(seeker["access_token"]),
    ).json()["data"]["items"]
    offer_cards = [item for item in items if item["kind"] == "offer"]
    assert len(offer_cards) == 1
    assert offer_cards[0]["ref_id"] == offer_id
    assert offer_cards[0]["card"]["salary_min"] == 32

    client.post(
        f"/api/applications/{app_id}/offer/respond",
        json={"action": "accept"},
        headers=auth(seeker["access_token"]),
    )
    items = client.get(
        f"/api/conversations/{conversation_id}/messages",
        headers=auth(seeker["access_token"]),
    ).json()["data"]["items"]
    assert [item for item in items if item["kind"] == "offer"][0]["card"]["status"] == "accepted"
