"""
JARVIS CLI – jarvis-cli.py

A rich, color-coded terminal interface for JARVIS.
Supports: chat, ask (single-shot), health, audit, permissions, models.

Usage:
  python -m cli.jarvis_cli chat
  python -m cli.jarvis_cli ask "What is the weather?"
  python -m cli.jarvis_cli health
  python -m cli.jarvis_cli audit --limit 20
  python -m cli.jarvis_cli models
  python -m cli.jarvis_cli permissions
"""

from __future__ import annotations

import json
import sys
import time
import uuid
from pathlib import Path
from typing import Optional

# Reconfigure stdout/stderr to UTF-8 on Windows consoles to prevent charmap errors
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Rich + Typer
import typer
from rich import print as rprint
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.rule import Rule
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

# JARVIS internals
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.challenge_prompt import ChallengePromptBuilder, PersonaConfig
from core.ollama_adapter import ChatMessage, OllamaAdapter
from core.permission_broker import PermissionBroker, PermissionTier

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

JARVIS_THEME = Theme({
    "jarvis":   "bold cyan",
    "user":     "bold green",
    "system":   "bold yellow",
    "error":    "bold red",
    "warn":     "yellow",
    "success":  "bold green",
    "tier.safe":        "dim green",
    "tier.read":        "cyan",
    "tier.write":       "yellow",
    "tier.destructive": "bold red",
})

console = Console(theme=JARVIS_THEME, highlight=True)
app = typer.Typer(
    name="jarvis-cli",
    help="JARVIS – Privacy-first personal AI assistant CLI",
    rich_markup_mode="rich",
    no_args_is_help=True,
)

OLLAMA_URL = "http://127.0.0.1:11434"
DEFAULT_MODEL = "qwen3:8b"
SESSION_ID = uuid.uuid4().hex[:12]


# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------

def _print_banner() -> None:
    banner = (
        "\n"
        "  [jarvis]     ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗[/jarvis]\n"
        "  [jarvis]     ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝[/jarvis]\n"
        "  [jarvis]     ██║███████║██████╔╝██║   ██║██║███████╗[/jarvis]\n"
        "  [jarvis]██   ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║[/jarvis]\n"
        "  [jarvis]╚█████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████║[/jarvis]\n"
        "  [jarvis] ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝[/jarvis]\n"
        f"  [dim]Privacy-first local AI assistant  │  session: {SESSION_ID}[/dim]\n"
    )
    console.print(banner)


def _tier_style(tier: str) -> str:
    return {
        "safe": "tier.safe",
        "read": "tier.read",
        "write": "tier.write",
        "destructive": "tier.destructive",
    }.get(tier.lower(), "white")


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_adapter() -> OllamaAdapter:
    return OllamaAdapter(base_url=OLLAMA_URL, default_model=DEFAULT_MODEL)


def _make_broker() -> PermissionBroker:
    return PermissionBroker(session_id=SESSION_ID)


def _make_prompt_builder() -> ChallengePromptBuilder:
    return ChallengePromptBuilder(PersonaConfig(challenge_level="balanced"))


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

@app.command()
def health(
    url: str = typer.Option(OLLAMA_URL, "--url", "-u", help="Ollama base URL"),
) -> None:
    """Check if the JARVIS backend and Ollama are running."""
    console.print(Rule("[jarvis]JARVIS Health Check[/jarvis]"))
    adapter = OllamaAdapter(base_url=url)

    with console.status("[jarvis]Pinging Ollama...[/jarvis]"):
        alive = adapter.is_healthy()

    if alive:
        console.print("[success]✓ Ollama is online[/success]")
        models = adapter.list_models()
        if models:
            console.print(f"[success]✓ {len(models)} model(s) available:[/success]")
            for m in models:
                console.print(f"   • [jarvis]{m.id}[/jarvis]")
        else:
            console.print("[warn]⚠ No models found. Run: ollama pull qwen3:8b[/warn]")
    else:
        console.print("[error]✗ Ollama is not reachable at {url}[/error]")
        console.print("[warn]  Start it with: ollama serve[/warn]")
        raise typer.Exit(code=1)


@app.command()
def models(
    url: str = typer.Option(OLLAMA_URL, "--url", "-u", help="Ollama base URL"),
) -> None:
    """List installed Ollama models."""
    adapter = OllamaAdapter(base_url=url)
    model_list = adapter.list_models()

    if not model_list:
        console.print("[warn]No models installed.[/warn]")
        raise typer.Exit(code=0)

    table = Table(title="Available Models", show_header=True, header_style="bold jarvis")
    table.add_column("Model ID", style="jarvis")
    table.add_column("Owned By")
    for m in model_list:
        table.add_row(m.id, m.owned_by)
    console.print(table)


