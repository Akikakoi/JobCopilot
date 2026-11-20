"""自研 Agent Runtime：tool-calling 执行循环 + 会话记忆 + 长期记忆注入 + SSE 事件流。"""

import json
import uuid
from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agent import memory as memory_tools
from app.agent import tools as tool_registry
from app.agent.prompts import system_prompt
from app.llm.client import LLMError, chat_completion_stream
from app.models import AgentMessage, AgentSession, User

MAX_TOOL_ROUNDS = 8
HISTORY_LIMIT = 24


def _safe_json(raw: str) -> Any:
    try:
        return json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        return {"_raw": raw}


class AgentRuntime:
    def __init__(self, db: Session, user: User, session: AgentSession):
        self.db = db
        self.user = user
        self.session = session
        self.agent_type = session.agent_type

    async def stream(self, user_input: str) -> AsyncIterator[dict]:
        user_message = AgentMessage(session_id=self.session.id, role="user", content=user_input)
        self.db.add(user_message)
        if self.session.title in ("", "新会话"):
            self.session.title = user_input.strip()[:24] or "新会话"
        self.db.commit()

        messages = await self._build_messages(user_input)
        tool_schemas = tool_registry.tool_schemas(self.agent_type)

        for _ in range(MAX_TOOL_ROUNDS):
            content_buffer = ""
            call_accumulator: dict[int, dict] = {}

            try:
                async for chunk in chat_completion_stream(messages, tools=tool_schemas):
                    if chunk.get("content"):
                        content_buffer += chunk["content"]
                        yield {"type": "token", "content": chunk["content"]}
                    for delta_call in chunk.get("tool_calls") or []:
                        index = delta_call.get("index", 0)
                        entry = call_accumulator.setdefault(
                            index,
                            {"id": "", "type": "function", "function": {"name": "", "arguments": ""}},
                        )
                        if delta_call.get("id"):
                            entry["id"] = delta_call["id"]
                        function = delta_call.get("function") or {}
                        if function.get("name"):
                            entry["function"]["name"] += function["name"]
                        if function.get("arguments"):
                            entry["function"]["arguments"] += function["arguments"]
            except LLMError as exc:
                yield {"type": "error", "message": str(exc)}
                return

            if not call_accumulator:
                assistant_message = AgentMessage(
                    session_id=self.session.id, role="assistant", content=content_buffer
                )
                self.db.add(assistant_message)
                self.db.commit()
                self.db.refresh(assistant_message)
                yield {
                    "type": "done",
                    "message_id": assistant_message.id,
                    "session_title": self.session.title,
                }
                return

            tool_calls = [call_accumulator[i] for i in sorted(call_accumulator)]
            for call in tool_calls:
                if not call["id"]:
                    call["id"] = f"call_{uuid.uuid4().hex[:12]}"

            self.db.add(
                AgentMessage(
                    session_id=self.session.id,
                    role="assistant",
                    content=content_buffer,
                    tool_calls=tool_calls,
                )
            )
            self.db.commit()
            messages.append(
                {"role": "assistant", "content": content_buffer, "tool_calls": tool_calls}
            )

            for call in tool_calls:
                name = call["function"]["name"]
                raw_args = call["function"]["arguments"] or "{}"
                yield {
                    "type": "tool_start",
                    "id": call["id"],
                    "name": name,
                    "args": _safe_json(raw_args),
                }
                result_text = await self._execute_tool(name, raw_args)
                yield {
                    "type": "tool_end",
                    "id": call["id"],
                    "name": name,
                    "result": result_text[:600],
                }
                self.db.add(
                    AgentMessage(
                        session_id=self.session.id,
                        role="tool",
                        content=result_text,
                        tool_call_id=call["id"],
                    )
                )
                self.db.commit()
                messages.append(
                    {"role": "tool", "tool_call_id": call["id"], "content": result_text}
                )

        fallback = AgentMessage(
            session_id=self.session.id,
            role="assistant",
            content="（本轮工具调用次数已达上限，请补充信息后再试）",
        )
        self.db.add(fallback)
        self.db.commit()
        self.db.refresh(fallback)
        yield {
            "type": "done",
            "message_id": fallback.id,
            "note": "已达到单轮工具调用上限",
        }

    async def _execute_tool(self, name: str, raw_args: str) -> str:
        tool = tool_registry.get_tool(self.agent_type, name)
        if tool is None:
            return json.dumps({"error": f"未知工具 {name}"}, ensure_ascii=False)
        args = _safe_json(raw_args)
        if not isinstance(args, dict):
            return json.dumps({"error": "工具参数必须是 JSON 对象"}, ensure_ascii=False)
        try:
            result = await tool.handler(self.db, self.user, **args)
        except TypeError as exc:
            result = {"error": f"工具参数不匹配：{exc}"}
        except Exception as exc:  # noqa: BLE001 工具异常回喂 LLM，不炸循环
            self.db.rollback()  # 事务可能已脏，先回滚，避免后续 commit 抛 PendingRollbackError
            result = {"error": f"工具执行失败：{exc}"}
        return memory_tools.dump_result(result)

    async def _build_messages(self, user_input: str) -> list[dict]:
        prompt = system_prompt(self.agent_type)

        # 会话首次对话：主动检索长期记忆并注入（D11 演示彩蛋的可靠实现）
        has_history = self.db.scalar(
            select(AgentMessage.id)
            .where(AgentMessage.session_id == self.session.id, AgentMessage.role == "assistant")
            .limit(1)
        )
        if not has_history:
            memories = await memory_tools.search_memory(self.db, self.user.id, user_input, top_k=5)
            if memories:
                lines = "\n".join(f"- {m['content']}" for m in memories)
                prompt += f"\n\n【已知用户体验/偏好（来自长期记忆）】\n{lines}"

        history = list(
            self.db.scalars(
                select(AgentMessage)
                .where(AgentMessage.session_id == self.session.id, AgentMessage.role != "system")
                .order_by(AgentMessage.id.desc())
                .limit(HISTORY_LIMIT)
            )
        )[::-1]
        # 避免历史从孤立的 tool 消息开始（OpenAI 协议要求 tool 紧跟 assistant.tool_calls）
        while history and history[0].role == "tool":
            history.pop(0)

        # 剔除不完整的工具轮（assistant.tool_calls 缺少对应 tool 结果），否则上游 API 会报错
        available_tool_ids = {m.tool_call_id for m in history if m.role == "tool"}
        keep_tool_ids: set[str] = set()
        normalized: list[AgentMessage] = []
        for message in history:
            if message.role == "assistant" and message.tool_calls:
                call_ids = [call.get("id") for call in message.tool_calls]
                if all(call_id in available_tool_ids for call_id in call_ids):
                    keep_tool_ids.update(call_ids)
                    normalized.append(message)
            elif message.role == "tool":
                if message.tool_call_id in keep_tool_ids:
                    normalized.append(message)
            else:
                normalized.append(message)

        messages: list[dict] = [{"role": "system", "content": prompt}]
        for message in normalized:
            if message.role == "assistant" and message.tool_calls:
                messages.append(
                    {
                        "role": "assistant",
                        "content": message.content or "",
                        "tool_calls": message.tool_calls,
                    }
                )
            elif message.role == "tool":
                messages.append(
                    {
                        "role": "tool",
                        "content": message.content,
                        "tool_call_id": message.tool_call_id or "",
                    }
                )
            else:
                messages.append({"role": message.role, "content": message.content})
        return messages
