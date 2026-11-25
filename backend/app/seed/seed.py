"""种子脚本：解析 seed_data/*.md → 建表灌库 → 生成向量 → 预置演示账号。

运行：cd backend && .venv/Scripts/python.exe -m app.seed.seed
幂等：先 drop_all 再 create_all。
注意：会重建整库。数据库已存在时需显式加 --force，且重建前自动备份为 jobcopilot.db.bak。
"""

import asyncio
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path

from app.config import BASE_DIR, settings
from app.db import Base, SessionLocal, engine, init_db
from app.llm.client import embed_texts
from app.matching import pipeline
from app.models import (
    Application,
    ApplicationEvent,
    Company,
    InterviewInvite,
    Job,
    Notification,
    Offer,
    Resume,
    User,
)
from app.security import hash_password
from app.services.job_service import job_embedding_text
from app.services.resume_service import build_resume_embedding_text
from app.utils import utcnow

ROOT = BASE_DIR.parent
JOBS_DIR = ROOT / "seed_data" / "jobs"
RESUMES_DIR = ROOT / "seed_data" / "resumes"
DEMO_PASSWORD = "123456"

# 招聘方账号使用公司拼音（全小写，不含音调），公司名保持中文；新公司账号回退为 company-序号
COMPANY_PINYIN: dict[str, str] = {
    "星澜科技": "xinglankeji",
    "北辰云": "beichenyun",
    "澜图数据": "lantushuju",
    "云枢智能": "yunshuzhineng",
    "极衡信息": "jihengxinxi",
    "远望数科": "yuanwangshuke",
    "拾光网络": "shiguangwangluo",
    "弦歌科技": "xiangekeji",
    "白鹭软件": "bailuruanjian",
    "芯语半导体": "xinyubandaoti",
    "恒锐智造": "hengruizhizao",
    "精工机械": "jinggongjixie",
    "云驰汽车": "yunchiqiche",
    "澄明新能源": "chengmingxinnengyuan",
    "绿源环保": "lvyuanhuanbao",
    "康宁医疗": "kangningyiliao",
    "仁和生物": "renheshengwu",
    "瑞衡银行": "ruihengyinhang",
    "安泰保险": "antaibaoxian",
    "知行教育": "zhixingjiaoyu",
    "万象传媒": "wanxiangchuanmei",
    "木棉互动": "mumianhudong",
    "星轨游戏": "xingguiyouxi",
    "悦享零售": "yuexianglingshou",
    "每日鲜": "meirixian",
    "拾味餐饮": "shiweicanyin",
    "顺捷供应链": "shunjiegongyinglian",
    "远行酒店": "yuanxingjiudian",
    "城远地产": "chengyuandichan",
    "广厦建设": "guangshajianshe",
    "正衡律所": "zhenghenglvsuo",
    "明德咨询": "mingdezixun",
    "半山设计": "banshansheji",
    "沃野农业": "woyenongye",
}

STATUS_CYCLE = ["submitted", "screening", "interview", "submitted", "rejected", "screening", "offer"]


def _parse_sections(text: str) -> tuple[str, dict[str, str], dict[str, list[str]]]:
    title = ""
    meta: dict[str, str] = {}
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("## "):
            current = line[3:].strip()
            sections[current] = []
        elif line.startswith("# ") and not title:
            title = line[2:].strip()
        elif line.startswith("- ") and current is None:
            key, _, value = line[2:].partition(":")
            meta[key.strip()] = value.strip()
        elif current:
            sections[current].append(line)
    return title, meta, sections


def _range(value: str, cast=float) -> tuple:
    left, _, right = value.partition("-")
    try:
        return cast(left.strip() or 0), cast(right.strip() or left.strip() or 0)
    except ValueError:
        return cast(0), cast(0)


def parse_job(path: Path) -> dict:
    title, meta, sections = _parse_sections(path.read_text(encoding="utf-8"))
    smin, smax = _range(meta.get("薪资", "0-0"))
    emin, emax = _range(meta.get("经验", "0-10"), int)
    return {
        "title": title,
        "company": meta.get("公司", ""),
        "industry": meta.get("行业", "互联网"),
        "location": meta.get("城市", "不限"),
        "district": "" if meta.get("区县", "") in ("", "—") else meta.get("区县", ""),
        "salary_min": smin,
        "salary_max": smax,
        "experience_min": emin,
        "experience_max": emax,
        "category": meta.get("类别", "其他"),
        "job_type": meta.get("性质", "全职"),
        "status": meta.get("状态", "open"),
        "required_skills": [s.strip() for s in ",".join(sections.get("必需技能", [])).split(",") if s.strip()],
        "preferred_skills": [s.strip() for s in ",".join(sections.get("加分技能", [])).split(",") if s.strip()],
        "description": "\n".join(sections.get("岗位描述", [])),
    }


