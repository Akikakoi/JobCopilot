"""站内消息：围绕投递的一对一会话（候选人 ↔ 岗位所属招聘方）。"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Application, Company, Conversation, Job, Message, Resume, User
from app.utils import utcnow

MAX_MESSAGE_LENGTH = 2000
PREVIEW_LENGTH = 80


class MessageError(ValueError):
    pass


def ensure_conversation(db: Session, application: Application) -> Conversation:
    conversation = db.scalar(
        select(Conversation).where(Conversation.application_id == application.id)
    )
    if conversation is not None:
        return conversation

    job = application.job if hasattr(application, "job") else db.get(Job, application.job_id)
    company = job.company if job is not None else None
    if company is None:
        raise MessageError("岗位缺少公司信息，无法创建会话")

    conversation = Conversation(
        application_id=application.id,
        seeker_user_id=application.user_id,
        employer_user_id=company.owner_user_id,
    )
    db.add(conversation)
    db.flush()
    return conversation


def _applications_for_user(db: Session, user: User) -> list[Application]:
    if user.role == "seeker":
        return list(
            db.scalars(
                select(Application)
                .where(Application.user_id == user.id)
                .order_by(Application.id.desc())
            )
        )
    return list(
        db.scalars(
            select(Application)
            .join(Job, Application.job_id == Job.id)
            .join(Company, Job.company_id == Company.id)
            .where(Company.owner_user_id == user.id)
            .order_by(Application.id.desc())
        )
    )


def _message_preview(content: str) -> str:
    text = (content or "").replace("\n", " ").strip()
    return text[:PREVIEW_LENGTH] + ("…" if len(text) > PREVIEW_LENGTH else "")


def list_conversations(db: Session, user: User) -> dict:
    applications = _applications_for_user(db, user)
    if not applications:
        return {"items": [], "unread": 0}

    app_ids = [item.id for item in applications]
    conversations = list(
        db.scalars(select(Conversation).where(Conversation.application_id.in_(app_ids)))
    )
    existing = {item.application_id for item in conversations}
    created = False
    for application in applications:
        if application.id in existing:
            continue
        try:
            conversations.append(ensure_conversation(db, application))
            created = True
        except MessageError:
            continue
    if created:
        db.commit()

    apps_by_id = {item.id: item for item in applications}
    job_ids = {item.job_id for item in applications}
    jobs = {
        job.id: job
        for job in db.scalars(select(Job).where(Job.id.in_(job_ids)))
    }
    company_ids = {job.company_id for job in jobs.values()}
    companies = {
        company.id: company
        for company in db.scalars(select(Company).where(Company.id.in_(company_ids)))
    }
    resume_ids = {item.resume_id for item in applications}
    resumes = {
        resume.id: resume
        for resume in db.scalars(select(Resume).where(Resume.id.in_(resume_ids)))
    }

    conv_ids = [item.id for item in conversations]
    messages = (
        list(
            db.scalars(
                select(Message)
                .where(Message.conversation_id.in_(conv_ids))
                .order_by(Message.id.asc())
            )
        )
        if conv_ids
        else []
    )
    last_by_conv: dict[int, Message] = {}
    unread_by_conv: dict[int, int] = {}
    for message in messages:
        last_by_conv[message.conversation_id] = message
        if message.sender_user_id != user.id and message.read_at is None:
            unread_by_conv[message.conversation_id] = (
                unread_by_conv.get(message.conversation_id, 0) + 1
            )

    items = []
    for conversation in conversations:
        application = apps_by_id.get(conversation.application_id)
        if application is None:
            continue
        job = jobs.get(application.job_id)
        company = companies.get(job.company_id) if job else None
        resume = resumes.get(application.resume_id)
        candidate_name = (resume.structured or {}).get("name") if resume else ""
        if not candidate_name:
            candidate_name = "候选人"
        company_name = company.name if company else ""
        last = last_by_conv.get(conversation.id)
        items.append(
            {
                "id": conversation.id,
                "application_id": application.id,
                "job_id": application.job_id,
                "job_title": job.title if job else "",
                "company_name": company_name,
                "candidate_name": candidate_name,
                "other_name": company_name if user.role == "seeker" else candidate_name,
                "unread": unread_by_conv.get(conversation.id, 0),
                "last_message": {
                    "content": _message_preview(last.content),
                    "created_at": last.created_at,
                    "sender_user_id": last.sender_user_id,
                    "mine": last.sender_user_id == user.id,
                }
                if last
                else None,
                "_sort": last.id if last else 0,
            }
        )

    items.sort(key=lambda item: (item["_sort"], item["id"]), reverse=True)
    unread_total = sum(item["unread"] for item in items)
    for item in items:
        item.pop("_sort", None)
    return {"items": items, "unread": unread_total}


def _get_conversation(db: Session, user: User, conversation_id: int) -> Conversation:
    conversation = db.get(Conversation, conversation_id)
    if conversation is None or user.id not in (
        conversation.seeker_user_id,
        conversation.employer_user_id,
    ):
        raise PermissionError("会话不存在或无权访问")
    return conversation


def message_to_dict(message: Message, user: User) -> dict:
    return {
        "id": message.id,
        "conversation_id": message.conversation_id,
        "content": message.content,
        "sender_user_id": message.sender_user_id,
        "mine": message.sender_user_id == user.id,
        "created_at": message.created_at,
    }


def list_messages(
    db: Session,
    user: User,
    conversation_id: int,
    after_id: int | None = None,
    limit: int = 100,
) -> list[dict]:
    _get_conversation(db, user, conversation_id)
    stmt = select(Message).where(Message.conversation_id == conversation_id)
    if after_id:
        stmt = stmt.where(Message.id > after_id)
    rows = list(db.scalars(stmt.order_by(Message.id.asc()).limit(min(limit, 200))))
    return [message_to_dict(item, user) for item in rows]


def send_message(
    db: Session, user: User, conversation_id: int, content: str
) -> dict:
    _get_conversation(db, user, conversation_id)
    text = (content or "").strip()
    if not text:
        raise MessageError("消息内容不能为空")
    if len(text) > MAX_MESSAGE_LENGTH:
        raise MessageError(f"消息不能超过 {MAX_MESSAGE_LENGTH} 字")

    message = Message(
        conversation_id=conversation_id, sender_user_id=user.id, content=text
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message_to_dict(message, user)


def mark_read(db: Session, user: User, conversation_id: int) -> int:
    _get_conversation(db, user, conversation_id)
    rows = list(
        db.scalars(
            select(Message).where(
                Message.conversation_id == conversation_id,
                Message.sender_user_id != user.id,
                Message.read_at.is_(None),
            )
        )
    )
    now = utcnow()
    for row in rows:
        row.read_at = now
    db.commit()
    return len(rows)


def unread_total(db: Session, user: User) -> int:
    stmt = (
        select(func.count(Message.id))
        .join(Conversation, Message.conversation_id == Conversation.id)
        .where(
            Message.sender_user_id != user.id,
            Message.read_at.is_(None),
        )
    )
    if user.role == "seeker":
        stmt = stmt.where(Conversation.seeker_user_id == user.id)
    else:
        stmt = stmt.where(Conversation.employer_user_id == user.id)
    return int(db.scalar(stmt) or 0)
