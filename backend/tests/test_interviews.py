import json

from tests.conftest import attach_resume, auth, create_job, register, standard_structured

QUESTION_COUNT = 6


def fake_llm():
    async def fake_chat(messages, tools=None, tool_choice=None, temperature=None, response_format=None):  # noqa: ANN001, ARG001
        system = messages[0]["content"]
        if "出 6 道中文面试题" in system:
            payload = {
                "questions": [
                    {
                        "id": f"q{i}",
                        "category": "technical" if i <= 2 else "project" if i <= 4 else "behavior",
                        "question": f"第 {i} 题：请介绍相关经验",
                        "focus": "考察点",
                        "reference_points": ["要点A", "要点B"],
                    }
                    for i in range(1, QUESTION_COUNT + 1)
                ]
            }
        elif "面试评估官" in system:
            payload = {
                "results": [
                    {"question_id": f"q{i}", "score": 70 + i, "rationale": "回答覆盖要点"}
                    for i in range(1, QUESTION_COUNT + 1)
                ]
            }
        else:
            payload = {
                "overall_score": 78,
                "dimensions": {"skills": 80, "project": 76, "communication": 82, "motivation": 74},
                "strengths": ["技术栈匹配", "项目有量化成果"],
                "risks": ["缺少框架迁移经验"],
                "suggestions": ["补充 RESTful 设计案例"],
                "summary": "整体达到可推进面试的水平",
            }
        return {"role": "assistant", "content": json.dumps(payload, ensure_ascii=False)}

    return fake_chat


def setup_entities(client):
    employer = register(client, "it-hr", "employer", company="星澜科技")
    other_employer = register(client, "it-hr2", "employer", company="云枢智能")
    seeker = register(client, "it-seeker", "seeker")
    other_seeker = register(client, "it-seeker2", "seeker")
    job = create_job(client, employer["access_token"])
    attach_resume(seeker["user"]["id"], [0.1] * 8, standard_structured())
    return employer, other_employer, seeker, other_seeker, job


def test_full_interview_flow(client, monkeypatch):
    monkeypatch.setattr("app.services.interview_service.chat_completion", fake_llm())
    employer, other_employer, seeker, _, job = setup_entities(client)

    application = client.post(
        "/api/applications",
        json={"job_id": job["id"]},
        headers=auth(seeker["access_token"]),
    ).json()["data"]

    created = client.post(
        "/api/interviews", json={"job_id": job["id"]}, headers=auth(seeker["access_token"])
    )
    assert created.status_code == 200, created.text
    interview = created.json()["data"]
    assert interview["status"] == "in_progress"
    questions = interview["plan"]["questions"]
    assert len(questions) == QUESTION_COUNT

    # 未答完不能生成报告
    incomplete = client.post(
        f"/api/interviews/{interview['id']}/complete",
        headers=auth(seeker["access_token"]),
    )
    assert incomplete.status_code == 400

    for question in questions:
        answered = client.post(
            f"/api/interviews/{interview['id']}/answers",
            json={"question_id": question["id"], "answer": "我的回答是……"},
            headers=auth(seeker["access_token"]),
        )
        assert answered.status_code == 200, answered.text

    completed = client.post(
        f"/api/interviews/{interview['id']}/complete",
        headers=auth(seeker["access_token"]),
    )
    assert completed.status_code == 200, completed.text
    result = completed.json()["data"]
    assert result["status"] == "completed"
    assert result["report"]["overall_score"] == 78
    assert len(result["answers"]) == QUESTION_COUNT
    assert all("score" in item for item in result["answers"])

    mine = client.get("/api/interviews/mine", headers=auth(seeker["access_token"]))
    assert mine.json()["data"]["items"][0]["status"] == "completed"

    report = client.get(
        f"/api/interviews/application/{application['id']}",
        headers=auth(employer["access_token"]),
    )
    assert report.status_code == 200
    assert report.json()["data"]["report"]["overall_score"] == 78

    # 其他公司无权查看
    forbidden = client.get(
        f"/api/interviews/application/{application['id']}",
        headers=auth(other_employer["access_token"]),
    )
    assert forbidden.status_code == 403


def test_interview_permissions_and_validation(client, monkeypatch):
    monkeypatch.setattr("app.services.interview_service.chat_completion", fake_llm())
    _, _, seeker, other_seeker, job = setup_entities(client)

    created = client.post(
        "/api/interviews", json={"job_id": job["id"]}, headers=auth(seeker["access_token"])
    ).json()["data"]

    stranger = client.get(
        f"/api/interviews/{created['id']}", headers=auth(other_seeker["access_token"])
    )
    assert stranger.status_code == 404

    bad_question = client.post(
        f"/api/interviews/{created['id']}/answers",
        json={"question_id": "q999", "answer": "x"},
        headers=auth(seeker["access_token"]),
    )
    assert bad_question.status_code == 400

    no_resume = client.post(
        "/api/interviews", json={"job_id": job["id"]}, headers=auth(other_seeker["access_token"])
    )
    assert no_resume.status_code == 400

    employer_cannot_start = client.post(
        "/api/interviews", json={"job_id": job["id"]}, headers=auth(
            register(client, "it-hr3", "employer")["access_token"]
        )
    )
    assert employer_cannot_start.status_code == 403
