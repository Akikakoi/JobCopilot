import asyncio
import json

from app.agent import tools as tool_registry
from app.db import SessionLocal
from app.models import Subscription, User
from tests.conftest import (
    attach_resume,
    auth,
    create_job,
    register,
    set_job_embedding,
    standard_structured,
)


def fake_interview_llm():
    async def fake_chat(messages, tools=None, tool_choice=None, temperature=None, response_format=None):  # noqa: ANN001, ARG001
        system = messages[0]["content"]
        if "出 6 道中文面试题" in system:
            payload = {
                "questions": [
                    {
                        "id": f"q{i}",
                        "category": "technical",
                        "question": f"第 {i} 题",
                        "focus": "考察点",
                        "reference_points": ["要点"],
                    }
                    for i in range(1, 7)
                ]
            }
        elif "面试评估官" in system:
            payload = {
                "results": [
                    {"question_id": f"q{i}", "score": 70 + i, "rationale": "ok"} for i in range(1, 7)
                ]
            }
        else:
            payload = {
                "overall_score": 78,
                "dimensions": {"skills": 80, "project": 76, "communication": 82, "motivation": 74},
                "strengths": ["技能匹配"],
                "risks": ["项目深度一般"],
                "suggestions": ["补充量化成果"],
                "summary": "整体可推进",
            }
        return {"role": "assistant", "content": json.dumps(payload, ensure_ascii=False)}

    return fake_chat


def get_user(username: str) -> User:
    with SessionLocal() as db:
        user = db.query(User).filter(User.username == username).one()
        db.expunge(user)
        return user


def run_tool(agent_type: str, name: str, user: User, **kwargs):
    tool = tool_registry.get_tool(agent_type, name)
    assert tool is not None, name
    with SessionLocal() as db:
        fresh = db.get(User, user.id)
        return asyncio.run(tool.handler(db, fresh, **kwargs))


def test_interview_tools_full_flow(client, monkeypatch):
    monkeypatch.setattr("app.services.interview_service.chat_completion", fake_interview_llm())
    employer = register(client, "tool-hr", "employer", company="星澜科技")
    seeker = register(client, "tool-seeker", "seeker")
    job = create_job(client, employer["access_token"])
    attach_resume(seeker["user"]["id"], [0.1] * 8, standard_structured())
    user = get_user("tool-seeker")

    created = run_tool("seeker", "create_mock_interview", user, job_id=job["id"])
    assert "interview_id" in created, created
    assert created["total_questions"] == 6
    assert created["first_question"]["id"] == "q1"

    interview_id = created["interview_id"]
    last = None
    for index in range(6):
        last = run_tool(
            "seeker",
            "submit_interview_answer",
            user,
            interview_id=interview_id,
            answer=f"这是第 {index + 1} 题的回答，覆盖了关键要点。",
        )
        assert "error" not in last, last
    assert last["all_answered"] is True

    report = run_tool("seeker", "get_interview_report", user, interview_id=interview_id)
    assert report["status"] == "completed"
    assert report["overall_score"] == 78
    assert report["suggestions"]


def test_subscription_and_notification_tools(client):
    seeker = register(client, "tool-seeker", "seeker")
    user = get_user("tool-seeker")

    created = run_tool(
        "seeker",
        "create_subscription",
        user,
        keywords="Python",
        location="上海",
        salary_min=25,
        skills=["Python"],
        match_score_min=60,
    )
    assert created["subscription_id"]
    with SessionLocal() as db:
        subscription = db.get(Subscription, created["subscription_id"])
        assert subscription is not None
        assert subscription.filters["location"] == "上海"

    notifications = run_tool("seeker", "list_unread_notifications", user)
    assert notifications["unread"] == 0


def test_employer_interview_report_tool_permissions(client, monkeypatch):
    monkeypatch.setattr("app.services.interview_service.chat_completion", fake_interview_llm())
    employer = register(client, "tool-hr", "employer", company="星澜科技")
    other = register(client, "tool-hr2", "employer", company="云枢智能")
    seeker = register(client, "tool-seeker", "seeker")
    job = create_job(client, employer["access_token"])
    attach_resume(seeker["user"]["id"], [0.1] * 8, standard_structured())
    application = client.post(
        "/api/applications", json={"job_id": job["id"]}, headers=auth(seeker["access_token"])
    ).json()["data"]

    seeker_user = get_user("tool-seeker")
    created = run_tool("seeker", "create_mock_interview", seeker_user, job_id=job["id"])
    for index in range(6):
        run_tool(
            "seeker",
            "submit_interview_answer",
            seeker_user,
            interview_id=created["interview_id"],
            answer=f"回答 {index}",
        )
    run_tool("seeker", "get_interview_report", seeker_user, interview_id=created["interview_id"])

    report = run_tool(
        "employer",
        "get_candidate_interview_report",
        get_user("tool-hr"),
        application_id=application["id"],
    )
    assert report["overall_score"] == 78

    forbidden = run_tool(
        "employer",
        "get_candidate_interview_report",
        get_user("tool-hr2"),
        application_id=application["id"],
    )
    assert "无权" in forbidden["error"]


