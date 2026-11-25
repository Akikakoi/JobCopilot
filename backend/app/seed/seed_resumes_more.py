"""增量灌库（简历侧）：把 seed_data/resumes 下尚未入库的简历追加为新的求职者账号。

与 app.seed.seed 的区别：不 drop、不重建、不动现有用户/岗位/投递；
新简历按简历里的姓名查重（display_name），用户名 cand 编号自动续接。
幂等：重复运行只处理尚未入库的简历文件。

运行：cd backend && .venv/Scripts/python.exe -m app.seed.seed_resumes_more
"""

import asyncio
import re
from pathlib import Path

from app.config import BASE_DIR
from app.db import SessionLocal, init_db
from app.llm.client import embed_texts
from app.models import Resume, User
from app.security import hash_password
from app.seed.seed import DEMO_PASSWORD, parse_resume
from app.services.resume_service import build_resume_embedding_text

ROOT = BASE_DIR.parent
RESUMES_DIR = ROOT / "seed_data" / "resumes"


def _next_username(db) -> str:
    """现有 cand 编号最大值 + 1，保证编号连续且不冲突。"""
    usernames = [
        row[0]
        for row in db.query(User.username).filter(User.username.like("cand%")).all()
    ]
    numbers = []
    for name in usernames:
        m = re.match(r"cand(\d+)", name)
        if m:
            numbers.append(int(m.group(1)))
    return f"cand{max(numbers, default=1) + 1:03d}"


async def seed_resumes_more() -> int:
    init_db()
    db = SessionLocal()
    try:
        paths = sorted(RESUMES_DIR.glob("*.md"))
        existing_names = {
            row[0]
            for row in db.query(User.display_name).filter(User.role == "seeker").all()
        }
        pending: list[tuple[dict, dict]] = []
        seen_new_names: set[str] = set()
        for path in paths:
            structured, extra = parse_resume(path)
            name = structured.get("name") or ""
            if not name or name in existing_names or name in seen_new_names:
                continue
            seen_new_names.add(name)
            pending.append((structured, extra))

        if not pending:
            print("没有待入库的新简历")
            return 0

        vectors = await embed_texts(
            [build_resume_embedding_text(item[0]) for item in pending]
        )

        created = 0
        for (structured, extra), vector in zip(pending, vectors, strict=True):
            username = _next_username(db)
            user = User(
                username=username,
                password_hash=hash_password(DEMO_PASSWORD),
                role="seeker",
                display_name=structured.get("name") or username,
            )
            db.add(user)
            db.flush()
            db.add(
                Resume(
                    user_id=user.id,
                    raw_text=extra["raw_text"],
                    structured=structured,
                    embedding=vector,
                    source="upload",
                )
            )
            created += 1
        db.commit()
        print(
            f"新增求职者 {created} 人（用户名自动续接），当前简历总数 "
            f"{db.query(Resume).count()}"
        )
        return created
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(seed_resumes_more())
