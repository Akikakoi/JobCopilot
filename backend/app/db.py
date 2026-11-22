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


def init_db() -> None:
    """建表（幂等）。学习项目用 create_all 代替迁移链，见开发文档 §4 备注。"""
    from app import models  # noqa: F401  确保所有模型已注册

    Base.metadata.create_all(bind=engine)
    _ensure_application_columns()
