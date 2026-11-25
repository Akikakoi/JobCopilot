"""规则精排：总分 100 = 技能 50 + 年限 20 + 地点 15 + 薪资 15；定位方向单独计分参与排序。"""

import re

from app.job_taxonomy import derive_subcategory
from app.models import Job

CITY_NOISE = ("市", " ", "　")
NEUTRAL_LOCATION_SCORE = 8.0
NEUTRAL_SALARY_SCORE = 8.0
NEUTRAL_DIRECTION_SCORE = 5.0
_CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")


def _norm(text: str | None) -> str:
    value = (text or "").strip().lower()
    for noise in CITY_NOISE:
        value = value.replace(noise, "")
    return value


def _skill_norm(text: str | None) -> str:
    """技能名保留空格（如 Spring Boot），仅压缩空白并转小写。"""
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _word_hit(target: str, item: str) -> bool:
    """英文技能按词边界匹配：Java 不命中 JavaScript，Go 不命中 Django。"""
    pattern = re.escape(target)
    if target[0].isalnum():
        pattern = r"(?<![a-z0-9])" + pattern
    if target[-1].isalnum():
        pattern += r"(?![a-z])"
    return re.search(pattern, item) is not None


def _skill_hit(skill: str, pool: list[str]) -> bool:
    target = _skill_norm(skill)
    if not target:
        return False
    cjk = bool(_CJK_RE.search(target))
    for raw in pool:
        item = _skill_norm(raw)
        if not item:
            continue
        if target == item:
            return True
        if cjk and (target in item or item in target):
            return True
        if not cjk and _word_hit(target, item):
            return True
    return False


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


def _location_score(resume_locations: list[str], job: Job, expect: dict | None = None) -> float:
    """地点评分（满分 15）：城市粗匹配 + 区级精匹配。

    区级只在城市已命中的前提下才影响得分，且**不设区不扣分**：
    - 城市命中 且 区命中 → 15
    - 城市命中、未设区 → 15（与历史一致，不惩罚未填）
    - 城市命中、设了区但区不符 → 11（同城但通勤可能不便）
    - 城市部分命中 → 10
    - 未设城市 → 中性 8
    - 其他 → 0
    """
    locs = [l for l in (resume_locations or []) if l.strip()]
    job_loc = _norm(job.location)
    if not locs:
        return NEUTRAL_LOCATION_SCORE

    districts_map = (expect or {}).get("districts") or {}
    intent_districts = [d for d in (districts_map.get(job.location) or []) if d.strip()]
    job_district = (job.district or "").strip()

    def _city_exact() -> bool:
        return any(_norm(l) == job_loc for l in locs)

    def _city_partial() -> bool:
        return any(
            _norm(l) and (_norm(l) in job_loc or job_loc in _norm(l))
            for l in locs
            if _norm(job.location) not in ("不限", "远程")
        )

    if _city_exact():
        if not intent_districts:
            return 15.0
        if job_district and job_district in intent_districts:
            return 15.0
        return 11.0
    if _city_partial():
        return 10.0
    if job_loc in ("不限", "远程", "全国") or any(_norm(l) in ("不限", "远程", "全国") for l in locs):
        return NEUTRAL_LOCATION_SCORE
    return 0.0


def _direction_score(expect: dict, job: Job) -> tuple[float, dict]:
    """岗位定位（意向方向）与岗位类别的匹配。

    总分 10：类别命中给基础分，二级方向命中再加分；
    未设置意向时给中性分，不让「没填定位」变成扣分。
    """
    categories = [c for c in (expect.get("categories") or []) if c.strip()]
    subcategories = [s for s in (expect.get("subcategories") or []) if s.strip()]
    job_category = job.category or "其他"
    job_sub = derive_subcategory(job_category, job.title)
    if not categories and not subcategories:
        return NEUTRAL_DIRECTION_SCORE, {
            "score": NEUTRAL_DIRECTION_SCORE,
            "max": 10,
            "intent_categories": [],
            "intent_subcategories": [],
            "job_category": job_category,
            "job_subcategory": job_sub,
            "category_hit": None,
            "subcategory_hit": None,
        }

    category_hit = job_category in categories if categories else None
    subcategory_hit = job_sub in subcategories if subcategories else None

    if category_hit is False:
        score = 0.0
    elif subcategory_hit is True:
        score = 10.0
    elif category_hit is True:
        score = 7.0
    else:
        # 只设了方向但岗位类别不限，或只设了类别且岗位类别未知
        score = 5.0 if (subcategories and category_hit is None) else NEUTRAL_DIRECTION_SCORE
    return score, {
        "score": round(score, 1),
        "max": 10,
        "intent_categories": categories,
        "intent_subcategories": subcategories,
        "job_category": job_category,
        "job_subcategory": job_sub,
        "category_hit": category_hit,
        "subcategory_hit": subcategory_hit,
    }


def _salary_score(expect: dict, job: Job) -> float:
    rmin = expect.get("salary_min")
    rmax = expect.get("salary_max")
    if rmin is None and rmax is None:
        return NEUTRAL_SALARY_SCORE
    jmin, jmax = float(job.salary_min or 0), float(job.salary_max or 0)
    if not jmax:
        return NEUTRAL_SALARY_SCORE

    if rmax is None:
        # 期望「XK 以上」（只设下限）：按岗位区间内 ≥ 下限的部分占比给分。
        # 岗位区间整体不低于下限 → 满分；上限能触到但大部分偏低 → 部分分；
        # 上限都够不到下限 → 0。固定薪资岗位单独处理。
        floor = float(rmin or 0)
        if jmax == jmin:
            return 15.0 if jmin >= floor else 0.0
        covered = max(0.0, jmax - max(jmin, floor))
        return round(15.0 * covered / (jmax - jmin), 2)

    rmin = float(rmin or 0)
    rmax = float(rmax)
    if jmax == jmin:
        # 岗位固定薪资：落在期望区间内即满分
        ratio = 1.0 if rmin <= jmin <= rmax else 0.0
    elif rmax == rmin:
        # 期望单点（上下限相同）：岗位区间能给出该值即满分
        ratio = 1.0 if jmin <= rmin <= jmax else 0.0
    else:
        overlap = max(0.0, min(jmax, rmax) - max(jmin, rmin))
        if overlap <= 0:
            ratio = 0.0
        else:
            # 分母取较窄区间宽度：岗位完全覆盖期望（含岗位给得更多）、
            # 或岗位完全落在期望内，均视为满足 → 满分；
            # 仅部分交叠时按较窄一方的未覆盖比例扣分。
            width = min(rmax - rmin, jmax - jmin)
            ratio = 1.0 if width <= 0 else min(overlap / width, 1.0)
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
    expectations = structured.get("expectations") or {}
    location_score = _location_score(
        expectations.get("locations") or [], job, expect=expectations
    )
    salary_score = _salary_score(expectations, job)
    direction_score, direction_detail = _direction_score(expectations, job)

    # 总分仍为原四项之和（满分 100），保证与历史分数、既有测试一致；
    # 定位方向分单独展示，并在 pipeline 里作为同分优先级参与排序。
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
                "resume_locations": expectations.get("locations") or [],
                "job_location": job.location,
                "intent_districts": (expectations.get("districts") or {}).get(job.location) or [],
                "job_district": job.district or "",
                "district_hit": (
                    (job.district or "").strip()
                    in ((expectations.get("districts") or {}).get(job.location) or [])
                    if job.district
                    and (expectations.get("districts") or {}).get(job.location)
                    else None
                ),
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
            "direction": direction_detail,
        },
    }
