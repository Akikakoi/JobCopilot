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


def test_cosine_similarity_bounds():
    assert cosine_similarity([1, 0], [1, 0]) == 1.0
    assert cosine_similarity([1, 0], [0, 1]) == 0.0
    assert cosine_similarity([0, 0], [1, 1]) == 0.0
