import asyncio
import json

from app.agent import tools as tool_registry
from app.db import SessionLocal
from app.models import Subscription, User
from tests.conftest import attach_resume, auth, create_job, register, standard_structured


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


def test_tool_schemas_expose_phase2_tools():
    seeker_names = {tool.name for tool in tool_registry.TOOLSETS["seeker"]}
    employer_names = {tool.name for tool in tool_registry.TOOLSETS["employer"]}
    assert {"create_mock_interview", "submit_interview_answer", "get_interview_report"} <= seeker_names
    assert {"create_subscription", "list_unread_notifications"} <= seeker_names
    assert "get_candidate_interview_report" in employer_names
