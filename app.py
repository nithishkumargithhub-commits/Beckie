"""
JARVIS – Application entry point (Phase 1).

Boots the FastAPI server with the Ollama adapter, permission broker,
audit logger, and challenge-mode prompt builder all wired together.
"""

from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.ollama_router import router as ollama_router
from core.audit_logger import AuditLogger
from core.challenge_prompt import ChallengePromptBuilder, PersonaConfig
from core.ollama_adapter import OllamaAdapter
from core.permission_broker import PermissionBroker
from db.schema import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("Jarvis.App")

SESSION_ID = uuid.uuid4().hex[:12]


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise all services on startup; clean up on shutdown."""
    logger.info("━━━ JARVIS starting (session=%s) ━━━", SESSION_ID)

    # Database
    init_db()
    logger.info("✓ Database ready")

    # Audit logger
    audit = AuditLogger(session_id=SESSION_ID)
    app.state.audit_logger = audit
    audit.log_system("startup", details={"session_id": SESSION_ID})
    logger.info("✓ Audit logger ready")

    # Ollama adapter
    adapter = OllamaAdapter()
    if await adapter.is_healthy_async():
        models = adapter.list_models()
        logger.info("✓ Ollama online (%d models)", len(models))
    else:
        logger.warning("⚠ Ollama not reachable – chat endpoints will be degraded")
    app.state.ollama_adapter = adapter

    # Permission broker
    broker = PermissionBroker(
        session_id=SESSION_ID,
        audit_callback=lambda result, extra: audit.log_permission(
            action_name=result.action_name,
            tier=result.tier.value,
            granted=result.granted,
            user_approved=result.user_approved,
            resource=extra.get("resource"),
        ),
    )
    app.state.permission_broker = broker
    logger.info("✓ Permission broker ready (all WRITE permissions reset)")

    # Challenge prompt builder
    app.state.prompt_builder = ChallengePromptBuilder(
        PersonaConfig(challenge_level="balanced")
    )
    logger.info("✓ Challenge-mode prompt builder ready")

    yield

    # ── Shutdown ──────────────────────────────────────────────────────
    audit.log_system("shutdown", details={"session_id": SESSION_ID})
    broker.revoke_session_permissions()
    audit.flush(timeout=5.0)
    audit.stop()
    adapter.close()
    logger.info("━━━ JARVIS stopped ━━━")


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app() -> FastAPI:
    app = FastAPI(
        title="JARVIS API",
        description=(
            "Privacy-first personal AI assistant.\n\n"
            "OpenAI-compatible endpoints backed by Ollama + Qwen3 8B (local)."
        ),
        version="1.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(ollama_router)

    @app.get("/")
    async def root():
        return {
            "service": "JARVIS",
            "version": "1.0.0",
            "session_id": SESSION_ID,
            "docs": "/docs",
        }

    return app


app = create_app()


# ---------------------------------------------------------------------------
# CLI runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host="127.0.0.1",
        port=8765,
        reload=False,
        log_level="info",
    )
