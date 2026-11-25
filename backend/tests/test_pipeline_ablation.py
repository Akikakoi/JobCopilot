"""pipeline 消融修复的回归测试。

覆盖四项修复：
1. 向量召回带意向城市配额
2. 薪资下限硬过滤
3. 方向作为同分破缺键
4. 相似度作为次级排序键

直接种库（User/Resume/Job），用 create_access_token 打 /api/match/jobs-for-me。
"""

from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.models import Company, Job, Resume, User
from app.security import create_access_token, hash_password
from tests.conftest import Base, engine, standard_structured


def unit_vec(dim: int, idx: int) -> list[float]:
    v = [0.0] * dim
    v[idx] = 1.0
    return v


class Seed:
    def __init__(self, client: TestClient):
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        self.client = client
        self.db = SessionLocal()
        self.user = User(
            username="ab-seeker",
            password_hash=hash_password("123456"),
            role="seeker",
            display_name="消融测试",
        )
        self.db.add(self.user)
        self.db.flush()
        self.token = create_access_token(self.user.id, "seeker")
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def company(self, name: str = "测试公司") -> Company:
        c = Company(owner_user_id=self.user.id, name=name, industry="互联网")
        self.db.add(c)
        self.db.flush()
        return c

    def job(self, company: Company, **overrides) -> Job:
        defaults = dict(
            title="Python 后端工程师",
            description="负责后端服务开发",
            required_skills=["Python", "FastAPI", "MySQL"],
            preferred_skills=["Docker"],
            experience_min=3,
            experience_max=5,
            location="上海",
            salary_min=25,
            salary_max=35,
            status="open",
        )
        defaults.update(overrides)
        job = Job(company_id=company.id, **defaults)
        self.db.add(job)
        self.db.flush()
        return job

    def resume(self, embedding: list[float], structured: dict) -> Resume:
        resume = Resume(
            user_id=self.user.id,
            raw_text="简历",
            structured=structured,
            embedding=embedding,
            source="paste",
        )
        self.db.add(resume)
        self.db.flush()
        return resume

    def commit(self):
        self.db.commit()

    def match(self, top_n: int = 10) -> list[dict]:
        resp = self.client.get(
            f"/api/match/jobs-for-me?top_n={top_n}&limit={top_n}", headers=self.headers
        )
        assert resp.status_code == 200, resp.text
        return resp.json()["data"]["items"]

    def teardown(self):
        self.db.close()
        Base.metadata.drop_all(bind=engine)


def test_city_quota_pulls_intent_city_into_recall(client):
    """意向北京的用户，北京岗位即使相似度略低也应进召回窗口。"""
    s = Seed(client)
    try:
        company = s.company()
        sh = s.job(company, location="上海")
        sh.embedding = unit_vec(8, 0)
        bj = s.job(company, location="北京", title="北京后端")
        bj.embedding = [0.6, 0.8, 0, 0, 0, 0, 0, 0]
        for i in range(8):
            j = s.job(company, location="上海", title=f"上海后端 {i}")
            j.embedding = unit_vec(8, 1)  # 与 resume 正交，相似度 0
        structured = standard_structured()
        structured["expectations"]["locations"] = ["北京"]
        s.resume(unit_vec(8, 0), structured)
        s.commit()
        bj_id = bj.id
        sh_id = sh.id

        items = s.match(top_n=4)
        ids = [item["id"] for item in items]
        assert bj_id in ids, f"北京岗位未进召回窗口: {ids} (岗位 {bj_id}, 上海 {sh_id})"
    finally:
        s.teardown()


def test_salary_floor_filters_unreachable_jobs(client):
    """期望 30K 以上，岗位上限 22K 的不应出现在结果里。"""
    s = Seed(client)
    try:
        company = s.company()
        low = s.job(company, salary_min=18, salary_max=22, title="低薪岗位")
        low.embedding = unit_vec(8, 0)
        ok = s.job(company, salary_min=30, salary_max=38, title="达标岗位")
        ok.embedding = unit_vec(8, 0)
        structured = standard_structured()
        structured["expectations"]["salary_min"] = 30
        structured["expectations"]["salary_max"] = None
        s.resume(unit_vec(8, 0), structured)
        s.commit()
        low_id, ok_id = low.id, ok.id

        items = s.match(top_n=10)
        ids = [item["id"] for item in items]
        assert low_id not in ids, f"低于期望下限的岗位未被过滤: {ids}"
        assert ok_id in ids, f"达标岗位未出现在结果: {ids}"
    finally:
        s.teardown()


def test_direction_breaks_ties(client):
    """两个岗位 rank_score 同分时，设了方向且命中的排前面。"""
    s = Seed(client)
    try:
        company = s.company()
        # 两个岗位都用同一套技能，保证 match_score 相同
        skills = ["Python", "FastAPI", "MySQL"]
        hit = s.job(company, title="游戏服务端工程师", required_skills=skills, description="游戏服务端", category="技术研发")
        hit.embedding = unit_vec(8, 0)
        other = s.job(company, title="后端开发工程师", required_skills=skills)
        other.embedding = unit_vec(8, 0)
        structured = standard_structured()
        structured["expectations"]["categories"] = ["技术研发"]
        structured["expectations"]["subcategories"] = ["游戏开发"]
        s.resume(unit_vec(8, 0), structured)
        s.commit()
        hit_id, other_id = hit.id, other.id

        items = s.match(top_n=10)
        assert items[0]["id"] == hit_id, [
            (i["id"], i["match_score"], i["rank_score"]) for i in items
        ]
        assert items[1]["id"] == other_id
        # match_score 相同，方向分只在排序键里
        assert items[0]["match_score"] == items[1]["match_score"]
    finally:
        s.teardown()


def test_similarity_breaks_score_ties(client):
    """match_score 同分时相似度高的排前面（无方向设置）。"""
    s = Seed(client)
    try:
        company = s.company()
        high = s.job(company, title="岗位高相似")
        high.embedding = unit_vec(8, 0)
        low = s.job(company, title="岗位低相似")
        low.embedding = [0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5]
        structured = standard_structured()
        structured["expectations"]["locations"] = []  # 不设城市，避免地点分差异
        s.resume(unit_vec(8, 0), structured)
        s.commit()
        high_id, low_id = high.id, low.id

        items = s.match(top_n=10)
        by_id = {item["id"]: item for item in items}
        assert high_id in by_id and low_id in by_id
        assert by_id[high_id]["similarity"] > by_id[low_id]["similarity"]
        order = [item["id"] for item in items]
        assert order.index(high_id) < order.index(low_id), order
    finally:
        s.teardown()
