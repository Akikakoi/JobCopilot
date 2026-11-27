"""站内消息：候选人与招聘方的一对一会话。

支持两种来源：
- application：投递后自动创建，会话与投递绑定；
- direct：沟通先于投递，求职者从岗位详情发起或招聘方主动联系。

同一候选人与同一公司最多一个「未绑定投递」的直接会话；投递时若已有这样的会话，会复用它并回填
application_id，避免「先聊后投」变成两个会话。已绑定投递的会话不会复用于其他岗位的直接沟通。
"""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Application, Company, Conversation, Job, Message, Resume, User
from app.utils import utcnow

MAX_MESSAGE_LENGTH = 2000
PREVIEW_LENGTH = 80


class MessageError(ValueError):
    pass


def _job_and_company(
    db: Session, application: Application
) -> tuple[Job | None, Company | None]:
    job = application.job if hasattr(application, "job") else db.get(Job, application.job_id)
    if job is None:
        return None, None
    company = job.company if job.company is not None else db.get(Company, job.company_id)
    return job, company


def ensure_conversation(db: Session, application: Application) -> Conversation:
    """投递会话：已存在则复用；存在同公司直接会话则绑定到本次投递。"""
    conversation = db.scalar(
        select(Conversation).where(Conversation.application_id == application.id)
    )
    if conversation is not None:
        return conversation

    job, company = _job_and_company(db, application)
    if company is None:
        raise MessageError("岗位缺少公司信息，无法创建会话")

    direct = db.scalar(
        select(Conversation)
        .where(
            Conversation.seeker_user_id == application.user_id,
            Conversation.company_id == company.id,
            Conversation.application_id.is_(None),
        )
        .order_by(Conversation.id.desc())
    )
    if direct is not None:
        direct.application_id = application.id
        # 绑定后会话以上述投递为上下文，列表展示的岗位同步切换
        direct.job_id = job.id if job is not None else direct.job_id
        db.flush()
        return direct

    conversation = Conversation(
        application_id=application.id,
        company_id=company.id,
        job_id=job.id if job is not None else None,
        seeker_user_id=application.user_id,
        employer_user_id=company.owner_user_id,
        source="application",
    )
    db.add(conversation)
    db.flush()
    return conversation


def _find_existing_conversation(
    db: Session, seeker_id: int, company_id: int, job: Job | None
) -> Conversation | None:
    if job is not None:
        application = db.scalar(
            select(Application).where(
                Application.user_id == seeker_id, Application.job_id == job.id
            )
        )
        if application is not None:
            conversation = db.scalar(
                select(Conversation).where(
                    Conversation.application_id == application.id
                )
            )
            if conversation is not None:
                return conversation

    return db.scalar(
        select(Conversation)
        .where(
            Conversation.seeker_user_id == seeker_id,
            Conversation.company_id == company_id,
            Conversation.application_id.is_(None),
        )
        .order_by(Conversation.id.desc())
    )


def start_conversation(
    db: Session,
    user: User,
    job_id: int | None = None,
    company_id: int | None = None,
    seeker_user_id: int | None = None,
) -> tuple[Conversation, bool]:
    """发起沟通，返回 (会话, 是否新建)。已存在同候选人同公司的未绑定直接会话时直接返回。"""
    if user.role == "seeker":
        if seeker_user_id is not None:
            raise MessageError("求职者不能指定候选人")
        seeker = user
        job = db.get(Job, job_id) if job_id else None
        if job_id and job is None:
            raise MessageError("岗位不存在")
        if job is not None:
            company = job.company or db.get(Company, job.company_id)
        elif company_id:
            company = db.get(Company, company_id)
        else:
            raise MessageError("请指定岗位或公司")
        if company is None:
            raise MessageError("公司不存在")
    else:
        if seeker_user_id is None:
            raise MessageError("请指定候选人")
        seeker = db.get(User, seeker_user_id)
        if seeker is None or seeker.role != "seeker":
            raise MessageError("候选人不存在")
        company = db.scalar(select(Company).where(Company.owner_user_id == user.id))
        if company is None:
            raise MessageError("请先完善公司信息")
        job = db.get(Job, job_id) if job_id else None
        if job_id and (job is None or job.company_id != company.id):
            raise MessageError("岗位不属于本公司")

    existing = _find_existing_conversation(db, seeker.id, company.id, job)
    if existing is not None:
        return existing, False

    conversation = Conversation(
        application_id=None,
        company_id=company.id,
        job_id=job.id if job is not None else None,
        seeker_user_id=seeker.id,
        employer_user_id=company.owner_user_id,
        source="direct",
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)
    return conversation, True


