import os
import tempfile
from pathlib import Path

# 必须在导入 app 之前设置，确保测试使用独立数据库与假密钥（不触网）
_TEST_DIR = Path(tempfile.mkdtemp(prefix="jobcopilot_test_"))
os.environ["DATABASE_URL"] = f"sqlite:///{(_TEST_DIR / 'test.db').as_posix()}"
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["CHAT_API_KEY"] = "test-key"
os.environ["EMBEDDING_API_KEY"] = "test-key"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Job, Resume  # noqa: E402


@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as test_client:
        yield test_client
    Base.metadata.drop_all(bind=engine)


def register(client: TestClient, username: str, role: str, company: str | None = None) -> dict:
    payload = {
        "username": username,
        "password": "demo1234",
        "role": role,
        "display_name": username,
    }
    if company:
        payload["company_name"] = company
    response = client.post("/api/auth/register", json=payload)
    assert response.status_code == 200, response.text
    return response.json()["data"]


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def create_job(client: TestClient, token: str, **overrides) -> dict:
    payload = {
        "title": "Python 后端工程师",
        "description": "负责后端服务开发",
        "required_skills": ["Python", "FastAPI", "MySQL"],
        "preferred_skills": ["Docker"],
        "experience_min": 3,
        "experience_max": 5,
        "location": "上海",
        "salary_min": 25,
        "salary_max": 35,
    }
    payload.update(overrides)
    response = client.post("/api/jobs", json=payload, headers=auth(token))
    assert response.status_code == 200, response.text
    return response.json()["data"]


def attach_resume(user_id: int, embedding: list[float], structured: dict) -> int:
    with SessionLocal() as db:
        resume = Resume(
            user_id=user_id,
            raw_text="张三的简历",
            structured=structured,
            embedding=embedding,
            source="paste",
        )
        db.add(resume)
        db.commit()
        db.refresh(resume)
        return resume.id


def set_job_embedding(job_id: int, embedding: list[float]) -> None:
    with SessionLocal() as db:
        job = db.get(Job, job_id)
        assert job is not None
        job.embedding = embedding
        db.commit()


def standard_structured() -> dict:
    return {
        "name": "张三",
        "title": "后端开发工程师",
        "skills": ["Python", "FastAPI", "MySQL", "Redis", "Docker"],
        "years_of_experience": 3,
        "education": [
            {"school": "复旦大学", "degree": "本科", "major": "计算机", "period": "2016-2020"}
        ],
        "work_experience": [
            {"company": "某公司", "role": "后端", "period": "2020-2023", "highlights": ["做过核心系统"]}
        ],
        "expectations": {
            "locations": ["上海"],
            "salary_min": 25,
            "salary_max": 35,
            "job_types": ["全职"],
        },
    }
