from typing import Any


def ok(data: Any = None, message: str = "ok") -> dict[str, Any]:
    return {"code": 0, "data": data, "message": message}


def fail(code: int, message: str, data: Any = None) -> dict[str, Any]:
    return {"code": code, "data": data, "message": message}