def post_card(
    db: Session,
    application: Application,
    sender_user_id: int,
    kind: str,
    ref_id: int,
    content: str,
) -> Message | None:
    """把面试邀约 / Offer 作为结构化卡片投递到会话，content 仅用于列表预览。

    同一实体重复投递（如修改 Offer 后重新发送）只更新原卡片消息，不刷屏。
    """
    try:
        conversation = ensure_conversation(db, application)
    except MessageError:
        return None

    message = db.scalar(
        select(Message).where(
            Message.conversation_id == conversation.id,
            Message.kind == kind,
            Message.ref_id == ref_id,
        )
    )
    conversation.updated_at = utcnow()
    if message is not None:
        message.content = content
        db.flush()
        return message

    message = Message(
        conversation_id=conversation.id,
        sender_user_id=sender_user_id,
        content=content,
        kind=kind,
        ref_id=ref_id,
    )
    db.add(message)
    db.flush()
    return message


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


def _ensure_application_conversations(db: Session, user: User) -> None:
    """历史投递没有会话时懒创建，任一方打开消息页即可补齐。"""
    applications = _applications_for_user(db, user)
    if not applications:
        return
    app_ids = [item.id for item in applications]
    existing = {
        row[0]
        for row in db.execute(
            select(Conversation.application_id).where(
                Conversation.application_id.in_(app_ids)
            )
        )
        if row[0] is not None
    }
    created = False
    for application in applications:
        if application.id in existing:
            continue
        try:
            ensure_conversation(db, application)
            created = True
        except MessageError:
            continue
    if created:
        db.commit()


def ensure_conversation_ids(
    db: Session, applications: list[Application]
) -> dict[int, int]:
    """批量确保投递会话存在，返回 application_id → conversation_id。"""
    if not applications:
        return {}
    app_ids = [item.id for item in applications]
    mapping = {
        app_id: conversation_id
        for app_id, conversation_id in db.execute(
            select(Conversation.application_id, Conversation.id).where(
                Conversation.application_id.in_(app_ids)
            )
        )
        if app_id is not None
    }
    created = False
    for application in applications:
        if application.id in mapping:
            continue
        try:
            conversation = ensure_conversation(db, application)
            mapping[application.id] = conversation.id
            created = True
        except MessageError:
            continue
    if created:
        db.commit()
    return mapping


def conversation_ids_by_application(
    db: Session, application_ids: list[int]
) -> dict[int, int]:
    if not application_ids:
        return {}
    return {
        app_id: conversation_id
        for app_id, conversation_id in db.execute(
            select(Conversation.application_id, Conversation.id).where(
                Conversation.application_id.in_(application_ids)
            )
        )
        if app_id is not None
    }


def _message_preview(content: str) -> str:
    text = (content or "").replace("\n", " ").strip()
    return text[:PREVIEW_LENGTH] + ("…" if len(text) > PREVIEW_LENGTH else "")