def test_pipeline_agent_tools(client):
    employer = register(client, "tool-hr", "employer", company="星澜科技")
    other = register(client, "tool-hr2", "employer", company="云枢智能")
    seeker = register(client, "tool-seeker", "seeker")
    job = create_job(client, employer["access_token"])
    attach_resume(seeker["user"]["id"], [0.1] * 8, standard_structured())
    application = client.post(
        "/api/applications", json={"job_id": job["id"]}, headers=auth(seeker["access_token"])
    ).json()["data"]

    invite = run_tool(
        "employer",
        "create_interview_invite",
        get_user("tool-hr"),
        application_id=application["id"],
        scheduled_at="2030-01-01T10:00",
        duration_minutes=60,
        mode="video",
        location="腾讯会议 123-456",
        note="技术二面",
    )
    assert "error" not in invite, invite
    assert invite["status"] == "pending"

    pipeline = run_tool("seeker", "list_my_pipeline", get_user("tool-seeker"))
    assert pipeline["applications"][0]["status"] == "interview"
    assert pipeline["applications"][0]["interview_invites"][0]["invite_id"] == invite["invite_id"]

    confirmed = run_tool(
        "seeker",
        "respond_interview_invite",
        get_user("tool-seeker"),
        application_id=application["id"],
        invite_id=invite["invite_id"],
        action="confirm",
        note="准时参加",
    )
    assert confirmed["status"] == "confirmed", confirmed

    completed = run_tool(
        "employer",
        "complete_interview_invite",
        get_user("tool-hr"),
        application_id=application["id"],
        invite_id=invite["invite_id"],
        note="一面通过",
    )
    assert completed["status"] == "completed", completed

    offer = run_tool(
        "employer",
        "create_offer",
        get_user("tool-hr"),
        application_id=application["id"],
        salary_min=30,
        salary_max=38,
        start_date="2030-02-01",
        expires_at="2030-01-10T23:59:59",
        note="期权另议",
    )
    assert "error" not in offer, offer
    assert offer["status"] == "pending"

    accepted = run_tool(
        "seeker",
        "respond_offer",
        get_user("tool-seeker"),
        application_id=application["id"],
        action="accept",
        note="接受",
    )
    assert accepted["status"] == "accepted", accepted

    confirmed_onboarding = run_tool(
        "seeker",
        "confirm_onboarding",
        get_user("tool-seeker"),
        application_id=application["id"],
        note="会按时到岗",
    )
    assert confirmed_onboarding["status"] == "onboarding", confirmed_onboarding
    assert confirmed_onboarding["onboarding"]["confirmed"] is True
    assert confirmed_onboarding["onboarding"]["date"] == "2030-02-01"

    pipeline = run_tool("seeker", "list_my_pipeline", get_user("tool-seeker"))
    assert pipeline["applications"][0]["next_step"] == "等待招聘方记录到岗结果"

    hired = run_tool(
        "employer",
        "record_onboarding_result",
        get_user("tool-hr"),
        application_id=application["id"],
        result="hired",
        onboarding_date="2030-02-03",
        note="已按期到岗",
    )
    assert hired["status"] == "hired", hired
    assert hired["onboarding"]["result"] == "hired"

    # 其他公司不能操作该投递
    forbidden = run_tool(
        "employer",
        "create_offer",
        get_user("tool-hr2"),
        application_id=application["id"],
        salary_min=10,
        salary_max=12,
    )
    assert "error" in forbidden
    assert "招聘方" in forbidden["error"]

    # 非法时间格式会返回可读错误
    bad_time = run_tool(
        "employer",
        "create_interview_invite",
        get_user("tool-hr"),
        application_id=application["id"],
        scheduled_at="明天下午",
    )
    assert "时间格式" in bad_time["error"]


