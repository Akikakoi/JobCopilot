"""Agent Runtime 行为测试：用 mock 的流式 LLM 验证工具循环、异常回喂与记忆注入（不触网）。"""

import asyncio

from app.agent.runtime import AgentRuntime
from app.db import SessionLocal
from app.models import AgentMemory, AgentMessage, AgentSession, Resume, User


async def collect(agen) -> list[dict]:
    return [event async for event in agen]


def make_runtime(db) -> AgentRuntime:
    user = User(
        username="runtime-user",
        password_hash="x",
        role="seeker",
        display_name="运行时测试",
    )
    db.add(user)
    db.flush()
    db.add(
        Resume(
            user_id=user.id,
            raw_text="张三的简历",
            structured={"name": "张三", "skills": ["Python"], "years_of_experience": 3},
            embedding=[0.1, 0.2, 0.3, 0.4],
            source="paste",
        )
    )
    session = AgentSession(user_id=user.id, agent_type="seeker", title="新会话")
    db.add(session)
    db.commit()
    db.refresh(user)
    db.refresh(session)
    return AgentRuntime(db, user, session)


def test_tool_loop_streams_events_and_persists_messages(client, monkeypatch):
    rounds = {"count": 0}

    async def fake_stream(messages, tools=None):  # noqa: ANN001, ARG001
        rounds["count"] += 1
        if rounds["count"] == 1:
            yield {
                "tool_calls": [
                    {
                        "index": 0,
                        "id": "call_1",
                        "function": {"name": "get_my_resume", "arguments": "{}"},
                    }
                ]
            }
        else:
            yield {"content": "你的"}

    monkeypatch.setattr("app.agent.runtime.chat_completion_stream", fake_stream)

    with SessionLocal() as db:
        runtime = make_runtime(db)
        events = asyncio.run(collect(runtime.stream("看看我的简历")))
        session_id = runtime.session.id

    kinds = [event["type"] for event in events]
    assert kinds[0] == "tool_start"
    assert "tool_end" in kinds
    assert kinds[-1] == "done"
    tool_end = next(event for event in events if event["type"] == "tool_end")
    assert "Python" in tool_end["result"]
    assert "你的" in "".join(e.get("content", "") for e in events if e["type"] == "token")

    with SessionLocal() as db:
        roles = [
            message.role
            for message in db.query(AgentMessage)
            .filter(AgentMessage.session_id == session_id)
            .order_by(AgentMessage.id)
        ]
    assert roles == ["user", "assistant", "tool", "assistant"]


def test_tool_exception_is_fed_back_and_loop_continues(client, monkeypatch):
    class BoomTool:
        name = "boom"

        async def handler(self, db, user, **kwargs):  # noqa: ANN001, ANN002
            raise RuntimeError("数据库炸了")

    monkeypatch.setattr("app.agent.tools.get_tool", lambda agent_type, name: BoomTool())

    rounds = {"count": 0}

    async def fake_stream(messages, tools=None):  # noqa: ANN001, ARG001
        rounds["count"] += 1
        if rounds["count"] == 1:
            yield {
                "tool_calls": [
                    {"index": 0, "id": "call_x", "function": {"name": "boom", "arguments": "{}"}}
                ]
            }
        else:
            yield {"content": "已处理异常"}

    monkeypatch.setattr("app.agent.runtime.chat_completion_stream", fake_stream)

    with SessionLocal() as db:
        runtime = make_runtime(db)
        events = asyncio.run(collect(runtime.stream("触发异常")))

    tool_end = next(event for event in events if event["type"] == "tool_end")
    assert "工具执行失败" in tool_end["result"]
    assert events[-1]["type"] == "done"
    assert any(e["type"] == "token" and "已处理异常" in e["content"] for e in events)


def test_new_session_injects_long_term_memory(client, monkeypatch):
    async def fake_embed(text: str) -> list[float]:
        return [1.0, 0.0, 0.0, 0.0]

    monkeypatch.setattr("app.agent.memory.embed_one", fake_embed)

    captured: dict[str, str] = {}

    async def fake_stream(messages, tools=None):  # noqa: ANN001, ARG001
        captured["system"] = messages[0]["content"]
        yield {"content": "记得"}

    monkeypatch.setattr("app.agent.runtime.chat_completion_stream", fake_stream)

    with SessionLocal() as db:
        runtime = make_runtime(db)
        db.add(
            AgentMemory(
                user_id=runtime.user.id,
                content="用户偏好：只考虑上海的工作",
                embedding=[1.0, 0.0, 0.0, 0.0],
            )
        )
        db.commit()
        asyncio.run(collect(runtime.stream("帮我找工作")))

    assert "只考虑上海的工作" in captured["system"]
