"""二期彩蛋：求职者 Agent × 招聘方 Agent 的自主对谈。

双方各自拥有受限工具集（只读为主），交替发言，事件以 SSE 推给前端。
不落库、不污染正式会话，属于纯演示编排层。
"""

import json
import uuid
from collections.abc import AsyncIterator

from sqlalchemy.orm import Session

from app.agent import tools as tool_registry
from app.agent.memory import dump_result
from app.llm.client import chat_completion_stream
from app.models import Application, Job, User

MAX_TOOL_ROUNDS = 3
TURN_CHAR_LIMIT = 1600

# 对谈只开放只读工具，避免彩蛋过程产生投递、改状态等副作用
DUEL_TOOLS = {
    "seeker": ["get_my_resume", "get_job_detail", "suggest_resume_improvements"],
    "employer": ["get_job_detail", "list_candidates", "screen_candidate"],
}

SEEKER_PROMPT = """你是 JobCopilot 的求职者 Agent，正在「AI 双方面谈」中代表候选人 {name} 与招聘方 Agent 对话。
目标：基于真实简历与岗位，说明自己的匹配点与优势，回应对方质疑。
规则：必须使用工具返回的真实数据，禁止编造经历；中文；每次发言 120-200 字，分点表达；首轮先做简短自我介绍；不要提及工具名。
本次对谈的岗位 id 是 {job_id}，调用 get_job_detail 时必须使用该 id，不得猜测。

岗位信息：
{job}

候选人简历：
{resume}"""

EMPLOYER_PROMPT = """你是 {company} 的招聘方 Agent，正在与候选人 Agent 进行「AI 双方面谈」。
目标：围绕岗位要求，追问 1-2 个关键问题（技能、项目深度、年限、薪资预期），并给出专业判断。
规则：必须使用工具返回的真实数据，禁止编造；中文；每次发言 120-200 字；专业但不客气；最后一轮必须明确给出「是否推进面试」的结论与理由；不要提及工具名。
本次对谈的岗位 id 是 {job_id}，候选人投递 id 是 {application_id}；调用 list_candidates / screen_candidate 时必须使用这两个 id，不得猜测。

岗位信息：
{job}

候选人简历：
{resume}"""


def _job_payload(job: Job) -> str:
    return json.dumps(
        {
            "id": job.id,
            "title": job.title,
            "company": job.company.name if job.company else "",
            "location": job.location,
            "salary": f"{job.salary_min}-{job.salary_max}K",
            "experience": f"{job.experience_min}-{job.experience_max} 年",
            "required_skills": job.required_skills or [],
            "preferred_skills": job.preferred_skills or [],
            "description": job.description or "",
        },
        ensure_ascii=False,
    )


def _resume_payload(application: Application, db: Session) -> str:
    from app.models import Resume

    resume = db.get(Resume, application.resume_id)
    return json.dumps(resume.structured if resume else {}, ensure_ascii=False)


def _tool_schemas(agent_type: str) -> list[dict]:
    schemas: list[dict] = []
    for name in DUEL_TOOLS[agent_type]:
        tool = tool_registry.get_tool(agent_type, name)
        if tool is not None:
            schemas.append(tool.schema())
    return schemas


def _build_messages(
    agent_type: str,
    job: Job,
    application: Application,
    db: Session,
    transcript: list[tuple[str, str]],
    final: bool,
) -> list[dict]:
    resume_json = _resume_payload(application, db)
    job_json = _job_payload(job)
    if agent_type == "seeker":
        name = (json.loads(resume_json).get("name") if resume_json else "") or "求职者"
        system = SEEKER_PROMPT.format(
            name=name, job=job_json, resume=resume_json, job_id=job.id
        )
    else:
        system = EMPLOYER_PROMPT.format(
            company=job.company.name if job.company else "本公司",
            job=job_json,
            resume=resume_json,
            job_id=job.id,
            application_id=application.id,
        )

    messages: list[dict] = [{"role": "system", "content": system}]
    if not transcript:
        messages.append({"role": "user", "content": "现在开始，请按你的角色开场发言。"})
    for speaker, content in transcript:
        role = "assistant" if speaker == agent_type else "user"
        messages.append({"role": role, "content": content})
    if transcript and transcript[-1][0] == agent_type:
        messages.append({"role": "user", "content": "请继续。"})
    if final:
        messages.append({"role": "user", "content": "（这是你的最后一轮发言，请收束并给出结论。）"})
    return messages


