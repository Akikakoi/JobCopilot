"""跨模块共用的小工具：统一 UTC 时间与向量相似度计算。"""

from datetime import datetime, timezone

import numpy as np


def utcnow() -> datetime:
    """当前 UTC 时间（naive），与数据库 DateTime 字段的存储语义保持一致。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    va, vb = np.asarray(a, dtype=np.float32), np.asarray(b, dtype=np.float32)
    denom = float(np.linalg.norm(va) * np.linalg.norm(vb))
    return 0.0 if denom == 0 else float(np.dot(va, vb) / denom)
