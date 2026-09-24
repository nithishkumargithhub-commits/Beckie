"""
JARVIS – FastAPI router: OpenAI-compatible Ollama endpoints.

Endpoints:
  GET  /v1/models                – list available models
  POST /v1/chat/completions      – chat with streaming support
  GET  /v1/health                – server + model health
  GET  /v1/audit                 – recent audit log tail
  GET  /v1/permissions/status    – current session permission state
  POST /v1/permissions/revoke    – revoke all write grants for session
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any, AsyncIterator, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

logger = logging.getLogger("Jarvis.API.OllamaRouter")

router = APIRouter(prefix="/v1", tags=["OpenAI-Compatible"])


# ---------------------------------------------------------------------------
# Pydantic schemas (OpenAI-compatible)
# ---------------------------------------------------------------------------

class ChatMessageSchema(BaseModel):
    role: str = Field(..., pattern="^(system|user|assistant|tool)$")
    content: str
    name: Optional[str] = None


class ChatCompletionRequest(BaseModel):
    model: Optional[str] = None
    messages: list[ChatMessageSchema]
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=1024, ge=1, le=8192)
    stream: bool = False


class PermissionRevokeRequest(BaseModel):
    session_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Dependency: get adapter from app state
# ---------------------------------------------------------------------------

def _get_adapter(request: Request):
    adapter = getattr(request.app.state, "ollama_adapter", None)
    if adapter is None:
        raise HTTPException(status_code=503, detail="Ollama adapter not initialised")
    return adapter


def _get_audit(request: Request):
    return getattr(request.app.state, "audit_logger", None)


def _get_broker(request: Request):
    return getattr(request.app.state, "permission_broker", None)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/health")
async def health(request: Request):
    """Check Ollama server reachability and model availability."""
    adapter = _get_adapter(request)
    audit = _get_audit(request)

    healthy = await adapter.is_healthy_async()
    models = adapter.list_models() if healthy else []

    if audit:
        audit.log_system("health_check", status="completed", details={"healthy": healthy})

    return JSONResponse({
        "status": "ok" if healthy else "degraded",
        "ollama": healthy,
        "models_available": len(models),
        "models": [m.to_dict() for m in models],
    })


@router.get("/models")
async def list_models(request: Request):
    """Return available models in OpenAI /v1/models format."""
    adapter = _get_adapter(request)
    models = adapter.list_models()
    return JSONResponse({
        "object": "list",
        "data": [m.to_dict() for m in models],
    })


@router.post("/chat/completions")
async def chat_completions(body: ChatCompletionRequest, request: Request):
    """
    OpenAI-compatible chat completions endpoint.
    Supports streaming (text/event-stream) and non-streaming JSON.
    All requests are audited.
    """
    from core.ollama_adapter import ChatMessage

    adapter = _get_adapter(request)
    audit = _get_audit(request)
    broker = _get_broker(request)

    # Permission gate: LLM queries are READ tier (auto-approved, audited)
    if broker:
        result = broker.request(
            action_name="chat_completion",
            details={"model": body.model, "message_count": len(body.messages)},
        )
        if not result.granted:
            raise HTTPException(status_code=403, detail="Chat completion denied by PermissionBroker")

    messages = [
        ChatMessage(role=m.role, content=m.content, name=m.name)
        for m in body.messages
    ]
    start = time.monotonic()

    if body.stream:
        async def stream_generator() -> AsyncIterator[bytes]:
            """Yield SSE chunks in OpenAI delta format."""
            completion_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
            token_count = 0
            try:
                gen = await adapter.chat_async(
                    messages=messages,
                    model=body.model,
                    temperature=body.temperature,
                    max_tokens=body.max_tokens,
                    stream=True,
                )
                async for delta in gen:
                    token_count += 1
                    chunk = {
                        "id": completion_id,
                        "object": "chat.completion.chunk",
                        "created": int(time.time()),
                        "model": body.model or "qwen3:8b",
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"role": "assistant", "content": delta},
                                "finish_reason": None,
                            }
                        ],
                    }
                    yield f"data: {json.dumps(chunk)}\n\n".encode()

                # Final done chunk
                done_chunk = {
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "created": int(time.time()),
                    "model": body.model or "qwen3:8b",
                    "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                }
                yield f"data: {json.dumps(done_chunk)}\n\n".encode()
                yield b"data: [DONE]\n\n"

            except Exception as exc:
                logger.error("Stream error: %s", exc)
                yield f"data: {json.dumps({'error': str(exc)})}\n\n".encode()
            finally:
                duration_ms = int((time.monotonic() - start) * 1000)
                if audit:
                    audit.log_llm_query(
                        prompt_tokens=len(messages),
                        completion_tokens=token_count,
                        model=body.model or "qwen3:8b",
                        duration_ms=duration_ms,
                    )

        return StreamingResponse(stream_generator(), media_type="text/event-stream")

    # Non-streaming
    try:
        completion = await adapter.chat_async(
            messages=messages,
            model=body.model,
            temperature=body.temperature,
            max_tokens=body.max_tokens,
            stream=False,
        )
        duration_ms = int((time.monotonic() - start) * 1000)
        if audit:
            audit.log_llm_query(
                prompt_tokens=completion.usage.prompt_tokens,
                completion_tokens=completion.usage.completion_tokens,
                model=body.model or "qwen3:8b",
                duration_ms=duration_ms,
            )
        return JSONResponse(completion.to_dict())

    except Exception as exc:
        duration_ms = int((time.monotonic() - start) * 1000)
        if audit:
            audit.log_llm_query(
                prompt_tokens=0,
                completion_tokens=0,
                model=body.model or "unknown",
                duration_ms=duration_ms,
                status="error",
                details={"error": str(exc)},
            )
        logger.error("Chat completion error: %s", exc)
        raise HTTPException(status_code=500, detail=f"LLM error: {exc}")


@router.get("/audit")
async def audit_tail(request: Request, limit: int = 50):
    """Return the most recent audit log entries."""
    audit = _get_audit(request)
    if audit is None:
        raise HTTPException(status_code=503, detail="Audit logger not available")
    return JSONResponse({"records": audit.recent(limit=min(limit, 500))})


@router.get("/audit/session")
async def audit_session_summary(request: Request):
    """Return aggregate stats for the current session."""
    audit = _get_audit(request)
    if audit is None:
        raise HTTPException(status_code=503, detail="Audit logger not available")
    return JSONResponse(audit.session_summary())


@router.get("/permissions/status")
async def permission_status(request: Request):
    """Return current permission grants for this session."""
    broker = _get_broker(request)
    if broker is None:
        raise HTTPException(status_code=503, detail="Permission broker not available")
    return JSONResponse(broker.status_summary())


@router.post("/permissions/revoke")
async def revoke_permissions(body: PermissionRevokeRequest, request: Request):
    """Revoke all in-memory WRITE permission grants for this session."""
    broker = _get_broker(request)
    audit = _get_audit(request)
    if broker is None:
        raise HTTPException(status_code=503, detail="Permission broker not available")
    broker.revoke_session_permissions()
    if audit:
        audit.log_system("permissions_revoked", details={"requested_by": "api"})
    return JSONResponse({"status": "revoked", "session_id": broker._session_id})
