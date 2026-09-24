"""
JARVIS – Ollama Adapter with OpenAI-compatible REST API.

Wraps the local Ollama runtime and exposes:
  - Streaming + non-streaming chat completions
  - Model listing
  - Health check
  - Automatic context-window management
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Iterator, Optional

import httpx

logger = logging.getLogger("Jarvis.Core.OllamaAdapter")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

OLLAMA_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_MODEL = "qwen3:8b"
DEFAULT_TIMEOUT = 120.0          # seconds for non-streaming
DEFAULT_STREAM_TIMEOUT = 300.0   # seconds for streaming
MAX_CONTEXT_TOKENS = 4096


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class ChatMessage:
    role: str      # system | user | assistant | tool
    content: str
    name: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"role": self.role, "content": self.content}
        if self.name:
            d["name"] = self.name
        return d


@dataclass
class CompletionChoice:
    index: int
    message: ChatMessage
    finish_reason: str = "stop"

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "message": self.message.to_dict(),
            "finish_reason": self.finish_reason,
        }


@dataclass
class CompletionUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def to_dict(self) -> dict[str, int]:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
        }


@dataclass
class ChatCompletion:
    """OpenAI-compatible chat completion response."""

    id: str = field(default_factory=lambda: f"chatcmpl-{uuid.uuid4().hex[:12]}")
    object: str = "chat.completion"
    created: int = field(default_factory=lambda: int(time.time()))
    model: str = DEFAULT_MODEL
    choices: list[CompletionChoice] = field(default_factory=list)
    usage: CompletionUsage = field(default_factory=CompletionUsage)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "object": self.object,
            "created": self.created,
            "model": self.model,
            "choices": [c.to_dict() for c in self.choices],
            "usage": self.usage.to_dict(),
        }


@dataclass
class ModelInfo:
    id: str
    object: str = "model"
    created: int = field(default_factory=lambda: int(time.time()))
    owned_by: str = "ollama"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "object": self.object,
            "created": self.created,
            "owned_by": self.owned_by,
        }


# ---------------------------------------------------------------------------
# Ollama Adapter
# ---------------------------------------------------------------------------

class OllamaAdapter:
    """
    Thread-safe adapter around the Ollama HTTP API.
    All public methods are synchronous; async variants are also provided.
    """

    def __init__(
        self,
        base_url: str = OLLAMA_BASE_URL,
        default_model: str = DEFAULT_MODEL,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._default_model = default_model
        self._timeout = timeout
        self._client = httpx.Client(
            base_url=self._base_url, timeout=self._timeout
        )
        self._async_client: Optional[httpx.AsyncClient] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        self._client.close()

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def is_healthy(self) -> bool:
        """Return True if the Ollama server is reachable."""
        try:
            resp = self._client.get("/", timeout=3.0)
            return resp.status_code == 200
        except Exception as exc:
            logger.warning("Ollama health check failed: %s", exc)
            return False

    async def is_healthy_async(self) -> bool:
        try:
            async with httpx.AsyncClient(base_url=self._base_url, timeout=3.0) as c:
                resp = await c.get("/")
                return resp.status_code == 200
        except Exception as exc:
            logger.warning("Ollama async health check failed: %s", exc)
            return False

    # ------------------------------------------------------------------
    # Model listing
    # ------------------------------------------------------------------

    def list_models(self) -> list[ModelInfo]:
        """Return installed models in OpenAI /v1/models format."""
        try:
            resp = self._client.get("/api/tags")
            resp.raise_for_status()
            data = resp.json()
            return [
                ModelInfo(id=m["name"])
                for m in data.get("models", [])
            ]
        except Exception as exc:
            logger.error("Failed to list Ollama models: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Chat completion – synchronous
    # ------------------------------------------------------------------

    def chat(
        self,
        messages: list[ChatMessage],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        stream: bool = False,
    ) -> ChatCompletion | Iterator[str]:
        """
        Send a chat request.  Returns a ChatCompletion for non-streaming,
        or an Iterator[str] of delta content strings for streaming.
        """
        model = model or self._default_model
        payload = {
            "model": model,
            "messages": [m.to_dict() for m in messages],
            "stream": stream,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        if stream:
            return self._stream_chat(payload, model)
        return self._blocking_chat(payload, model)

    def _blocking_chat(
        self, payload: dict[str, Any], model: str
    ) -> ChatCompletion:
        start = time.monotonic()
        try:
            resp = self._client.post("/api/chat", json=payload)
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error("Ollama HTTP error: %s", exc.response.text)
            raise
        except Exception as exc:
            logger.error("Ollama request failed: %s", exc)
            raise

        data = resp.json()
        duration_ms = int((time.monotonic() - start) * 1000)
        logger.debug("Ollama response in %d ms (model=%s)", duration_ms, model)

        msg_data = data.get("message", {})
        choice = CompletionChoice(
            index=0,
            message=ChatMessage(
                role=msg_data.get("role", "assistant"),
                content=msg_data.get("content", ""),
            ),
            finish_reason="stop" if data.get("done") else "length",
        )
        usage = CompletionUsage(
            prompt_tokens=data.get("prompt_eval_count", 0),
            completion_tokens=data.get("eval_count", 0),
        )
        return ChatCompletion(model=model, choices=[choice], usage=usage)

    def _stream_chat(
        self, payload: dict[str, Any], model: str
    ) -> Iterator[str]:
        try:
            with self._client.stream(
                "POST",
                "/api/chat",
                json=payload,
                timeout=DEFAULT_STREAM_TIMEOUT,
            ) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines():
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    delta = chunk.get("message", {}).get("content", "")
                    if delta:
                        yield delta
                    if chunk.get("done"):
                        break
        except Exception as exc:
            logger.error("Ollama stream error: %s", exc)
            raise

    # ------------------------------------------------------------------
    # Chat completion – async
    # ------------------------------------------------------------------

    async def chat_async(
        self,
        messages: list[ChatMessage],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        stream: bool = False,
    ) -> ChatCompletion | AsyncIterator[str]:
        model = model or self._default_model
        payload = {
            "model": model,
            "messages": [m.to_dict() for m in messages],
            "stream": stream,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        if stream:
            return self._async_stream_chat(payload, model)
        return await self._async_blocking_chat(payload, model)

    async def _async_blocking_chat(
        self, payload: dict[str, Any], model: str
    ) -> ChatCompletion:
        async with httpx.AsyncClient(
            base_url=self._base_url, timeout=self._timeout
        ) as client:
            start = time.monotonic()
            resp = await client.post("/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()
            duration_ms = int((time.monotonic() - start) * 1000)
            logger.debug("Async Ollama response in %d ms", duration_ms)

        msg_data = data.get("message", {})
        choice = CompletionChoice(
            index=0,
            message=ChatMessage(
                role=msg_data.get("role", "assistant"),
                content=msg_data.get("content", ""),
            ),
            finish_reason="stop" if data.get("done") else "length",
        )
        return ChatCompletion(
            model=model,
            choices=[choice],
            usage=CompletionUsage(
                prompt_tokens=data.get("prompt_eval_count", 0),
                completion_tokens=data.get("eval_count", 0),
            ),
        )

    async def _async_stream_chat(
        self, payload: dict[str, Any], model: str
    ) -> AsyncIterator[str]:
        async with httpx.AsyncClient(
            base_url=self._base_url, timeout=DEFAULT_STREAM_TIMEOUT
        ) as client:
            async with client.stream("POST", "/api/chat", json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    delta = chunk.get("message", {}).get("content", "")
                    if delta:
                        yield delta
                    if chunk.get("done"):
                        break

    # ------------------------------------------------------------------
    # Raw generate (for non-chat single-turn prompts)
    # ------------------------------------------------------------------

    def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.5,
        max_tokens: int = 512,
    ) -> str:
        """Single-turn generate; returns plain text response."""
        model = model or self._default_model
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        try:
            resp = self._client.post("/api/generate", json=payload)
            resp.raise_for_status()
            return resp.json().get("response", "").strip()
        except Exception as exc:
            logger.error("Ollama generate error: %s", exc)
            raise


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_adapter: Optional[OllamaAdapter] = None


def get_adapter() -> OllamaAdapter:
    """Return the module-level singleton adapter, creating it if needed."""
    global _adapter
    if _adapter is None:
        _adapter = OllamaAdapter()
    return _adapter
