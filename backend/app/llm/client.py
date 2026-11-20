"""OpenAI 兼容的 LLM / Embedding 统一适配层。

chat 与 embedding 各自独立配置（base_url / api_key / model），
切换供应商只改 backend/.env，不改业务代码。
"""

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.config import settings

TIMEOUT = httpx.Timeout(120.0, connect=15.0)


class LLMError(RuntimeError):
    pass


def _chat_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.chat_api_key}",
        "Content-Type": "application/json",
    }


def _embedding_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.embedding_api_key}",
        "Content-Type": "application/json",
    }


async def chat_completion(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    tool_choice: str | dict | None = "auto",
    temperature: float | None = None,
    response_format: dict | None = None,
) -> dict[str, Any]:
    """非流式对话，返回 assistant message（含 content / tool_calls）。"""
    payload: dict[str, Any] = {
        "model": settings.chat_model,
        "messages": messages,
        "temperature": settings.chat_temperature if temperature is None else temperature,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = tool_choice or "auto"
    if response_format:
        payload["response_format"] = response_format

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.post(
            f"{settings.chat_base_url.rstrip('/')}/chat/completions",
            headers=_chat_headers(),
            json=payload,
        )
    if resp.status_code >= 400:
        raise LLMError(f"chat 调用失败 {resp.status_code}: {resp.text[:500]}")
    data = resp.json()
    return data["choices"][0]["message"]


async def chat_completion_stream(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """流式对话。逐块产出 {"content": str, "tool_calls": list[dict]}。"""
    payload: dict[str, Any] = {
        "model": settings.chat_model,
        "messages": messages,
        "temperature": settings.chat_temperature,
        "stream": True,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        async with client.stream(
            "POST",
            f"{settings.chat_base_url.rstrip('/')}/chat/completions",
            headers=_chat_headers(),
            json=payload,
        ) as resp:
            if resp.status_code >= 400:
                body = await resp.aread()
                raise LLMError(f"chat 流式调用失败 {resp.status_code}: {body[:500]!r}")
            async for line in resp.aiter_lines():
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                if not data:
                    continue
                try:
                    chunk = json.loads(data)
                except json.JSONDecodeError:
                    continue
                delta = chunk.get("choices", [{}])[0].get("delta", {}) or {}
                out: dict[str, Any] = {}
                if delta.get("content"):
                    out["content"] = delta["content"]
                if delta.get("tool_calls"):
                    out["tool_calls"] = delta["tool_calls"]
                if out:
                    yield out


async def embed_texts(texts: list[str], batch_size: int = 10) -> list[list[float]]:
    """批量向量化，保持输入顺序返回。"""
    if not texts:
        return []
    vectors: list[list[float]] = []
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        for start in range(0, len(texts), batch_size):
            batch = texts[start : start + batch_size]
            payload: dict[str, Any] = {
                "model": settings.embedding_model,
                "input": batch,
                "encoding_format": "float",
            }
            if settings.embedding_dimensions:
                payload["dimensions"] = settings.embedding_dimensions
            resp = await client.post(
                f"{settings.embedding_base_url.rstrip('/')}/embeddings",
                headers=_embedding_headers(),
                json=payload,
            )
            if resp.status_code >= 400:
                raise LLMError(f"embedding 调用失败 {resp.status_code}: {resp.text[:500]}")
            items = sorted(resp.json()["data"], key=lambda x: x["index"])
            vectors.extend(item["embedding"] for item in items)
    return vectors


async def embed_one(text: str) -> list[float]:
    return (await embed_texts([text]))[0]


def message_text(content: Any) -> str:
    """OpenAI content 可能是 str 或分段数组，统一取纯文本。"""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(part.get("text", "") for part in content if isinstance(part, dict))
    return ""