@app.command()
def ask(
    question: str = typer.Argument(..., help="Single-shot question to ask JARVIS"),
    model: str = typer.Option(DEFAULT_MODEL, "--model", "-m"),
    temperature: float = typer.Option(0.7, "--temp", "-t"),
    challenge: str = typer.Option("balanced", "--challenge", "-c",
                                   help="Challenge level: minimal | balanced | assertive"),
) -> None:
    """Ask JARVIS a single question and print the answer."""
    _print_banner()
    adapter = _make_adapter()
    broker = _make_broker()
    builder = ChallengePromptBuilder(PersonaConfig(challenge_level=challenge))

    system_prompt = builder.build(session_id=SESSION_ID)
    messages = [
        ChatMessage(role="system", content=system_prompt),
        ChatMessage(role="user",   content=question),
    ]

    # Permission check (READ tier for a query)
    broker.register_action("chat_completion", PermissionTier.READ)
    result = broker.request("chat_completion", details={"question": question[:80]})
    if not result.granted:
        console.print("[error]Permission denied.[/error]")
        raise typer.Exit(code=1)

    console.print(f"[user]You:[/user] {question}\n")

    with console.status("[jarvis]Thinking...[/jarvis]"):
        start = time.monotonic()
        try:
            completion = adapter.chat(messages=messages, model=model, temperature=temperature)
        except Exception as exc:
            console.print(f"[error]LLM error: {exc}[/error]")
            raise typer.Exit(code=1)
        elapsed = time.monotonic() - start

    answer = completion.choices[0].message.content if completion.choices else ""
    console.print(Panel(
        Markdown(answer),
        title="[jarvis]JARVIS[/jarvis]",
        border_style="cyan",
        subtitle=f"[dim]{elapsed:.1f}s · {completion.usage.total_tokens} tokens · {model}[/dim]",
    ))


@app.command()
def chat(
    model: str = typer.Option(DEFAULT_MODEL, "--model", "-m"),
    temperature: float = typer.Option(0.7, "--temp", "-t"),
    challenge: str = typer.Option("balanced", "--challenge", "-c"),
    stream: bool = typer.Option(True, "--stream/--no-stream"),
) -> None:
    """Start an interactive REPL session with JARVIS."""
    _print_banner()
    adapter = _make_adapter()
    broker = _make_broker()
    builder = ChallengePromptBuilder(PersonaConfig(challenge_level=challenge))

    # Verify Ollama is alive before entering REPL
    if not adapter.is_healthy():
        console.print("[error]✗ Ollama is not running. Start it with: ollama serve[/error]")
        raise typer.Exit(code=1)

    system_prompt = builder.build(session_id=SESSION_ID)
    history: list[ChatMessage] = [ChatMessage(role="system", content=system_prompt)]

    console.print(
        Panel(
            f"Model: [jarvis]{model}[/jarvis]  │  "
            f"Challenge: [warn]{challenge}[/warn]  │  "
            f"Session: [dim]{SESSION_ID}[/dim]\n"
            "[dim]Type /help, /audit, /perms, /clear, or /quit[/dim]",
            title="[jarvis]JARVIS Chat[/jarvis]",
            border_style="cyan",
        )
    )

    broker.register_action("chat_completion", PermissionTier.READ)

    while True:
        try:
            user_input = Prompt.ask("[user]You[/user]")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Goodbye.[/dim]")
            break

        if not user_input.strip():
            continue

        # Slash commands
        if user_input.startswith("/"):
            _handle_slash(user_input.strip(), broker, history, adapter)
            continue

        # Normal chat
        history.append(ChatMessage(role="user", content=user_input))

        result = broker.request("chat_completion")
        if not result.granted:
            console.print("[error]Chat request denied.[/error]")
            continue

        if stream:
            _stream_response(adapter, history, model, temperature, history)
        else:
            _blocking_response(adapter, history, model, temperature, history)


def _stream_response(
    adapter: OllamaAdapter,
    messages: list[ChatMessage],
    model: str,
    temperature: float,
    history: list[ChatMessage],
) -> None:
    """Stream response with live update panel."""
    console.print(Rule(style="dim cyan"))
    collected = ""
    start = time.monotonic()
    try:
        gen = adapter.chat(messages=messages, model=model,
                           temperature=temperature, stream=True)
        with Live(console=console, refresh_per_second=12) as live:
            for delta in gen:
                collected += delta
                live.update(Panel(
                    Markdown(collected),
                    title="[jarvis]JARVIS[/jarvis]",
                    border_style="cyan",
                ))
    except Exception as exc:
        console.print(f"[error]Stream error: {exc}[/error]")
        return

    elapsed = time.monotonic() - start
    console.print(f"[dim]  {elapsed:.1f}s[/dim]")
    history.append(ChatMessage(role="assistant", content=collected))


