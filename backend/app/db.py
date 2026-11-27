from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


APPLICATION_ONBOARDING_COLUMNS = {
    "onboarding_date": "VARCHAR(32) NOT NULL DEFAULT ''",
    "onboarding_confirmed_at": "DATETIME",
    "onboarding_result": "VARCHAR(16) NOT NULL DEFAULT ''",
    "onboarding_result_at": "DATETIME",
    "onboarding_note": "TEXT NOT NULL DEFAULT ''",
}


def _ensure_application_columns() -> None:
    """旧库增量补列：create_all 不会修改已有表，这里只做可空/带默认值的追加。"""
    inspector = inspect(engine)
    if "applications" not in inspector.get_table_names():
        return
    existing = {column["name"] for column in inspector.get_columns("applications")}
    missing = {
        name: ddl
        for name, ddl in APPLICATION_ONBOARDING_COLUMNS.items()
        if name not in existing
    }
    if not missing:
        return
    with engine.begin() as conn:
        for name, ddl in missing.items():
            conn.execute(text(f"ALTER TABLE applications ADD COLUMN {name} {ddl}"))


CONVERSATION_COLUMNS = {
    "company_id": "INTEGER",
    "job_id": "INTEGER",
    "source": "VARCHAR(16) NOT NULL DEFAULT 'application'",
}

# SQLite 无法直接去掉 NOT NULL，直接沟通上线需要把 application_id 放宽为可空，只能重建表。
_CONVERSATIONS_REBUILD_DDL = """
CREATE TABLE conversations_new (
    id INTEGER NOT NULL,
    application_id INTEGER,
    company_id INTEGER,
    job_id INTEGER,
    seeker_user_id INTEGER NOT NULL,
    employer_user_id INTEGER NOT NULL,
    source VARCHAR(16) NOT NULL DEFAULT 'application',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(application_id) REFERENCES applications (id),
    FOREIGN KEY(company_id) REFERENCES companies (id),
    FOREIGN KEY(job_id) REFERENCES jobs (id),
    FOREIGN KEY(seeker_user_id) REFERENCES users (id),
    FOREIGN KEY(employer_user_id) REFERENCES users (id)
)
"""


def _ensure_message_columns() -> None:
    """旧库增量补列：卡片消息的 kind / ref_id。"""
    inspector = inspect(engine)
    if "messages" not in inspector.get_table_names():
        return
    existing = {column["name"] for column in inspector.get_columns("messages")}
    missing = {
        "kind": "VARCHAR(16) NOT NULL DEFAULT 'text'",
        "ref_id": "INTEGER",
    }
    missing = {name: ddl for name, ddl in missing.items() if name not in existing}
    if not missing:
        return
    with engine.begin() as conn:
        for name, ddl in missing.items():
            conn.execute(text(f"ALTER TABLE messages ADD COLUMN {name} {ddl}"))


def _ensure_conversation_schema() -> None:
    """旧库升级：补 company_id / job_id / source，并放宽 application_id 为可空。"""
    inspector = inspect(engine)
    if "conversations" not in inspector.get_table_names():
        return
    columns = {column["name"]: column for column in inspector.get_columns("conversations")}
    missing = {
        name: ddl for name, ddl in CONVERSATION_COLUMNS.items() if name not in columns
    }
    needs_rebuild = columns["application_id"]["nullable"] is False
    if not missing and not needs_rebuild:
        return

    with engine.begin() as conn:
        for name, ddl in missing.items():
            conn.execute(text(f"ALTER TABLE conversations ADD COLUMN {name} {ddl}"))
        conn.execute(
            text(
                """
                UPDATE conversations SET company_id = (
                    SELECT j.company_id FROM applications a
                    JOIN jobs j ON a.job_id = j.id
                    WHERE a.id = conversations.application_id
                )
                WHERE company_id IS NULL AND application_id IS NOT NULL
                """
            )
        )
        conn.execute(
            text(
                """
                UPDATE conversations SET job_id = (
                    SELECT a.job_id FROM applications a
                    WHERE a.id = conversations.application_id
                )
                WHERE job_id IS NULL AND application_id IS NOT NULL
                """
            )
        )

    if not needs_rebuild or not settings.database_url.startswith("sqlite"):
        return

    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS conversations_new"))
        conn.execute(text(_CONVERSATIONS_REBUILD_DDL))
        conn.execute(
            text(
                """
                INSERT INTO conversations_new
                    (id, application_id, company_id, job_id,
                     seeker_user_id, employer_user_id, source, created_at, updated_at)
                SELECT id, application_id, company_id, job_id,
                       seeker_user_id, employer_user_id, source, created_at, updated_at
                FROM conversations
                """
            )
        )
        conn.execute(text("DROP TABLE conversations"))
        conn.execute(text("ALTER TABLE conversations_new RENAME TO conversations"))
        conn.execute(
            text(
                "CREATE UNIQUE INDEX ix_conversations_application_id "
                "ON conversations (application_id)"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX ix_conversations_seeker_user_id "
                "ON conversations (seeker_user_id)"
            )
        )
        conn.execute(
            text(
                "CREATE INDEX ix_conversations_employer_user_id "
                "ON conversations (employer_user_id)"
            )
        )
        conn.execute(
            text("CREATE INDEX ix_conversations_company_id ON conversations (company_id)")
        )
        conn.execute(text("CREATE INDEX ix_conversations_job_id ON conversations (job_id)"))


def init_db() -> None:
    """建表（幂等）。学习项目用 create_all 代替迁移链，见开发文档 §4 备注。"""
    from app import models  # noqa: F401  确保所有模型已注册

    Base.metadata.create_all(bind=engine)
    _ensure_application_columns()
    _ensure_conversation_schema()
    _ensure_message_columns()
    _backfill_match_explanations()


def _backfill_match_explanations() -> None:
    """一次性回填：把投递记录里已有的解读迁到独立缓存表，避免升级后重调 LLM。

    幂等：缓存表已有该 (resume_id, job_id) 时跳过。
    """
    from sqlalchemy import text

    inspector = inspect(engine)
    if "match_explanations" not in inspector.get_table_names():
        return
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT OR IGNORE INTO match_explanations
                    (resume_id, job_id, fingerprint, match_score, explanation)
                SELECT a.resume_id, a.job_id, '', COALESCE(a.match_score, 0),
                       a.match_explanation
                FROM applications a
                WHERE a.match_explanation IS NOT NULL
                  AND NOT EXISTS (
                    SELECT 1 FROM match_explanations m
                    WHERE m.resume_id = a.resume_id AND m.job_id = a.job_id
                  )
                """
            )
        )
