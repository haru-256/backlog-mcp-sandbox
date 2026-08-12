import time
import uuid
from collections.abc import Awaitable, Callable
from urllib.parse import urlencode

from fastapi import FastAPI, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from loguru import logger
from openai.types.chat import ChatCompletionMessageParam
from pydantic import BaseModel, Field

from .agent import run_agent
from .jwt_tokens import sign_token
from .logging_config import configure_logging
from .request_context import request_id_var
from .settings import Settings

settings = Settings.from_env()
configure_logging(settings)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    messages: list[ChatCompletionMessageParam]
    user_id: str = Field(min_length=1)
    org_id: str = Field(min_length=1)


class ChatResponse(BaseModel):
    message: ChatCompletionMessageParam
    messages: list[ChatCompletionMessageParam]


class HealthResponse(BaseModel):
    ok: bool


@app.post("/chat")
async def chat(request: ChatRequest) -> ChatResponse:
    messages = await run_agent(list(request.messages), settings, request.user_id, request.org_id)
    return ChatResponse(message=messages[-1], messages=messages)


@app.get("/backlog/connect")
async def backlog_connect(
    user_id: str = Query(min_length=1),
    org_id: str = Query(min_length=1),
) -> RedirectResponse:
    state = sign_token(
        secret=settings.mcp_jwt_secret,
        typ="connect",
        user_id=user_id,
        org_id=org_id,
        issuer=settings.host_public_url,
        ttl_seconds=settings.connect_token_ttl_seconds,
    )
    query = urlencode({"state": state})
    return RedirectResponse(f"{settings.mcp_public_url}/connect?{query}", status_code=302)


@app.get("/health")
async def health() -> HealthResponse:
    return HealthResponse(ok=True)


@app.middleware("http")
async def access_log(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    token = request_id_var.set(request_id)
    request.state.request_id = request_id

    try:
        started = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - started) * 1000
        logger.info(
            "access method={method} path={path} status={status} duration_ms={duration_ms:.1f}",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=duration_ms,
        )
        response.headers["x-request-id"] = request_id
        response.headers["x-process-time"] = str(duration_ms)
        return response
    finally:
        request_id_var.reset(token)