def _blocking_response(
    adapter: OllamaAdapter,
    messages: list[ChatMessage],
    model: str,
    temperature: float,
    history: list[ChatMessage],
) -> None:
    with console.status("[jarvis]Thinking...[/jarvis]"):
        start = time.monotonic()
        try:
            completion = adapter.chat(messages=messages, model=model, temperature=temperature)
        except Exception as exc:
            console.print(f"[error]LLM error: {exc}[/error]")
            return
        elapsed = time.monotonic() - start

    answer = completion.choices[0].message.content if completion.choices else ""
    console.print(Panel(
        Markdown(answer),
        title="[jarvis]JARVIS[/jarvis]",
        border_style="cyan",
        subtitle=f"[dim]{elapsed:.1f}s · {completion.usage.total_tokens} tokens[/dim]",
    ))
    history.append(ChatMessage(role="assistant", content=answer))


def _handle_slash(cmd: str, broker: PermissionBroker,
                  history: list[ChatMessage], adapter: OllamaAdapter) -> None:
    cmd_lower = cmd.lower()

    if cmd_lower == "/help":
        table = Table(show_header=False, box=None)
        for c, desc in [
            ("/help",    "Show this help"),
            ("/audit",   "Show last 10 audit records"),
            ("/perms",   "Show current session permissions"),
            ("/clear",   "Clear conversation history"),
            ("/models",  "List installed models"),
            ("/quit",    "Exit"),
        ]:
            table.add_row(f"[jarvis]{c}[/jarvis]", desc)
        console.print(table)

    elif cmd_lower == "/audit":
        from core.audit_logger import get_audit_logger
        logs = get_audit_logger().recent(limit=10)
        if not logs:
            console.print("[dim]No audit records yet.[/dim]")
            return
        table = Table(title="Recent Audit Log", show_header=True, header_style="bold")
        table.add_column("Timestamp", style="dim", width=22)
        table.add_column("Action")
        table.add_column("Tier")
        table.add_column("Status")
        table.add_column("Approved", justify="center")
        for r in logs:
            tier_str = r.get("tier") or ""
            table.add_row(
                r.get("timestamp", "")[:19],
                r.get("action_name", ""),
                Text(tier_str, style=_tier_style(tier_str)),
                r.get("status", ""),
                "✓" if r.get("user_approved") else "○",
            )
        console.print(table)

    elif cmd_lower == "/perms":
        summary = broker.status_summary()
        console.print(Panel(
            json.dumps(summary, indent=2),
            title="[jarvis]Permission Status[/jarvis]",
            border_style="yellow",
        ))

    elif cmd_lower == "/clear":
        # Keep only the system prompt
        system = next((m for m in history if m.role == "system"), None)
        history.clear()
        if system:
            history.append(system)
        console.print("[success]✓ Conversation cleared[/success]")

    elif cmd_lower == "/models":
        model_list = adapter.list_models()
        for m in model_list:
            console.print(f"  • [jarvis]{m.id}[/jarvis]")

    elif cmd_lower in ("/quit", "/exit", "/q"):
        console.print("[dim]Goodbye.[/dim]")
        raise typer.Exit()

    else:
        console.print(f"[warn]Unknown command: {cmd}[/warn]  Type /help for options.")


@app.command()
def audit(
    limit: int = typer.Option(20, "--limit", "-n", help="Number of records to show"),
    action_type: Optional[str] = typer.Option(None, "--type", "-t"),
) -> None:
    """Display recent audit log entries from the local database."""
    from core.audit_logger import get_audit_logger
    al = get_audit_logger()
    records = al.recent(limit=limit)

    if action_type:
        records = [r for r in records if r.get("action_type") == action_type]

    if not records:
        console.print("[dim]No audit records found.[/dim]")
        return

    table = Table(
        title=f"Audit Log (last {len(records)} records)",
        show_header=True, header_style="bold cyan",
    )
    table.add_column("ID",        style="dim",    width=6)
    table.add_column("Timestamp", style="dim",    width=21)
    table.add_column("Type",      width=16)
    table.add_column("Action",    width=20)
    table.add_column("Tier",      width=12)
    table.add_column("Status",    width=14)
    table.add_column("Approved",  justify="center", width=9)

    for r in records:
        tier_str = r.get("tier") or "-"
        status   = r.get("status") or ""
        status_style = (
            "success" if status in ("approved", "auto_approved", "completed")
            else ("error" if status in ("denied", "error") else "white")
        )
        table.add_row(
            str(r.get("id", "")),
            (r.get("timestamp") or "")[:19],
            r.get("action_type", ""),
            r.get("action_name", ""),
            Text(tier_str, style=_tier_style(tier_str)),
            Text(status, style=status_style),
            "[success]✓[/success]" if r.get("user_approved") else "[dim]○[/dim]",
        )
    console.print(table)


@app.command()
def permissions() -> None:
    """Show the current session's permission grants."""
    broker = _make_broker()
    summary = broker.status_summary()
    console.print(Panel(
        json.dumps(summary, indent=2),
        title="[jarvis]JARVIS Permissions[/jarvis]",
        border_style="yellow",
    ))
    console.print(
        "[dim]Note: All WRITE permissions are reset on each restart by design.[/dim]"
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app()