def list_conversations(db: Session, user: User) -> dict:
    _ensure_application_conversations(db, user)

    stmt = select(Conversation)
    if user.role == "seeker":
        stmt = stmt.where(Conversation.seeker_user_id == user.id)
    else:
        stmt = stmt.where(Conversation.employer_user_id == user.id)
    conversations = list(db.scalars(stmt))
    if not conversations:
        return {"items": [], "unread": 0}

    conv_ids = [item.id for item in conversations]
    messages = list(
        db.scalars(
            select(Message)
            .where(Message.conversation_id.in_(conv_ids))
            .order_by(Message.id.asc())
        )
    )
    last_by_conv: dict[int, Message] = {}
    unread_by_conv: dict[int, int] = {}
    for message in messages:
        last_by_conv[message.conversation_id] = message
        if message.sender_user_id != user.id and message.read_at is None:
            unread_by_conv[message.conversation_id] = (
                unread_by_conv.get(message.conversation_id, 0) + 1
            )

    app_ids = [item.application_id for item in conversations if item.application_id]
    applications = (
        {
            item.id: item
            for item in db.scalars(select(Application).where(Application.id.in_(app_ids)))
        }
        if app_ids
        else {}
    )
    job_ids = {item.job_id for item in conversations if item.job_id}
    job_ids |= {item.job_id for item in applications.values()}
    jobs = (
        {job.id: job for job in db.scalars(select(Job).where(Job.id.in_(job_ids)))}
        if job_ids
        else {}
    )
    company_ids = {item.company_id for item in conversations if item.company_id}
    company_ids |= {job.company_id for job in jobs.values()}
    companies = (
        {
            company.id: company
            for company in db.scalars(
                select(Company).where(Company.id.in_(company_ids))
            )
        }
        if company_ids
        else {}
    )
    seeker_ids = {item.seeker_user_id for item in conversations}
    resumes = {
        resume.user_id: resume
        for resume in db.scalars(select(Resume).where(Resume.user_id.in_(seeker_ids)))
    }
    seekers = {
        item.id: item
        for item in db.scalars(select(User).where(User.id.in_(seeker_ids)))
    }

    items = []
    for conversation in conversations:
        application = applications.get(conversation.application_id or 0)
        job_id = conversation.job_id or (application.job_id if application else None)
        job = jobs.get(job_id or 0)
        company_id = conversation.company_id or (job.company_id if job else None)
        company = companies.get(company_id or 0)
        resume = resumes.get(conversation.seeker_user_id)
        seeker = seekers.get(conversation.seeker_user_id)
        candidate_name = (resume.structured or {}).get("name") if resume else ""
        if not candidate_name and seeker is not None:
            candidate_name = seeker.display_name or seeker.username
        if not candidate_name:
            candidate_name = "候选人"
        company_name = company.name if company else ""
        last = last_by_conv.get(conversation.id)
        items.append(
            {
                "id": conversation.id,
                "application_id": conversation.application_id,
                "company_id": company_id,
                "job_id": job_id,
                "job_title": job.title if job else "",
                "company_name": company_name,
                "candidate_name": candidate_name,
                "other_name": company_name if user.role == "seeker" else candidate_name,
                "source": conversation.source or "application",
                "unread": unread_by_conv.get(conversation.id, 0),
                "last_message": {
                    "content": _message_preview(last.content),
                    "created_at": last.created_at,
                    "sender_user_id": last.sender_user_id,
                    "mine": last.sender_user_id == user.id,
                }
                if last
                else None,
                # 有消息的会话优先按最后一条消息排序，空会话按创建时间排在后面
                "_sort": (
                    (1, last.created_at or conversation.created_at)
                    if last
                    else (0, conversation.created_at or datetime(1970, 1, 1))
                ),
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
        "kind": message.kind or "text",
        "ref_id": message.ref_id,
        "sender_user_id": message.sender_user_id,
        "mine": message.sender_user_id == user.id,
        "created_at": message.created_at,
    }


def list_messages(
    db: Session,
    user: User,
    conversation_id: int,
    after_id: int | None = None,
    before_id: int | None = None,
    limit: int = 100,
) -> tuple[list[dict], bool]:
    """默认返回最新 limit 条；before_id 用于向前翻页，after_id 用于增量拉取。"""
    _get_conversation(db, user, conversation_id)
    if after_id and before_id:
        raise MessageError("after_id 与 before_id 不能同时使用")
    size = min(limit, 200)

    if after_id:
        rows = list(
            db.scalars(
                select(Message)
                .where(Message.conversation_id == conversation_id, Message.id > after_id)
                .order_by(Message.id.asc())
                .limit(size)
            )
        )
        return [message_to_dict(item, user) for item in rows], False

    stmt = select(Message).where(Message.conversation_id == conversation_id)
    if before_id:
        stmt = stmt.where(Message.id < before_id)
    rows = list(db.scalars(stmt.order_by(Message.id.desc()).limit(size + 1)))
    has_more = len(rows) > size
    rows = list(reversed(rows[:size]))
    return [message_to_dict(item, user) for item in rows], has_more


def send_message(
    db: Session, user: User, conversation_id: int, content: str
) -> dict:
    conversation = _get_conversation(db, user, conversation_id)
    text = (content or "").strip()
    if not text:
        raise MessageError("消息内容不能为空")
    if len(text) > MAX_MESSAGE_LENGTH:
        raise MessageError(f"消息不能超过 {MAX_MESSAGE_LENGTH} 字")

    message = Message(
        conversation_id=conversation_id, sender_user_id=user.id, content=text
    )
    conversation.updated_at = utcnow()
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
