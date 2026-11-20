from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.status_code, "data": None, "message": str(exc.detail)},
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    first = exc.errors()[0] if exc.errors() else {}
    msg = first.get("msg", "参数校验失败")
    return JSONResponse(
        status_code=422,
        content={"code": 422, "data": exc.errors(), "message": f"参数校验失败：{msg}"},
    )


@app.get("/api/health")
def health():
    return {"code": 0, "data": {"status": "ok"}, "message": "ok"}


# 路由注册（按里程碑逐步补齐）
from app.routers import (  # noqa: E402
    agent,
    applications,
    auth,
    interviews,
    jobs,
    match,
    notifications,
    resumes,
    subscriptions,
)

app.include_router(auth.router, prefix="/api")
app.include_router(resumes.router, prefix="/api")
app.include_router(jobs.router, prefix="/api")
app.include_router(applications.router, prefix="/api")
app.include_router(match.router, prefix="/api")
app.include_router(interviews.router, prefix="/api")
app.include_router(subscriptions.router, prefix="/api")
app.include_router(notifications.router, prefix="/api")
app.include_router(agent.router, prefix="/api")
