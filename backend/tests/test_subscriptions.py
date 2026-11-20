from datetime import datetime, timedelta, timezone

from app.db import SessionLocal
from app.models import Subscription
from app.services import subscription_service
from tests.conftest import attach_resume, auth, create_job, register, standard_structured


def reset_throttle():
    subscription_service._last_scan.clear()  # noqa: SLF001


def create_subscription(client, token, **filters):
    payload = {
        "name": "上海 Python 高薪",
        "filters": {"location": "上海", "salary_min": 30, "keywords": "Python", **filters},
    }
    response = client.post("/api/subscriptions", json=payload, headers=auth(token))
    assert response.status_code == 200, response.text
    return response.json()["data"]


def test_subscription_crud_and_scan(client):
    reset_throttle()
    seeker = register(client, "sub-seeker", "seeker")
    employer = register(client, "sub-hr", "employer", company="星澜科技")
    attach_resume(seeker["user"]["id"], [0.1] * 8, standard_structured())

    subscription = create_subscription(client, seeker["access_token"])
    assert subscription["active"] is True

    # 匹配的岗位：上海 / 30-45K / Python
    create_job(
        client,
        employer["access_token"],
        title="Python 高级后端",
        location="上海",
        salary_min=30,
        salary_max=45,
        required_skills=["Python", "FastAPI"],
    )
    # 不匹配：北京 / 10-15K
    create_job(
        client,
        employer["access_token"],
        title="Python 初级后端",
        location="北京",
        salary_min=10,
        salary_max=15,
        required_skills=["Python"],
    )

    scan = client.post("/api/subscriptions/scan", headers=auth(seeker["access_token"]))
    assert scan.status_code == 200
    result = scan.json()["data"]
    assert result["skipped"] is False
    assert result["created"] == 1

    notifications = client.get("/api/notifications", headers=auth(seeker["access_token"]))
    data = notifications.json()["data"]
    assert data["unread"] == 1
    assert data["items"][0]["payload"]["title"] == "Python 高级后端"
    notification_id = data["items"][0]["id"]

    # 10 分钟内重复扫描被节流
    again = client.post("/api/subscriptions/scan", headers=auth(seeker["access_token"]))
    assert again.json()["data"]["skipped"] is True

    # 清掉节流并回退水位，仍不会重复提醒（dedupe）
    reset_throttle()
    with SessionLocal() as db:
        row = db.get(Subscription, subscription["id"])
        assert row is not None
        row.last_checked_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=5)
        db.commit()
    rescan = client.post("/api/subscriptions/scan", headers=auth(seeker["access_token"]))
    assert rescan.json()["data"]["created"] == 0

    read = client.post(
        f"/api/notifications/{notification_id}/read",
        headers=auth(seeker["access_token"]),
    )
    assert read.status_code == 200
    assert read.json()["data"]["read"] is True

    unread = client.get(
        "/api/notifications?unread_only=true", headers=auth(seeker["access_token"])
    )
    assert unread.json()["data"]["unread"] == 0

    updated = client.put(
        f"/api/subscriptions/{subscription['id']}",
        json={"active": False, "name": "暂停的订阅"},
        headers=auth(seeker["access_token"]),
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["active"] is False

    deleted = client.delete(
        f"/api/subscriptions/{subscription['id']}", headers=auth(seeker["access_token"])
    )
    assert deleted.status_code == 200


def test_subscription_permissions(client):
    reset_throttle()
    seeker = register(client, "sub-seeker", "seeker")
    other = register(client, "sub-seeker2", "seeker")
    employer = register(client, "sub-hr", "employer", company="星澜科技")
    attach_resume(seeker["user"]["id"], [0.1] * 8, standard_structured())

    subscription = create_subscription(client, seeker["access_token"])

    forbidden_update = client.put(
        f"/api/subscriptions/{subscription['id']}",
        json={"name": "被改"},
        headers=auth(other["access_token"]),
    )
    assert forbidden_update.status_code == 404

    forbidden_role = client.get("/api/subscriptions", headers=auth(employer["access_token"]))
    assert forbidden_role.status_code == 403

    # 生成一条通知，验证跨用户读取被拒
    create_job(client, employer["access_token"])
    client.post("/api/subscriptions/scan", headers=auth(seeker["access_token"]))
    items = client.get("/api/notifications", headers=auth(seeker["access_token"])).json()[
        "data"
    ]["items"]
    if items:
        stolen = client.post(
            f"/api/notifications/{items[0]['id']}/read", headers=auth(other["access_token"])
        )
        assert stolen.status_code == 404
