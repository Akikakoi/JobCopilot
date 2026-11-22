from datetime import datetime

from app.db import SessionLocal
from app.models import (
    Application,
    ApplicationEvent,
    Company,
    Job,
    Notification,
    Offer,
    Resume,
    User,
)
from app.seed.seed import _seed_pipeline


def test_seed_pipeline_creates_invites_offers_and_notifications(client):
    with SessionLocal() as db:
        owner = User(
            username="seed-hr",
            password_hash="x",
            role="employer",
            display_name="HR",
        )
        seeker = User(
            username="seed-seeker",
            password_hash="x",
            role="seeker",
            display_name="候选人",
        )
        db.add_all([owner, seeker])
        db.flush()

        company = Company(
            owner_user_id=owner.id, name="星澜科技", industry="互联网", description=""
        )
        db.add(company)
        db.flush()

        jobs = [
            Job(
                company_id=company.id,
                title=f"Python 后端 {index}",
                salary_min=25,
                salary_max=35,
                required_skills=["Python"],
            )
            for index in range(4)
        ]
        resume = Resume(
            user_id=seeker.id, raw_text="", structured={"name": "候选人"}, source="paste"
        )
        db.add_all([*jobs, resume])
        db.flush()

        applications = [
            Application(
                job_id=job.id,
                resume_id=resume.id,
                user_id=seeker.id,
                status="interview" if index == 0 else "offer",
            )
            for index, job in enumerate(jobs)
        ]
        db.add_all(applications)
        db.commit()

        invited, offered = _seed_pipeline(
            db,
            [
                (applications[0], 0),
                (applications[1], 0),
                (applications[2], 1),
                (applications[3], 2),
            ],
            {job.id: job for job in jobs},
            {company.id: owner.id},
            now=datetime(2030, 1, 1, 9, 0),
        )

        assert invited == 1
        assert offered == 3

        offer_rows = {row.application_id: row for row in db.query(Offer).all()}
        assert offer_rows[applications[1].id].status == "accepted"
        assert offer_rows[applications[2].id].status == "pending"
        assert offer_rows[applications[3].id].status == "declined"

        # 接受 Offer 会进入入职阶段（部分演示数据直接标记已入职）
        db.refresh(applications[1])
        assert applications[1].status == "hired"
        assert applications[1].onboarding_result == "hired"
        assert applications[1].onboarding_date == "2030-01-31"

        # 拒绝 Offer 会同步把投递置为 rejected 并记录事件
        db.refresh(applications[3])
        assert applications[3].status == "rejected"
        events = db.query(ApplicationEvent).all()
        assert len(events) == 3
        assert {event.to_status for event in events} == {"onboarding", "hired", "rejected"}

        notes = db.query(Notification).all()
        assert len(notes) == 4
        assert {note.type for note in notes} == {"interview_invite", "offer"}
