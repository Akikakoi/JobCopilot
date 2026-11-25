"""岗位定位（求职意向）测试：设置入口、参与匹配、定位诊断。"""

import json

from app.db import SessionLocal
from app.matching.rules import score_resume_job
from app.models import Resume
from tests.conftest import (
    attach_resume,
    auth,
    register,
    standard_structured,
)


async def fake_embed(text: str) -> list[float]:  # noqa: ARG001
    return [0.2] * 8


def fake_extract_structured(name: str = "李四", city: str = "广州"):
    async def _extract(raw_text: str) -> dict:  # noqa: ARG001
        return {
            "name": name,
            "title": "前端开发工程师",
            "skills": ["React", "TypeScript"],
            "years_of_experience": 2,
            "education": [],
            "work_experience": [],
            "expectations": {"locations": [city], "salary_min": 18, "salary_max": 25},
        }

    return _extract


def fake_diagnose():
    async def fake_chat(messages, tools=None, tool_choice=None, temperature=None, response_format=None):  # noqa: ANN001, ARG001
        payload = {
            "positioning": "后端为主力方向，可兼顾数据开发",
            "fits": [
                {
                    "category": "技术研发",
                    "subcategory": "后端开发",
                    "fit_score": 88,
                    "reason": "3 年 Python/FastAPI 经验，有高并发项目",
                    "gap": "缺少大型团队协作经验",
                },
                {
                    "category": "技术研发",
                    "subcategory": "数据开发",
                    "fit_score": 62,
                    "reason": "有 MySQL 与数据处理经验",
                    "gap": "缺数据仓库与调度框架经验",
                },
            ],
            "risks": ["目标薪资略高于当前年限的市场中位数"],
            "next_steps": ["补一个云原生项目", "把高并发经历量化"],
        }
        return {"role": "assistant", "content": json.dumps(payload, ensure_ascii=False)}

    return fake_chat


def test_job_intent_defaults_empty(client):
    seeker = register(client, "intent-empty", "seeker")
    res = client.get("/api/resumes/intent", headers=auth(seeker["access_token"]))
    assert res.status_code == 200
    data = res.json()["data"]
    assert data["target_title"] == ""
    assert data["categories"] == []
    assert data["has_resume"] is False


def test_save_and_read_job_intent(client, monkeypatch):
    monkeypatch.setattr("app.services.resume_service.embed_one", fake_embed)
    seeker = register(client, "intent-save", "seeker")

    res = client.put(
        "/api/resumes/intent",
        headers=auth(seeker["access_token"]),
        json={
            "target_title": "后端开发工程师",
            "categories": ["技术研发", "不存在的类别"],
            "subcategories": ["后端开发"],
            "locations": ["上海", "杭州"],
            "salary_min": 25,
            "salary_max": 40,
            "job_types": ["全职"],
        },
    )
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["target_title"] == "后端开发工程师"
    # 非法类别被过滤
    assert data["categories"] == ["技术研发"]
    assert data["locations"] == ["上海", "杭州"]

    # 再读一次，确认已持久化
    again = client.get("/api/resumes/intent", headers=auth(seeker["access_token"])).json()["data"]
    assert again["target_title"] == "后端开发工程师"
    assert again["salary_min"] == 25


def test_salary_range_auto_swapped(client, monkeypatch):
    monkeypatch.setattr("app.services.resume_service.embed_one", fake_embed)
    seeker = register(client, "intent-swap", "seeker")
    res = client.put(
        "/api/resumes/intent",
        headers=auth(seeker["access_token"]),
        json={"salary_min": 40, "salary_max": 20},
    )
    data = res.json()["data"]
    assert data["salary_min"] == 20
    assert data["salary_max"] == 40


def test_intent_written_into_resume_structured(client, monkeypatch):
    monkeypatch.setattr("app.services.resume_service.embed_one", fake_embed)
    seeker = register(client, "intent-write", "seeker")
    client.put(
        "/api/resumes/intent",
        headers=auth(seeker["access_token"]),
        json={"target_title": "算法工程师", "categories": ["技术研发"]},
    )
    with SessionLocal() as db:
        resume = db.query(Resume).filter(Resume.user_id == seeker["user"]["id"]).one()
        exp = (resume.structured or {}).get("expectations") or {}
        assert exp["target_title"] == "算法工程师"
        assert exp["categories"] == ["技术研发"]
        assert resume.embedding is not None