def test_pipeline_agent_tool_decline_and_cancel(client):
    employer = register(client, "tool-hr", "employer", company="星澜科技")
    other = register(client, "tool-hr2", "employer", company="云枢智能")
    seeker = register(client, "tool-seeker", "seeker")
    job = create_job(client, employer["access_token"])
    attach_resume(seeker["user"]["id"], [0.1] * 8, standard_structured())
    application = client.post(
        "/api/applications", json={"job_id": job["id"]}, headers=auth(seeker["access_token"])
    ).json()["data"]

    invite = run_tool(
        "employer",
        "create_interview_invite",
        get_user("tool-hr"),
        application_id=application["id"],
        scheduled_at="2030-01-01T10:00:00+08:00",
    )
    assert "error" not in invite, invite

    # 带时区的时间会换算成 UTC 存储
    pipeline = run_tool("seeker", "list_my_pipeline", get_user("tool-seeker"))
    scheduled = pipeline["applications"][0]["interview_invites"][0]["scheduled_at"]
    assert scheduled.hour == 2 and scheduled.minute == 0

    # 候选人拒绝邀约
    declined = run_tool(
        "seeker",
        "respond_interview_invite",
        get_user("tool-seeker"),
        application_id=application["id"],
        invite_id=invite["invite_id"],
        action="decline",
        note="当天有冲突",
    )
    assert declined["status"] == "declined", declined

    # 已结束的邀约不能再次响应
    again = run_tool(
        "seeker",
        "respond_interview_invite",
        get_user("tool-seeker"),
        application_id=application["id"],
        invite_id=invite["invite_id"],
        action="confirm",
    )
    assert "error" in again

    # 新一轮邀约：其他公司不能取消，本公司可以取消
    second = run_tool(
        "employer",
        "create_interview_invite",
        get_user("tool-hr"),
        application_id=application["id"],
        scheduled_at="2030-01-05T14:00",
        mode="onsite",
        location="会议室 A",
    )
    forbidden = run_tool(
        "employer",
        "cancel_interview_invite",
        get_user("tool-hr2"),
        application_id=application["id"],
        invite_id=second["invite_id"],
    )
    assert "error" in forbidden

    cancelled = run_tool(
        "employer",
        "cancel_interview_invite",
        get_user("tool-hr"),
        application_id=application["id"],
        invite_id=second["invite_id"],
        note="面试官临时有安排",
    )
    assert cancelled["status"] == "cancelled", cancelled

    # 非法 action 直接返回错误，不进入服务层
    bad_invite_action = run_tool(
        "seeker",
        "respond_interview_invite",
        get_user("tool-seeker"),
        application_id=application["id"],
        invite_id=invite["invite_id"],
        action="maybe",
    )
    assert "error" in bad_invite_action

    bad_offer_action = run_tool(
        "seeker",
        "respond_offer",
        get_user("tool-seeker"),
        application_id=application["id"],
        action="maybe",
    )
    assert "error" in bad_offer_action

    # 不存在的投递 / 邀约返回可读错误
    missing = run_tool(
        "seeker",
        "respond_interview_invite",
        get_user("tool-seeker"),
        application_id=9999,
        invite_id=9999,
        action="confirm",
    )
    assert "error" in missing


def test_offer_agent_tool_decline_and_candidate_view(client):
    employer = register(client, "tool-hr", "employer", company="星澜科技")
    seeker = register(client, "tool-seeker", "seeker")
    job = create_job(client, employer["access_token"])
    attach_resume(seeker["user"]["id"], [0.1] * 8, standard_structured())
    set_job_embedding(job["id"], [0.1] * 8)
    application = client.post(
        "/api/applications", json={"job_id": job["id"]}, headers=auth(seeker["access_token"])
    ).json()["data"]

    offer = run_tool(
        "employer",
        "create_offer",
        get_user("tool-hr"),
        application_id=application["id"],
        salary_min=30,
        salary_max=38,
        start_date="2030-02-01",
        expires_at="2030-01-10T23:59:59+08:00",
        note="期权另议",
    )
    assert "error" not in offer, offer

    # 候选人列表能看到 Offer 状态
    candidates = run_tool(
        "employer", "list_candidates", get_user("tool-hr"), job_id=job["id"]
    )
    assert candidates["candidates"][0]["offer_status"] == "pending"

    declined = run_tool(
        "seeker",
        "respond_offer",
        get_user("tool-seeker"),
        application_id=application["id"],
        action="decline",
        note="已接受其他机会",
    )
    assert declined["status"] == "declined", declined

    pipeline = run_tool("seeker", "list_my_pipeline", get_user("tool-seeker"))
    item = pipeline["applications"][0]
    assert item["status"] == "rejected"
    assert item["offer"]["status"] == "declined"

    # 投递结束后不能再发 Offer
    again = run_tool(
        "employer",
        "create_offer",
        get_user("tool-hr"),
        application_id=application["id"],
        salary_min=20,
        salary_max=22,
    )
    assert "error" in again


def test_tool_schemas_expose_phase2_tools():
    seeker_names = {tool.name for tool in tool_registry.TOOLSETS["seeker"]}
    employer_names = {tool.name for tool in tool_registry.TOOLSETS["employer"]}
    assert {"create_mock_interview", "submit_interview_answer", "get_interview_report"} <= seeker_names
    assert {"create_subscription", "list_unread_notifications"} <= seeker_names
    assert {"list_my_pipeline", "respond_interview_invite", "respond_offer"} <= seeker_names
    assert "get_candidate_interview_report" in employer_names
    assert {"create_interview_invite", "cancel_interview_invite", "create_offer"} <= employer_names
    assert "complete_interview_invite" in employer_names
