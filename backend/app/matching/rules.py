"""规则精排：总分 100 = 技能 50 + 年限 20 + 地点 15 + 薪资 15。"""

from app.models import Job

CITY_NOISE = ("市", " ", "　")
NEUTRAL_LOCATION_SCORE = 8.0
NEUTRAL_SALARY_SCORE = 8.0


def _norm(text: str | None) -> str:
    value = (text or "").strip().lower()
    for noise in CITY_NOISE:
        value = value.replace(noise, "")
    return value


def _skill_hit(skill: str, pool: list[str]) -> bool:
    target = _norm(skill)
    if not target:
        return False
    return any(target == _norm(item) or target in _norm(item) or _norm(item) in target for item in pool)


def _match_skills(required: list[str], resume_skills: list[str]) -> list[str]:
    return [s for s in required if _skill_hit(s, resume_skills)]


def _years_score(resume_years: float, job: Job) -> float:
    need = job.experience_min or 0
    if resume_years >= need:
        return 20.0
    gap = need - resume_years
    if gap <= 1:
        return 10.0
    return 0.0


def _location_score(resume_locations: list[str], job: Job) -> float:
    locs = [l for l in (resume_locations or []) if l.strip()]
    job_loc = _norm(job.location)
    if not locs:
        return NEUTRAL_LOCATION_SCORE
    if any(_norm(l) == job_loc for l in locs):
        return 15.0
    if any(
        _norm(l) and (_norm(l) in job_loc or job_loc in _norm(l))
        for l in locs
        if _norm(job.location) not in ("不限", "远程")
    ):
        return 10.0
    if job_loc in ("不限", "远程", "全国") or any(_norm(l) in ("不限", "远程", "全国") for l in locs):
        return NEUTRAL_LOCATION_SCORE
    return 0.0


def _salary_score(expect: dict, job: Job) -> float:
    rmin = expect.get("salary_min")
    rmax = expect.get("salary_max")
    if rmin is None and rmax is None:
        return NEUTRAL_SALARY_SCORE
    rmin = float(rmin or 0)
    rmax = float(rmax or rmin)
    jmin, jmax = float(job.salary_min or 0), float(job.salary_max or 0)
    if not jmax:
        return NEUTRAL_SALARY_SCORE

    if jmax == jmin:
        ratio = 1.0 if rmin <= jmin <= rmax else 0.0
    else:
        overlap = max(0.0, min(jmax, rmax) - max(jmin, rmin))
        ratio = overlap / (jmax - jmin)
    return round(15.0 * min(ratio, 1.0), 2)


def score_resume_job(structured: dict, job: Job) -> dict:
    """返回总分明细，供前端展示与 LLM 解读引用。"""
    resume_skills: list[str] = structured.get("skills") or []
    required = job.required_skills or []
    preferred = job.preferred_skills or []

    matched_required = _match_skills(required, resume_skills)
    matched_preferred = _match_skills(preferred, resume_skills)

    skills_required_score = 40.0 * len(matched_required) / len(required) if required else 40.0
    skills_preferred_score = 10.0 * len(matched_preferred) / len(preferred) if preferred else 5.0
    years = float(structured.get("years_of_experience") or 0)
    years_score = _years_score(years, job)
    location_score = _location_score(
        (structured.get("expectations") or {}).get("locations") or [], job
    )
    salary_score = _salary_score(structured.get("expectations") or {}, job)

    total = round(
        skills_required_score + skills_preferred_score + years_score + location_score + salary_score, 1
    )
    return {
        "total": min(total, 100.0),
        "breakdown": {
            "skills_required": {
                "score": round(skills_required_score, 1),
                "max": 40,
                "matched": matched_required,
                "missing": [s for s in required if s not in matched_required],
            },
            "skills_preferred": {
                "score": round(skills_preferred_score, 1),
                "max": 10,
                "matched": matched_preferred,
            },
            "experience": {
                "score": round(years_score, 1),
                "max": 20,
                "resume_years": years,
                "required_years": job.experience_min,
            },
            "location": {
                "score": round(location_score, 1),
                "max": 15,
                "resume_locations": (structured.get("expectations") or {}).get("locations") or [],
                "job_location": job.location,
            },
            "salary": {
                "score": round(salary_score, 1),
                "max": 15,
                "resume_range": [
                    (structured.get("expectations") or {}).get("salary_min"),
                    (structured.get("expectations") or {}).get("salary_max"),
                ],
                "job_range": [job.salary_min, job.salary_max],
            },
        },
    }
