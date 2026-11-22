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