async def _execute_tool(
    db: Session, user: User, agent_type: str, name: str, raw_args: str
) -> str:
    if name not in DUEL_TOOLS[agent_type]:
        return json.dumps({"error": f"对谈中不可调用工具 {name}"}, ensure_ascii=False)
    tool = tool_registry.get_tool(agent_type, name)
    if tool is None:
        return json.dumps({"error": f"未知工具 {name}"}, ensure_ascii=False)
    try:
        args = json.loads(raw_args or "{}")
    except json.JSONDecodeError:
        args = {}
    if not isinstance(args, dict):
        args = {}
    try:
        result = await tool.handler(db, user, **args)
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        result = {"error": f"工具执行失败：{exc}"}
    return dump_result(result)


async def _run_turn(
    db: Session,
    user: User,
    agent_type: str,
    messages: list[dict],
) -> AsyncIterator[dict]:
    """单个 Agent 的一轮发言（内部可能多次工具调用）。最后产出 turn_content 事件。"""
    schema = _tool_schemas(agent_type)
    content_all = ""

    for _ in range(MAX_TOOL_ROUNDS):
        content = ""
        calls: dict[int, dict] = {}
        async for chunk in chat_completion_stream(messages, tools=schema):
            if chunk.get("content"):
                content += chunk["content"]
                content_all += chunk["content"]
                yield {"type": "token", "speaker": agent_type, "content": chunk["content"]}
            for delta in chunk.get("tool_calls") or []:
                index = delta.get("index", 0)
                entry = calls.setdefault(
                    index,
                    {"id": "", "type": "function", "function": {"name": "", "arguments": ""}},
                )
                if delta.get("id"):
                    entry["id"] = delta["id"]
                function = delta.get("function") or {}
                if function.get("name"):
                    entry["function"]["name"] += function["name"]
                if function.get("arguments"):
                    entry["function"]["arguments"] += function["arguments"]

        if not calls:
            yield {"type": "turn_content", "speaker": agent_type, "content": content_all.strip()[:TURN_CHAR_LIMIT]}
            return

        tool_calls = [calls[i] for i in sorted(calls)]
        for call in tool_calls:
            if not call["id"]:
                call["id"] = f"duel_{uuid.uuid4().hex[:10]}"
        messages.append({"role": "assistant", "content": content, "tool_calls": tool_calls})

        for call in tool_calls:
            name = call["function"]["name"]
            raw_args = call["function"]["arguments"] or "{}"
            yield {
                "type": "tool_start",
                "speaker": agent_type,
                "id": call["id"],
                "name": name,
                "args": _safe_args(raw_args),
            }
            result = await _execute_tool(db, user, agent_type, name, raw_args)
            yield {
                "type": "tool_end",
                "speaker": agent_type,
                "id": call["id"],
                "name": name,
                "result": result[:600],
            }
            messages.append({"role": "tool", "tool_call_id": call["id"], "content": result})

    yield {"type": "turn_content", "speaker": agent_type, "content": content_all.strip()[:TURN_CHAR_LIMIT]}


def _safe_args(raw: str):
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"_raw": raw}


async def stream_duel(
    db: Session,
    employer: User,
    job: Job,
    application: Application,
    rounds: int = 2,
) -> AsyncIterator[dict]:
    seeker_user = db.get(User, application.user_id)
    if seeker_user is None:
        yield {"type": "error", "message": "候选人不存在"}
        return

    transcript: list[tuple[str, str]] = []
    yield {"type": "duel_start", "rounds": rounds, "job": job.title}

    for round_index in range(rounds):
        for agent_type, user in (("seeker", seeker_user), ("employer", employer)):
            final = round_index == rounds - 1 and agent_type == "employer"
            yield {
                "type": "speaker",
                "speaker": agent_type,
                "round": round_index + 1,
            }
            messages = _build_messages(agent_type, job, application, db, transcript, final)
            content = ""
            async for event in _run_turn(db, user, agent_type, messages):
                if event["type"] == "turn_content":
                    content = event["content"]
                else:
                    yield event
            if not content:
                content = "（本轮未产生有效发言）"
            transcript.append((agent_type, content))
            yield {"type": "turn_end", "speaker": agent_type, "content": content}

    yield {"type": "done", "turns": len(transcript)}
