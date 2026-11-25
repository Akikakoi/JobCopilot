"""跨模块共用的小工具：统一 UTC 时间与向量相似度计算。"""

from datetime import datetime, timezone

import numpy as np


def utcnow() -> datetime:
    """当前 UTC 时间（naive），与数据库 DateTime 字段的存储语义保持一致。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def to_utc_naive(value: datetime | None) -> datetime | None:
    """带时区的时间转为 UTC naive；已经是 naive 的值按 UTC 理解，原样返回。"""
    if value is None or value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    va, vb = np.asarray(a, dtype=np.float32), np.asarray(b, dtype=np.float32)
    denom = float(np.linalg.norm(va) * np.linalg.norm(vb))
    return 0.0 if denom == 0 else float(np.dot(va, vb) / denom)
