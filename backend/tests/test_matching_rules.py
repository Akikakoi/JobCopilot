from app.matching.pipeline import cosine_similarity
from app.matching.rules import score_resume_job
from app.models import Job


def make_job(**overrides) -> Job:
    defaults = dict(
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
    )
    defaults.update(overrides)
    return Job(**defaults)


def make_resume(**overrides) -> dict:
    data = {
        "title": "后端开发工程师",
        "skills": ["Python", "FastAPI", "MySQL", "Redis", "Docker"],
        "years_of_experience": 3,
        "expectations": {
            "locations": ["上海"],
            "salary_min": 25,
            "salary_max": 35,
            "job_types": ["全职"],
        },
    }
    data.update(overrides)
    return data


def test_perfect_match_scores_high():
    result = score_resume_job(make_resume(), make_job())
    assert result["total"] >= 90
    assert result["breakdown"]["skills_required"]["score"] == 40
    assert result["breakdown"]["experience"]["score"] == 20
    assert result["breakdown"]["location"]["score"] == 15
    assert result["breakdown"]["salary"]["score"] == 15


def test_missing_required_skills_lowers_score():
    resume = make_resume(skills=["Python"])
    result = score_resume_job(resume, make_job())
    assert result["breakdown"]["skills_required"]["score"] < 20
    assert "FastAPI" in result["breakdown"]["skills_required"]["missing"]


def test_experience_gap_penalty():
    one_year_short = score_resume_job(make_resume(years_of_experience=2), make_job())
    two_years_short = score_resume_job(make_resume(years_of_experience=1), make_job())
    assert one_year_short["breakdown"]["experience"]["score"] == 10
    assert two_years_short["breakdown"]["experience"]["score"] == 0


def test_location_and_salary_mismatch():
    resume = make_resume(
        expectations={
            "locations": ["成都"],
            "salary_min": 45,
            "salary_max": 60,
            "job_types": [],
        }
    )
    result = score_resume_job(resume, make_job())
    assert result["breakdown"]["location"]["score"] == 0
    assert result["breakdown"]["salary"]["score"] == 0


def test_salary_full_score_when_job_covers_expectation():
    """岗位区间完全覆盖期望（含岗位给得更多）→ 满分，而非按岗位宽度打折。"""
    resume = make_resume(
        expectations={
            "locations": ["上海"],
            "salary_min": 22,
            "salary_max": 34,
            "job_types": ["全职"],
        }
    )
    result = score_resume_job(resume, make_job(salary_min=22, salary_max=38))
    assert result["breakdown"]["salary"]["score"] == 15


def test_salary_point_expectation_covered_by_job():
    """期望「XK 以上」（只设下限）：按岗位区间内达标部分占比给分。
    30K 以上 对 22-38K：只有 30-38 达标 → 半分。"""
    resume = make_resume(
        expectations={
            "locations": ["上海"],
            "salary_min": 30,
            "salary_max": None,
            "job_types": ["全职"],
        }
    )
    result = score_resume_job(resume, make_job(salary_min=22, salary_max=38))
    assert result["breakdown"]["salary"]["score"] == 7.5


def test_salary_floor_expectation_various_jobs():
    """下限型期望的边界 case：
    - 岗位区间全部 ≥ 下限 → 满分（offer 必然达标）
    - 岗位上限够不到下限 → 0 分
    - 固定薪资 ≥ 下限 → 满分（修复旧 bug：旧算法会误判为 0）
    """
    resume = make_resume(
        expectations={
            "locations": ["上海"],
            "salary_min": 30,
            "salary_max": None,
            "job_types": ["全职"],
        }
    )
    full = score_resume_job(resume, make_job(salary_min=30, salary_max=40))
    assert full["breakdown"]["salary"]["score"] == 15

    zero = score_resume_job(resume, make_job(salary_min=22, salary_max=28))
    assert zero["breakdown"]["salary"]["score"] == 0

    fixed = score_resume_job(resume, make_job(salary_min=35, salary_max=35))
    assert fixed["breakdown"]["salary"]["score"] == 15


def test_salary_partial_overlap_scores_by_narrower_range():
    """仅部分交叠时按较窄一方的覆盖比例给分。"""
    resume = make_resume(
        expectations={
            "locations": ["上海"],
            "salary_min": 20,
            "salary_max": 24,
            "job_types": ["全职"],
        }
    )
    result = score_resume_job(resume, make_job(salary_min=22, salary_max=38))
    assert result["breakdown"]["salary"]["score"] == 7.5


def _required_breakdown(required: list[str], resume_skills: list[str]) -> dict:
    job = make_job(required_skills=required, preferred_skills=[])
    return score_resume_job(make_resume(skills=resume_skills), job)["breakdown"][
        "skills_required"
    ]


def test_english_skills_match_on_word_boundaries():
    assert _required_breakdown(["Java"], ["JavaScript"])["missing"] == ["Java"]
    assert _required_breakdown(["Go"], ["Django"])["missing"] == ["Go"]
    assert _required_breakdown(["SQL"], ["MySQL"])["missing"] == ["SQL"]

    assert _required_breakdown(["Java"], ["Java 8"])["matched"] == ["Java"]
    assert _required_breakdown(["React"], ["React Native"])["matched"] == ["React"]
    assert _required_breakdown(["Spring"], ["Spring Boot"])["matched"] == ["Spring"]
    assert _required_breakdown(["Node"], ["Node.js"])["matched"] == ["Node"]
    assert _required_breakdown(["C++"], ["C++"])["matched"] == ["C++"]
    assert _required_breakdown([".NET"], ["ASP.NET"])["matched"] == [".NET"]


def test_cjk_skills_keep_substring_matching():
    assert _required_breakdown(["机器学习"], ["机器学习平台开发"])["matched"] == ["机器学习"]
    assert _required_breakdown(["数据分析"], ["数据"])["matched"] == ["数据分析"]


def test_cosine_similarity_bounds():
    assert cosine_similarity([1, 0], [1, 0]) == 1.0
    assert cosine_similarity([1, 0], [0, 1]) == 0.0
    assert cosine_similarity([0, 0], [1, 1]) == 0.0