def parse_resume(path: Path) -> tuple[dict, dict]:
    name, meta, sections = _parse_sections(path.read_text(encoding="utf-8"))
    smin, smax = _range(meta.get("期望薪资", "0-0").replace("K", ""))
    skills = [s.strip() for s in ",".join(sections.get("技能", [])).split(",") if s.strip()]

    education = []
    for line in sections.get("教育经历", []):
        parts = [p.strip() for p in line.lstrip("- ").split("|")]
        if len(parts) >= 4:
            education.append(
                {"school": parts[0], "degree": parts[1], "major": parts[2], "period": parts[3]}
            )

    work: list[dict] = []
    for line in sections.get("工作经历", []):
        if line.startswith("### "):
            parts = [p.strip() for p in line[4:].split("|")]
            work.append(
                {
                    "company": parts[0] if parts else "",
                    "role": parts[1] if len(parts) > 1 else "",
                    "period": parts[2] if len(parts) > 2 else "",
                    "highlights": [],
                }
            )
        elif line.startswith("- ") and work:
            work[-1]["highlights"].append(line[2:].strip())

    structured = {
        "name": name,
        "title": meta.get("目标职位", ""),
        "skills": skills,
        "years_of_experience": float(meta.get("工作年限", 0) or 0),
        "education": education,
        "work_experience": work,
        "expectations": {
            "locations": [meta.get("期望城市", "")] if meta.get("期望城市") else [],
            "salary_min": smin or None,
            "salary_max": smax or None,
            "job_types": ["全职"],
        },
    }
    return structured, {"raw_text": path.read_text(encoding="utf-8")}


def _build_employers(db, company_industries: dict[str, str]) -> dict[str, Company]:
    """每家公司配一个招聘方账号：账号为公司拼音，公司名保持中文；星澜科技为演示账号。"""
    companies: dict[str, Company] = {}
    for index, (name, industry) in enumerate(company_industries.items()):
        is_demo = name == "星澜科技"
        pinyin = COMPANY_PINYIN.get(name, f"company-{index:02d}")
        owner = User(
            username=pinyin,
            password_hash=hash_password(DEMO_PASSWORD),
            role="employer",
            display_name="李 HR" if is_demo else f"{name} HR",
        )
        db.add(owner)
        db.flush()
        company = Company(
            owner_user_id=owner.id, name=name, industry=industry, description=""
        )
        db.add(company)
        db.flush()
        companies[name] = company
    return companies