def test_direction_score_neutral_without_intent():
    job = create_job_model()
    resume = standard_structured()
    resume["expectations"] = {"locations": ["上海"], "salary_min": 25, "salary_max": 35}
    result = score_resume_job(resume, job)
    b = result["breakdown"]
    direction = b["direction"]
    assert direction["score"] == 5.0
    assert direction["category_hit"] is None
    # 总分只含原四项，不含 direction（方向分单独用于排序）
    four = (
        b["skills_required"]["score"]
        + b["skills_preferred"]["score"]
        + b["experience"]["score"]
        + b["location"]["score"]
        + b["salary"]["score"]
    )
    assert result["total"] == round(four, 1)


def test_direction_score_hits():
    job = create_job_model()
    resume = standard_structured()
    resume["expectations"] = {
        "locations": ["上海"],
        "salary_min": 25,
        "salary_max": 35,
        "categories": ["技术研发"],
        "subcategories": ["后端开发"],
    }
    result = score_resume_job(resume, job)
    direction = result["breakdown"]["direction"]
    assert direction["score"] == 10.0
    assert direction["category_hit"] is True
    assert direction["subcategory_hit"] is True


def test_direction_score_category_miss():
    job = create_job_model()
    resume = standard_structured()
    resume["expectations"] = {
        "locations": ["上海"],
        "salary_min": 25,
        "salary_max": 35,
        "categories": ["设计"],
        "subcategories": ["视觉与平面"],
    }
    result = score_resume_job(resume, job)
    direction = result["breakdown"]["direction"]
    assert direction["score"] == 0.0
    assert direction["category_hit"] is False


# =========================== 地点定位（区级） ===========================


def make_job_in_district(district: str, location: str = "上海"):
    from app.models import Job

    return Job(
        title="Python 后端工程师",
        description="",
        required_skills=["Python", "FastAPI", "MySQL"],
        preferred_skills=["Docker", "Kubernetes"],
        experience_min=3,
        experience_max=5,
        location=location,
        district=district,
        salary_min=25,
        salary_max=35,
        status="open",
        category="技术研发",
    )


def test_district_hit_scores_full():
    resume = standard_structured()
    resume["expectations"] = {
        "locations": ["上海"],
        "districts": {"上海": ["徐汇区", "闵行区"]},
        "salary_min": 25,
        "salary_max": 35,
    }
    result = score_resume_job(resume, make_job_in_district("徐汇区"))
    loc = result["breakdown"]["location"]
    assert loc["score"] == 15.0
    assert loc["district_hit"] is True
    assert loc["job_district"] == "徐汇区"


def test_district_miss_in_same_city_scores_lower():
    resume = standard_structured()
    resume["expectations"] = {
        "locations": ["上海"],
        "districts": {"上海": ["徐汇区"]},
        "salary_min": 25,
        "salary_max": 35,
    }
    result = score_resume_job(resume, make_job_in_district("嘉定区"))
    loc = result["breakdown"]["location"]
    # 同城但区不符：11 分，低于命中区与未设区的 15
    assert loc["score"] == 11.0
    assert loc["district_hit"] is False


def test_no_district_intent_keeps_full_score():
    resume = standard_structured()
    resume["expectations"] = {
        "locations": ["上海"],
        "salary_min": 25,
        "salary_max": 35,
    }
    result = score_resume_job(resume, make_job_in_district("嘉定区"))
    loc = result["breakdown"]["location"]
    # 未设区不扣分，保持历史 15 分
    assert loc["score"] == 15.0
    assert loc["district_hit"] is None


def test_district_for_other_city_ignored():
    resume = standard_structured()
    resume["expectations"] = {
        "locations": ["上海", "北京"],
        "districts": {"北京": ["朝阳区"]},
        "salary_min": 25,
        "salary_max": 35,
    }
    # 岗位在上海，意向的区只针对北京 → 上海按未设区处理，15 分
    result = score_resume_job(resume, make_job_in_district("嘉定区"))
    assert result["breakdown"]["location"]["score"] == 15.0


