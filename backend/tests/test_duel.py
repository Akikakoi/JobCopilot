import asyncio

from app.agent.duel import stream_duel
from app.db import SessionLocal
from app.models import Application, Company, Job, Resume, User
from app.security import hash_password


def setup_duel_data() -> tuple[int, int, int, int]:
    with SessionLocal() as db:
        employer = User(
            username="duel-hr",
            password_hash=hash_password("demo1234"),
            role="employer",
            display_name="HR",
        )
        db.add(employer)
        db.flush()
        company = Company(owner_user_id=employer.id, name="对谈公司", industry="互联网")
        db.add(company)
        db.flush()
        job = Job(
            company_id=company.id,
            title="Python 后端工程师",
            required_skills=["Python", "FastAPI"],
            experience_min=3,
            experience_max=5,
            location="上海",
            salary_min=25,
            salary_max=35,
            status="open",
        )
        db.add(job)
        db.flush()
        seeker = User(
            username="duel-seeker",
            password_hash=hash_password("demo1234"),
            role="seeker",
            display_name="张三",
        )
        db.add(seeker)
        db.flush()
        resume = Resume(
            user_id=seeker.id,
            raw_text="张三的简历",
            structured={"name": "张三", "skills": ["Python"], "years_of_experience": 3},
            embedding=[0.1, 0.2],
            source="paste",
        )
        db.add(resume)
        db.flush()
        application = Application(
            job_id=job.id, resume_id=resume.id, user_id=seeker.id, status="submitted"
        )
        db.add(application)
        db.commit()
        return employer.id, seeker.id, job.id, application.id


def test_duel_requires_employer(client):
    setup_duel_data()
    with SessionLocal() as db:
        seeker = db.query(User).filter(User.role == "seeker").one()
        job = db.query(Job).one()
        application = db.query(Application).one()

    login = client.post("/api/auth/login", json={"username": seeker.username, "password": "demo1234"})
    token = login.json()["data"]["access_token"]
    response = client.post(
        "/api/agent/duel",
        json={"job_id": job.id, "application_id": application.id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 403


def test_duel_rejects_mismatched_application(client):
    setup_duel_data()
    employer = client.post(
        "/api/auth/login", json={"username": "duel-hr", "password": "demo1234"}
    ).json()["data"]
    with SessionLocal() as db:
        job = db.query(Job).one()
        application = db.query(Application).one()

    response = client.post(
        "/api/agent/duel",
        json={"job_id": job.id + 999, "application_id": application.id},
        headers={"Authorization": f"Bearer {employer['access_token']}"},
    )
    assert response.status_code == 404


def test_duel_alternates_speakers_and_restricts_tools(client, monkeypatch):
    _, _, job_id, application_id = setup_duel_data()
    calls = {"count": 0}

    async def fake_stream(messages, tools=None):  # noqa: ANN001, ARG001
        calls["count"] += 1
        if calls["count"] == 1:
            yield {
                "tool_calls": [
                    {
                        "index": 0,
                        "id": "duel_call_1",
                        "function": {"name": "apply_to_job", "arguments": '{"job_id": 1}'},
                    }
                ]
            }
        else:
            yield {"content": f"第{calls['count']}次发言"}

    monkeypatch.setattr("app.agent.duel.chat_completion_stream", fake_stream)

    async def collect():
        with SessionLocal() as db:
            employer = db.query(User).filter(User.role == "employer").one()
            job = db.query(Job).filter(Job.id == job_id).one()
            application = db.query(Application).filter(Application.id == application_id).one()
            return [event async for event in stream_duel(db, employer, job, application, rounds=2)]

    events = asyncio.run(collect())
    turn_ends = [event for event in events if event["type"] == "turn_end"]
    assert [event["speaker"] for event in turn_ends] == ["seeker", "employer", "seeker", "employer"]
    assert events[-1] == {"type": "done", "turns": 4}

    tool_end = next(event for event in events if event["type"] == "tool_end")
    assert "不可调用" in tool_end["result"]