def _seed_pipeline(
    db,
    created_apps: list[tuple[Application, int]],
    jobs_by_id: dict[int, Job],
    owner_by_company: dict[int, int],
    now: datetime | None = None,
) -> tuple[int, int]:
    """为投递预置面试邀约与 Offer，返回 (邀约数, Offer 数)。"""
    now = now or utcnow()
    invite_count = 0
    offer_count = 0

    for app, index in created_apps:
        job = jobs_by_id.get(app.job_id)
        if job is None:
            continue
        owner_id = owner_by_company.get(job.company_id)
        if owner_id is None:
            continue

        if app.status == "interview":
            status = ["pending", "confirmed", "completed"][index % 3]
            scheduled = now + timedelta(days=(index % 5) + 1, hours=10)
            if status == "completed":
                scheduled = now - timedelta(days=2, hours=1)
            invite = InterviewInvite(
                application_id=app.id,
                job_id=job.id,
                user_id=app.user_id,
                created_by_user_id=owner_id,
                round=1,
                scheduled_at=scheduled,
                duration_minutes=45,
                mode=["video", "onsite", "phone"][index % 3],
                location=["腾讯会议 123-456-789", "公司 3 层会议室", "电话面试"][index % 3],
                note="简历匹配度较高，安排一轮技术面",
                status=status,
            )
            db.add(invite)
            db.flush()
            db.add(
                Notification(
                    user_id=app.user_id,
                    type="interview_invite",
                    title=f"面试邀约：{job.title} · {job.company.name if job.company else ''}",
                    payload={
                        "application_id": app.id,
                        "job_id": job.id,
                        "title": job.title,
                        "round": invite.round,
                        "scheduled_at": invite.scheduled_at.isoformat(),
                        "mode": invite.mode,
                        "location": invite.location,
                    },
                    dedupe_key=f"invite:{invite.id}:created",
                )
            )
            invite_count += 1

        if app.status == "offer":
            outcome = ["accepted", "pending", "declined"][index % 3]
            offer = Offer(
                application_id=app.id,
                job_id=job.id,
                user_id=app.user_id,
                created_by_user_id=owner_id,
                salary_min=job.salary_min,
                salary_max=job.salary_max,
                start_date=(now + timedelta(days=30)).date().isoformat(),
                expires_at=now + timedelta(days=7),
                note="薪资与岗位信息以正式 offer 为准",
                status=outcome,
            )
            if outcome != "pending":
                offer.responded_at = now
                offer.response_note = "已接受，按期入职" if outcome == "accepted" else "已接受其他机会"
            db.add(offer)
            db.flush()
            db.add(
                Notification(
                    user_id=app.user_id,
                    type="offer",
                    title=f"收到 Offer：{job.title} · {job.company.name if job.company else ''}",
                    payload={
                        "application_id": app.id,
                        "job_id": job.id,
                        "title": job.title,
                        "salary_min": offer.salary_min,
                        "salary_max": offer.salary_max,
                        "start_date": offer.start_date,
                        "expires_at": offer.expires_at.isoformat() if offer.expires_at else None,
                    },
                    dedupe_key=f"offer:{offer.id}:pending",
                )
            )
            if outcome == "declined":
                app.status = "rejected"
                app.status_note = "候选人拒绝了 Offer"
                db.add(
                    ApplicationEvent(
                        application_id=app.id,
                        from_status="offer",
                        to_status="rejected",
                        note="候选人拒绝了 Offer",
                        actor_user_id=app.user_id,
                    )
                )
            elif outcome == "accepted":
                app.status = "onboarding"
                app.onboarding_date = offer.start_date
                app.status_note = "候选人已接受 Offer，进入待入职"
                db.add(
                    ApplicationEvent(
                        application_id=app.id,
                        from_status="offer",
                        to_status="onboarding",
                        note="候选人已接受 Offer，进入待入职",
                        actor_user_id=app.user_id,
                    )
                )
                if index % 2 == 0:
                    app.onboarding_confirmed_at = now
                if index % 4 == 0:
                    app.status = "hired"
                    app.onboarding_result = "hired"
                    app.onboarding_result_at = now
                    app.status_note = "已按期到岗"
                    db.add(
                        ApplicationEvent(
                            application_id=app.id,
                            from_status="onboarding",
                            to_status="hired",
                            note="招聘方确认已到岗",
                            actor_user_id=owner_id,
                        )
                    )
            offer_count += 1

    db.commit()
    return invite_count, offer_count