def test_job_without_district_falls_back_to_city():
    resume = standard_structured()
    resume["expectations"] = {
        "locations": ["上海"],
        "districts": {"上海": ["徐汇区"]},
        "salary_min": 25,
        "salary_max": 35,
    }
    # 岗位没有区信息：不因缺数据而扣分
    result = score_resume_job(resume, make_job_in_district(""))
    assert result["breakdown"]["location"]["score"] == 11.0


def test_save_intent_with_districts(client, monkeypatch):
    monkeypatch.setattr("app.services.resume_service.embed_one", fake_embed)
    seeker = register(client, "intent-dist", "seeker")

    res = client.put(
        "/api/resumes/intent",
        headers=auth(seeker["access_token"]),
        json={
            "locations": ["上海"],
            "districts": {"上海": ["徐汇区", "徐汇区", " 闵行区 "], "北京": []},
            "salary_min": 20,
            "salary_max": 35,
        },
    )
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    # 去重 + 去空白
    assert data["districts"] == {"上海": ["徐汇区", "闵行区"]}
    # 空城市的区被丢弃
    assert "北京" not in data["districts"]


def test_districts_auto_add_city_to_locations(client, monkeypatch):
    monkeypatch.setattr("app.services.resume_service.embed_one", fake_embed)
    seeker = register(client, "intent-dist2", "seeker")

    res = client.put(
        "/api/resumes/intent",
        headers=auth(seeker["access_token"]),
        # 只传区，不传城市
        json={"districts": {"杭州": ["余杭区"]}},
    )
    data = res.json()["data"]
    assert data["locations"] == ["杭州"]
    assert data["districts"] == {"杭州": ["余杭区"]}


def create_job_model():
    from app.models import Job

    return Job(
        title="Python 后端工程师",
        description="",
        required_skills=["Python", "FastAPI", "MySQL"],
        preferred_skills=["Docker", "Kubernetes"],
        experience_min=3,
        experience_max=5,
        location="上海",
        salary_min=25,
        salary_max=35,
        status="open",
        category="技术研发",
    )


def test_diagnose_job_fit(client, monkeypatch):
    monkeypatch.setattr("app.services.resume_service.embed_one", fake_embed)
    import app.services.resume_service as rs

    monkeypatch.setattr(rs, "chat_completion", fake_diagnose())

    seeker = register(client, "intent-diag", "seeker")
    attach_resume(seeker["user"]["id"], [0.1] * 8, standard_structured())

    res = client.post(
        "/api/resumes/diagnose", headers=auth(seeker["access_token"]), json={}
    )
    assert res.status_code == 200, res.text
    data = res.json()["data"]
    assert data["positioning"]
    assert len(data["fits"]) == 2
    assert data["fits"][0]["fit_score"] >= data["fits"][1]["fit_score"]
    assert data["fits"][0]["category"] == "技术研发"


def test_diagnose_requires_resume(client):
    seeker = register(client, "intent-diag-empty", "seeker")
    res = client.post(
        "/api/resumes/diagnose", headers=auth(seeker["access_token"]), json={}
    )
    assert res.status_code == 400
    assert "简历" in res.json()["message"]


def test_diagnose_employer_forbidden(client):
    employer = register(client, "intent-emp", "employer", company="测试公司")
    res = client.post(
        "/api/resumes/diagnose", headers=auth(employer["access_token"]), json={}
    )
    assert res.status_code == 403


# =========================== 意向不被覆盖 ===========================