async def seed() -> None:
    Base.metadata.drop_all(bind=engine)
    init_db()
    db = SessionLocal()
    try:
        job_rows = [parse_job(p) for p in sorted(JOBS_DIR.glob("*.md"))]
        company_industries: dict[str, str] = {}
        for row in job_rows:
            company_industries.setdefault(row["company"], row.get("industry", "互联网"))
        # 演示公司排在最前，保证星澜科技的账号一定是 xinglankeji
        company_industries = {
            "星澜科技": company_industries.get("星澜科技", "互联网"),
            **{k: v for k, v in company_industries.items() if k != "星澜科技"},
        }
        companies = _build_employers(db, company_industries)

        # ---- 岗位 ----
        jobs: list[Job] = []
        for row in job_rows:
            company_name = row.pop("company")
            row.pop("industry", None)
            company = companies[company_name]
            jobs.append(Job(company_id=company.id, **row))
        db.add_all(jobs)
        db.commit()

        vectors = await embed_texts([job_embedding_text(job) for job in jobs])
        for job, vector in zip(jobs, vectors, strict=True):
            job.embedding = vector
        db.commit()
        print(f"岗位写入完成：{len(jobs)} 个")

        # ---- 简历 + 求职者 ----
        demo_created: list[tuple[User, Resume, int]] = []
        resume_paths = sorted(RESUMES_DIR.glob("*.md"))
        structured_list = []
        for index, path in enumerate(resume_paths):
            structured, extra = parse_resume(path)
            structured_list.append((structured, extra, path))

        resume_vectors = await embed_texts(
            [build_resume_embedding_text(item[0]) for item in structured_list]
        )

        for index, (structured, extra, _path) in enumerate(structured_list):
            is_demo = index == 0
            user = User(
                username="zhangsan" if is_demo else f"cand{index + 1:02d}",
                password_hash=hash_password(DEMO_PASSWORD),
                role="seeker",
                display_name=structured["name"],
            )
            db.add(user)
            db.flush()
            resume = Resume(
                user_id=user.id,
                raw_text=extra["raw_text"],
                structured=structured,
                embedding=resume_vectors[index],
                source="upload",
            )
            db.add(resume)
            db.flush()
            demo_created.append((user, resume, index))
        db.commit()
        print(f"简历写入完成：{len(demo_created)} 份（演示账号 zhangsan / 123456）")

        # ---- 预置投递（让 HR 端有候选人可看） ----
        app_count = 0
        created_apps: list[tuple[Application, int]] = []
        for user, resume, index in demo_created:
            if index == 0:
                continue  # 演示求职者 zhangsan 保持零投递，便于完整演示「找岗位 → 投递」链路
            matches = await pipeline.match_jobs_for_resume(db, resume, max_results=3)
            for rank, item in enumerate(matches):
                app = Application(
                    job_id=item["id"],
                    resume_id=resume.id,
                    user_id=user.id,
                    status=STATUS_CYCLE[(index + rank) % len(STATUS_CYCLE)],
                    match_score=item["match_score"],
                )
                db.add(app)
                created_apps.append((app, index + rank))
                app_count += 1
        db.commit()
        print(f"投递记录写入完成：{app_count} 条")

        # ---- 预置面试邀约与 Offer（让双端流程页有存量数据可看） ----
        jobs_by_id = {job.id: job for job in jobs}
        owner_by_company = {company.id: company.owner_user_id for company in companies.values()}
        invite_count, offer_count = _seed_pipeline(
            db, created_apps, jobs_by_id, owner_by_company
        )
        print(f"面试邀约写入完成：{invite_count} 条；Offer 写入完成：{offer_count} 条")

        demo_company = companies.get("星澜科技")
        demo_username = (
            COMPANY_PINYIN.get(demo_company.name, "company-00") if demo_company else ""
        )
        hr_count = max(len(companies) - 1, 0)
        print("\n演示账号（密码统一 123456）：")
        print("  求职者 zhangsan")
        print(
            f"  招聘方 {demo_username}"
            + (f"（公司：{demo_company.name}）" if demo_company else "")
        )
        print(f"  其余 {hr_count} 个招聘方账号为对应公司的拼音（见 COMPANY_PINYIN）")
        print(f"  其余求职者 cand02 ~ cand{len(demo_created):02d}")
    finally:
        db.close()


def _sqlite_path() -> Path | None:
    """当前配置指向的 SQLite 文件路径；非 SQLite 时返回 None。"""
    prefix = "sqlite:///"
    if not settings.database_url.startswith(prefix):
        return None
    return Path(settings.database_url[len(prefix) :])


def _guard_existing_db() -> None:
    """已有的数据库不允许静默重建：需 --force，且重建前自动备份。"""
    path = _sqlite_path()
    if path is None or not path.exists() or path.stat().st_size == 0:
        return

    if "--force" not in sys.argv:
        print(
            f"[x] 数据库 {path.name} 已有数据。种子脚本会 drop 全部表，"
            "用户上传的简历、投递等数据都会被清空。\n"
            "    确认要重建请加 --force；只想重启服务请勿执行本脚本。\n"
            "    例：.venv\\Scripts\\python -m app.seed.seed --force"
        )
        sys.exit(1)

    backup = path.with_name(path.name + ".bak")
    shutil.copy2(path, backup)
    print(f"[!] 已备份原数据库到 {backup.name}，随后将重建整库。")


if __name__ == "__main__":
    _guard_existing_db()
    asyncio.run(seed())