def test_reparse_keeps_saved_intent(client, monkeypatch):
    """重新解析简历不应丢掉已保存的求职意向。"""
    monkeypatch.setattr("app.services.resume_service.embed_one", fake_embed)
    monkeypatch.setattr(
        "app.services.resume_service.extract_structured", fake_extract_structured()
    )
    seeker = register(client, "intent-reparse", "seeker")
    client.put(
        "/api/resumes/intent",
        headers=auth(seeker["access_token"]),
        json={"locations": ["北京"], "salary_min": 30, "salary_max": None},
    )
    res = client.put(
        "/api/resumes/mine",
        headers=auth(seeker["access_token"]),
        json={"text": "# 李四\n- 目标职位: 前端开发工程师\n- 工作年限: 2\n- 期望城市: 广州\n- 期望薪资: 18-25K\n\n## 技能\nReact, TypeScript\n\n## 教育经历\n- 华南理工 | 本科 | 计算机 | 2018-2022\n\n## 工作经历\n### 某公司 | 前端 | 2022-2024\n- 做过中后台"},
    )
    assert res.status_code == 200, res.text
    intent = client.get("/api/resumes/intent", headers=auth(seeker["access_token"])).json()["data"]
    assert intent["locations"] == ["北京"]
    assert intent["salary_min"] == 30
    assert intent["salary_max"] is None


def test_restore_version_keeps_current_intent(client, monkeypatch):
    """回滚到没存意向的旧版本时，当前显式意向应保留。"""
    monkeypatch.setattr("app.services.resume_service.embed_one", fake_embed)
    monkeypatch.setattr(
        "app.services.resume_service.extract_structured", fake_extract_structured("王五", "上海")
    )
    seeker = register(client, "intent-restore", "seeker")
    raw = "# 王五\n- 目标职位: 后端\n- 工作年限: 3\n- 期望城市: 上海\n- 期望薪资: 20-30K\n\n## 技能\nPython\n\n## 教育经历\n- 某大学 | 本科 | 计算机 | 2016-2020\n\n## 工作经历\n### 某公司 | 后端 | 2020-2023\n- 写过服务" 
    client.put(
        "/api/resumes/mine",
        headers=auth(seeker["access_token"]),
        json={"text": raw},
    )
    client.put(
        "/api/resumes/intent",
        headers=auth(seeker["access_token"]),
        json={"locations": ["深圳"], "salary_min": 28, "salary_max": None},
    )
    versions = client.get("/api/resumes/versions", headers=auth(seeker["access_token"])).json()["data"]["items"]
    assert versions
    # 回滚到最早的版本（没有深圳意向）
    oldest = versions[-1]
    res = client.post(
        f"/api/resumes/versions/{oldest['id']}/restore",
        headers=auth(seeker["access_token"]),
    )
    assert res.status_code == 200, res.text
    intent = client.get("/api/resumes/intent", headers=auth(seeker["access_token"])).json()["data"]
    assert intent["locations"] == ["深圳"]
    assert intent["salary_min"] == 28


def test_apply_optimization_keeps_intent(client, monkeypatch):
    """按岗优化补充技能不应丢掉求职意向。"""
    monkeypatch.setattr("app.services.resume_service.embed_one", fake_embed)
    monkeypatch.setattr(
        "app.services.resume_service.extract_structured", fake_extract_structured("赵六", "上海")
    )
    seeker = register(client, "intent-opt", "seeker")
    client.put(
        "/api/resumes/mine",
        headers=auth(seeker["access_token"]),
        json={"text": "# 赵六\n- 目标职位: 后端\n- 工作年限: 3\n- 期望城市: 上海\n- 期望薪资: 20-30K\n\n## 技能\nPython, FastAPI\n\n## 教育经历\n- 某大学 | 本科 | 计算机 | 2016-2020\n\n## 工作经历\n### 某公司 | 后端 | 2020-2023\n- 写过服务"},
    )
    client.put(
        "/api/resumes/intent",
        headers=auth(seeker["access_token"]),
        json={"locations": ["杭州"], "salary_min": 25, "salary_max": None},
    )
    res = client.post(
        "/api/resumes/optimize/apply",
        headers=auth(seeker["access_token"]),
        json={"skills_to_add": ["Docker"], "category": "技术研发"},
    )
    assert res.status_code == 200, res.text
    intent = client.get("/api/resumes/intent", headers=auth(seeker["access_token"])).json()["data"]
    assert intent["locations"] == ["杭州"]
    assert intent["salary_min"] == 25
    skills = res.json()["data"]["structured"]["skills"]
    assert "Docker" in skills
