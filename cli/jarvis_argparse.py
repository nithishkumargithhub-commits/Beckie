"""
JARVIS CLI – argparse + colorama interface.

Usage:
  python -m cli.jarvis_argparse chat
  python -m cli.jarvis_argparse ask "What time is it?"
  python -m cli.jarvis_argparse health
  python -m cli.jarvis_argparse audit [--limit N] [--type TYPE]
  python -m cli.jarvis_argparse models
  python -m cli.jarvis_argparse permissions [--revoke]
  python -m cli.jarvis_argparse db --init
  python -m cli.jarvis_argparse --version

The --color/--no-color flag controls ANSI output (auto-detected on Windows).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import textwrap
import time
import uuid
from pathlib import Path
from typing import Any, Optional

# Reconfigure stdout/stderr to UTF-8 on Windows consoles to prevent charmap errors
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ── colorama ──────────────────────────────────────────────────────────────────
try:
    import colorama
    from colorama import Back, Fore, Style
    colorama.init(autoreset=True)
    _COLOR = True
except ImportError:
    _COLOR = False
    # Minimal stubs so the rest of the file works without colorama
    class _Stub:
        def __getattr__(self, _: str) -> str:
            return ""
    Fore = _Stub()   # type: ignore
    Back = _Stub()   # type: ignore
    Style = _Stub()  # type: ignore

# ── project root on path ──────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logger = logging.getLogger("Jarvis.CLI")

# ---------------------------------------------------------------------------
# Colour helpers
# ---------------------------------------------------------------------------

def _c(text: str, *codes: str, enabled: bool = True) -> str:
    if not enabled or not _COLOR:
        return text
    return "".join(codes) + text + Style.RESET_ALL


def banner(session_id: str, color: bool = True) -> str:
    lines = [
        _c("  ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗", Fore.CYAN, Style.BRIGHT, enabled=color),
        _c("  ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝", Fore.CYAN, Style.BRIGHT, enabled=color),
        _c("  ██║███████║██████╔╝██║   ██║██║███████╗", Fore.CYAN, Style.BRIGHT, enabled=color),
        _c("  ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║", Fore.CYAN, Style.BRIGHT, enabled=color),
        _c("  ╚█████╔╝██║  ██║██║  ██║  ╚████╔╝ ██║███████║", Fore.CYAN, Style.BRIGHT, enabled=color),
        _c("   ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝   ╚═══╝  ╚═╝╚══════╝", Fore.CYAN, Style.BRIGHT, enabled=color),
        _c(f"  Privacy-first local AI  │  session: {session_id}", Fore.WHITE, Style.DIM, enabled=color),
    ]
    return "\n".join(lines) + "\n"


def _ok(msg: str, color: bool = True) -> str:
    return _c("✓ ", Fore.GREEN, Style.BRIGHT, enabled=color) + msg


def _err(msg: str, color: bool = True) -> str:
    return _c("✗ ", Fore.RED, Style.BRIGHT, enabled=color) + msg


def _warn(msg: str, color: bool = True) -> str:
    return _c("⚠ ", Fore.YELLOW, enabled=color) + msg


def _info(msg: str, color: bool = True) -> str:
    return _c("  → ", Fore.CYAN, enabled=color) + msg


def _label(text: str, color: bool = True) -> str:
    return _c(text, Fore.CYAN, Style.BRIGHT, enabled=color)


def _header(text: str, color: bool = True) -> str:
    line = "─" * max(len(text), 40)
    return f"\n{_label(text, color)}\n{line}"


def _dim(text: str, color: bool = True) -> str:
    return _c(text, Style.DIM, enabled=color)


def _tier_color(tier: str, text: str, color: bool = True) -> str:
    mapping = {
        "safe":        Fore.GREEN,
        "read":        Fore.CYAN,
        "write":       Fore.YELLOW,
        "destructive": Fore.RED,
    }
    return _c(text, mapping.get(tier.lower(), Fore.WHITE), enabled=color)


# ---------------------------------------------------------------------------
# Sub-command implementations
# ---------------------------------------------------------------------------

SESSION_ID = uuid.uuid4().hex[:12]
OLLAMA_URL = "http://127.0.0.1:11434"
DEFAULT_MODEL = "qwen3:8b"


def cmd_health(args: argparse.Namespace) -> int:
    """Check Ollama health and list installed models."""
    from core.ollama_adapter import OllamaAdapter

    c = args.color
    print(_label("JARVIS Health Check", c))
    print("─" * 40)

    adapter = OllamaAdapter(base_url=args.url)
    alive = adapter.is_healthy()

    if alive:
        print(_ok("Ollama is online", c))
        models = adapter.list_models()
        if models:
            print(_ok(f"{len(models)} model(s) available:", c))
            for m in models:
                print(_info(m.id, c))
        else:
            print(_warn("No models found. Run: ollama pull qwen3:8b", c))
        return 0
    else:
        print(_err(f"Ollama not reachable at {args.url}", c))
        print(_warn("Start it with:  ollama serve", c))
        return 1


def cmd_models(args: argparse.Namespace) -> int:
    """List all installed Ollama models."""
    from core.ollama_adapter import OllamaAdapter

    c = args.color
    adapter = OllamaAdapter(base_url=args.url)
    models = adapter.list_models()

    if not models:
        print(_warn("No models installed.", c))
        return 0

    print(_label("Installed Models", c))
    print(f"{'Model':<35} {'Owned By':<15}")
    print("─" * 52)
    for m in models:
        print(f"{_c(m.id, Fore.CYAN, enabled=c):<44} {m.owned_by}")
    return 0


def cmd_ask(args: argparse.Namespace) -> int:
    """Single-shot question/answer."""
    from core.ollama_adapter import ChatMessage, OllamaAdapter
    from core.challenge_prompt import ChallengePromptBuilder, PersonaConfig
    from core.permission_broker import PermissionBroker, PermissionTier

    c = args.color
    print(banner(SESSION_ID, c))

    adapter = OllamaAdapter(base_url=args.url, default_model=args.model)
    if not adapter.is_healthy():
        print(_err("Ollama not running. Start with: ollama serve", c))
        return 1

    builder = ChallengePromptBuilder(PersonaConfig(challenge_level=args.challenge))
    system_content = builder.build(session_id=SESSION_ID)

    messages = [
        ChatMessage(role="system", content=system_content),
        ChatMessage(role="user",   content=args.question),
    ]

    broker = PermissionBroker(session_id=SESSION_ID)
    broker.register_action("chat_completion", PermissionTier.READ)
    result = broker.request("chat_completion")
    if not result.granted:
        print(_err("Chat permission denied.", c))
        return 1

    print(f"{_label('You', c)}: {args.question}\n")

    print("─" * 60)
    start = time.monotonic()
    try:
        completion = adapter.chat(
            messages=messages,
            model=args.model,
            temperature=args.temperature,
        )
    except Exception as exc:
        print(_err(f"LLM error: {exc}", c))
        return 1

    elapsed = time.monotonic() - start
    answer = completion.choices[0].message.content if completion.choices else "(no response)"

    print(f"{_label('JARVIS', c)}:")
    # Word-wrap at 80 chars
    for line in answer.splitlines():
        print(textwrap.fill(line, width=80) if line else "")

    print("─" * 60)
    print(_dim(f"  {elapsed:.1f}s · {completion.usage.total_tokens} tokens · {args.model}", c))
    return 0


def cmd_chat(args: argparse.Namespace) -> int:
    """Interactive REPL session."""
    from core.ollama_adapter import ChatMessage, OllamaAdapter
    from core.challenge_prompt import ChallengePromptBuilder, PersonaConfig
    from core.permission_broker import PermissionBroker, PermissionTier

    c = args.color
    print(banner(SESSION_ID, c))

    adapter = OllamaAdapter(base_url=args.url, default_model=args.model)
    if not adapter.is_healthy():
        print(_err("Ollama not running. Start with: ollama serve", c))
        return 1

    builder = ChallengePromptBuilder(PersonaConfig(challenge_level=args.challenge))
    system_content = builder.build(session_id=SESSION_ID)

    history: list[ChatMessage] = [ChatMessage(role="system", content=system_content)]
    broker = PermissionBroker(session_id=SESSION_ID)
    broker.register_action("chat_completion", PermissionTier.READ)

    print(f"Model: {_c(args.model, Fore.CYAN, enabled=c)}  "
          f"Challenge: {_c(args.challenge, Fore.YELLOW, enabled=c)}  "
          f"Session: {_dim(SESSION_ID, c)}")
    print(_dim("Commands: /help, /audit, /perms, /clear, /quit", c))
    print("─" * 60)

    while True:
        try:
            raw = input(f"{_label('You', c)} > ")
        except (KeyboardInterrupt, EOFError):
            print(f"\n{_dim('Goodbye.', c)}")
            return 0

        user_input = raw.strip()
        if not user_input:
            continue

        # Slash commands
        if user_input.startswith("/"):
            rc = _handle_slash(user_input, broker, history, adapter, c)
            if rc == "quit":
                return 0
            continue

        history.append(ChatMessage(role="user", content=user_input))

        result = broker.request("chat_completion")
        if not result.granted:
            print(_err("Permission denied.", c))
            continue

        start = time.monotonic()
        try:
            if args.stream:
                _stream_print(adapter, history, args.model, args.temperature, c, history)
            else:
                _blocking_print(adapter, history, args.model, args.temperature, c, history)
        except Exception as exc:
            print(_err(f"Error: {exc}", c))

    return 0


def _stream_print(
    adapter: Any,
    messages: list[Any],
    model: str,
    temperature: float,
    color: bool,
    history: list[Any],
) -> None:
    from core.ollama_adapter import ChatMessage
    print(f"\n{_label('JARVIS', color)}:", end=" ", flush=True)
    collected = ""
    start = time.monotonic()
    try:
        for delta in adapter.chat(messages=messages, model=model,
                                   temperature=temperature, stream=True):
            print(delta, end="", flush=True)
            collected += delta
    except Exception:
        raise
    finally:
        elapsed = time.monotonic() - start
        print(f"\n{_dim(f'  {elapsed:.1f}s', color)}")
    history.append(ChatMessage(role="assistant", content=collected))


def _blocking_print(
    adapter: Any,
    messages: list[Any],
    model: str,
    temperature: float,
    color: bool,
    history: list[Any],
) -> None:
    from core.ollama_adapter import ChatMessage
    print(_dim("  thinking…", color), end="\r", flush=True)
    start = time.monotonic()
    completion = adapter.chat(messages=messages, model=model, temperature=temperature)
    elapsed = time.monotonic() - start

    answer = completion.choices[0].message.content if completion.choices else ""
    print(" " * 20 + "\r", end="")  # erase spinner
    print(f"\n{_label('JARVIS', color)}:")
    for line in answer.splitlines():
        print(textwrap.fill(line, width=80) if line else "")
    print(_dim(f"\n  {elapsed:.1f}s · {completion.usage.total_tokens} tokens", color))
    history.append(ChatMessage(role="assistant", content=answer))


def _handle_slash(
    cmd: str,
    broker: Any,
    history: list[Any],
    adapter: Any,
    color: bool,
) -> str:
    cmd_lower = cmd.lower()
    if cmd_lower == "/help":
        for name, desc in [
            ("/help",  "Show this help"),
            ("/audit", "Show last 10 audit records"),
            ("/perms", "Show current permission grants"),
            ("/clear", "Clear conversation history"),
            ("/models","List installed models"),
            ("/quit",  "Exit JARVIS"),
        ]:
            print(f"  {_c(name, Fore.CYAN, enabled=color):<30} {desc}")
    elif cmd_lower == "/audit":
        try:
            from core.audit_logger import get_audit_logger
            records = get_audit_logger().recent(10)
            if not records:
                print(_dim("  No audit records yet.", color))
            else:
                print(f"\n{'Timestamp':<21} {'Action':<22} {'Tier':<14} {'Status':<14} Approved")
                print("─" * 80)
                for r in records:
                    tier = r.get("tier") or "-"
                    status = r.get("status") or ""
                    ts = (r.get("timestamp") or "")[:19]
                    approved = "✓" if r.get("user_approved") else "○"
                    print(
                        f"{_dim(ts, color):<21} "
                        f"{r.get('action_name',''):<22} "
                        f"{_tier_color(tier, tier, color):<14} "
                        f"{status:<14} "
                        f"{approved}"
                    )
        except Exception as exc:
            print(_err(f"Audit error: {exc}", color))
    elif cmd_lower == "/perms":
        summary = broker.status_summary()
        print(json.dumps(summary, indent=2))
    elif cmd_lower == "/clear":
        from core.ollama_adapter import ChatMessage
        system = next((m for m in history if m.role == "system"), None)
        history.clear()
        if system:
            history.append(system)
        print(_ok("Conversation cleared.", color))
    elif cmd_lower == "/models":
        for m in adapter.list_models():
            print(_info(m.id, color))
    elif cmd_lower in ("/quit", "/exit", "/q"):
        return "quit"
    else:
        print(_warn(f"Unknown command: {cmd}  Type /help for options.", color))
    return "ok"


def cmd_audit(args: argparse.Namespace) -> int:
    """Display recent audit log records."""
    from core.audit_logger import get_audit_logger

    c = args.color
    al = get_audit_logger()
    records = al.recent(limit=args.limit)

    if args.type:
        records = [r for r in records if r.get("action_type") == args.type]

    if not records:
        print(_dim("No audit records found.", c))
        return 0

    print(f"\n{_label(f'Audit Log (last {len(records)} records)', c)}")
    print(f"{'ID':<6} {'Timestamp':<21} {'Type':<17} {'Action':<22} {'Tier':<14} {'Status':<14} App")
    print("─" * 98)
    for r in records:
        tier = r.get("tier") or "-"
        status = r.get("status") or ""
        ts = (r.get("timestamp") or "")[:19]
        approved = _c("✓", Fore.GREEN, enabled=c) if r.get("user_approved") else _dim("○", c)
        if status in ("approved", "auto_approved", "completed"):
            status_str = _c(status, Fore.GREEN, enabled=c)
        elif status in ("denied", "error"):
            status_str = _c(status, Fore.RED, enabled=c)
        else:
            status_str = status
        print(
            f"{str(r.get('id','')):<6} "
            f"{_dim(ts, c):<21} "
            f"{r.get('action_type',''):<17} "
            f"{r.get('action_name',''):<22} "
            f"{_tier_color(tier, tier, c):<14} "
            f"{status_str:<23} "
            f"{approved}"
        )
    return 0


def cmd_permissions(args: argparse.Namespace) -> int:
    """Show or revoke current session permissions."""
    from core.permission_broker import PermissionBroker

    c = args.color
    broker = PermissionBroker(session_id=SESSION_ID)

    if args.revoke:
        broker.revoke_session_permissions()
        print(_ok("All session permissions revoked.", c))
        return 0

    summary = broker.status_summary()
    print(_label("Session Permissions", c))
    print(json.dumps(summary, indent=2))
    print(_dim("\nNote: All WRITE permissions reset on every restart.", c))
    return 0


def cmd_db(args: argparse.Namespace) -> int:
    """Database management commands."""
    c = args.color

    if args.init:
        from db.schema import init_db, DB_PATH
        try:
            init_db()
            print(_ok(f"Database initialised at {DB_PATH}", c))
        except Exception as exc:
            print(_err(f"DB init failed: {exc}", c))
            return 1
        return 0

    if args.tables:
        from db.schema import get_db, DB_PATH
        try:
            with get_db() as conn:
                rows = conn.execute(
                    "SELECT name, type FROM sqlite_master "
                    "WHERE type IN ('table','view') ORDER BY name"
                ).fetchall()
            print(f"\n{_label('Database Tables', c)}")
            for r in rows:
                print(f"  {_c(r['name'], Fore.CYAN, enabled=c)}")
        except Exception as exc:
            print(_err(f"DB query failed: {exc}", c))
            return 1
        return 0

    print(_warn("Specify --init or --tables", c))
    return 1


def cmd_train_wakeword(args: argparse.Namespace) -> int:
    """Train custom 'Hey Beckie' wake word model."""
    print(_header("Training Custom Wake Word Model ('Hey Beckie')", args.color))
    from pipeline.train_wakeword import train_hey_beckie_model, measure_false_positive_rate
    output_path = getattr(args, "output", None) or "models/hey_beckie.onnx"
    onnx_file = train_hey_beckie_model(output_path=output_path)
    print(f"\n{_c('✓ Model exported:', Fore.GREEN, enabled=args.color)} {onnx_file}")
    if getattr(args, "eval_fpr", False):
        fpr = measure_false_positive_rate(onnx_file)
        print(f"{_c('✓ False Positive Rate:', Fore.CYAN, enabled=args.color)} {fpr:.2f}/hour")
    return 0


def cmd_voice(args: argparse.Namespace) -> int:
    """Run JARVIS Voice Pipeline."""
    print(_header("JARVIS Voice Assistant", args.color))
    from pipeline.voice_router import VoiceCommandRouter
    from pipeline.wake_word import WakeWordListener
    from pipeline.indicator import TrayListeningIndicator
    from pipeline.mic_permission import MicrophonePermissionManager
    from core.permission_broker import PermissionBroker
    from core.audit_logger import get_audit_logger

    session_id = uuid.uuid4().hex[:12]
    broker = PermissionBroker(session_id=session_id)
    audit = get_audit_logger(session_id=session_id)
    indicator = TrayListeningIndicator(headless=False)
    indicator.start()

    perm_mgr = MicrophonePermissionManager(permission_broker=broker, audit_logger=audit)
    router = VoiceCommandRouter(
        indicator=indicator,
        permission_broker=broker,
        permission_manager=perm_mgr,
        audit_logger=audit,
    )

    listener = WakeWordListener(
        on_wake_callback=lambda: router.handle_wake_event(),
        permission_manager=perm_mgr,
    )

    print(f"{_c('✓ Tray Indicator:', Fore.GREEN, enabled=args.color)} Running")
    print(f"{_c('✓ Wake Word:', Fore.GREEN, enabled=args.color)} 'Hey Beckie' / Ctrl+Alt+J")
    print(f"{_dim('Press Ctrl+C to stop.', args.color)}")

    listener.start()
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        listener.stop()
        indicator.stop()
        audit.flush()
        audit.stop()
        print(f"\n{_c('✓ Voice Assistant stopped.', Fore.YELLOW, enabled=args.color)}")
def cmd_brightness(args: argparse.Namespace) -> int:
    """Control and inspect screen brightness across monitors."""
    from actions.brightness import brightness_controller
    if getattr(args, "list", False):
        print(_header("Display Brightness – Connected Monitors", args.color))
        monitors = brightness_controller.list_monitors()
        for m in monitors:
            t = "External (DDC/CI)" if m["is_external"] else "Internal Panel"
            b = f"{m['brightness']}%" if m['brightness'] is not None else "Unknown"
            print(f"  [{m['index']}] {m['name']} ({t}) – Brightness: {b}")
        return 0
    elif getattr(args, "level", None) is not None:
        lvl = args.level
        disp = getattr(args, "display", None)
        success, msg = brightness_controller.set_brightness(lvl, display=disp)
        if success:
            print(_ok(msg, args.color))
            return 0
        else:
            print(_err(msg, args.color))
            return 1
    else:
        b = brightness_controller.get_brightness(getattr(args, "display", None))
        print(f"Current brightness: {b}%")
        return 0


def cmd_volume(args: argparse.Namespace) -> int:
    """Control and inspect master audio volume and mute."""
    from actions.volume import volume_controller
    if getattr(args, "mute", False):
        success, msg = volume_controller.mute()
        print(_ok(msg, args.color) if success else _err(msg, args.color))
        return 0 if success else 1
    elif getattr(args, "unmute", False):
        success, msg = volume_controller.unmute()
        print(_ok(msg, args.color) if success else _err(msg, args.color))
        return 0 if success else 1
    elif getattr(args, "level", None) is not None:
        success, msg = volume_controller.set_volume(args.level)
        print(_ok(msg, args.color) if success else _err(msg, args.color))
        return 0 if success else 1
    else:
        vol = volume_controller.get_volume()
        muted = volume_controller.is_muted()
        status_str = f"Master Volume: {vol}%" + (" (MUTED)" if muted else "")
        print(_ok(status_str, args.color))
        return 0


def cmd_file_ops(args: argparse.Namespace) -> int:
    """Safe file operations and approved application launcher."""
    from actions.file_ops import file_ops
    if getattr(args, "launch", None):
        success, msg = file_ops.launch_approved_app(args.launch)
        print(_ok(msg, args.color) if success else _err(msg, args.color))
        return 0 if success else 1
    elif getattr(args, "search", None):
        results = file_ops.search_folders(args.search)
        print(_header(f"File Search Results for '{args.search}'", args.color))
        if not results:
            print("  No matching files found.")
        for r in results:
            print(f"  • {r['name']} ({r['size_formatted']}) → {r['path']}")
        return 0
    elif getattr(args, "metadata", None):
        meta = file_ops.show_metadata(args.metadata, compute_hash=True)
        print(_header(f"File Metadata: {meta['name']}", args.color))
        for k, v in meta.items():
            print(f"  {k:15}: {v}")
        return 0
    elif getattr(args, "list_apps", False):
        apps = file_ops.list_approved_apps()
        print(_header("Approved Applications Whitelist", args.color))
        for a in apps:
            print(f"  • {a['name']:15} ({a['command']}) – {a['description']}")
        return 0
    else:
        print("Please specify --launch, --search, --metadata, or --list-apps.")
        return 1


def cmd_recycle_bin(args: argparse.Namespace) -> int:
    """Safely move a file or folder to the Windows Recycle Bin."""
    from actions.recycle_bin import recycle_bin
    success, msg, impact = recycle_bin.move_to_recycle_bin(args.path)
    if impact:
        print(_dim(impact.summary, args.color))
    print(_ok(msg, args.color) if success else _err(msg, args.color))
    return 0 if success else 1


def cmd_startup(args: argparse.Namespace) -> int:
    """Manage automatic startup at Windows logon via Task Scheduler."""
    from actions.startup_manager import startup_manager
    if getattr(args, "enable", False):
        success, msg = startup_manager.enable_startup()
        print(_ok(msg, args.color) if success else _err(msg, args.color))
        return 0 if success else 1
    elif getattr(args, "disable", False):
        success, msg = startup_manager.disable_startup()
        print(_ok(msg, args.color) if success else _err(msg, args.color))
        return 0 if success else 1
    else:
        status = startup_manager.get_startup_status()
        state = "ENABLED" if status["enabled"] else "DISABLED (Default)"
        color_fn = Fore.GREEN if status["enabled"] else Fore.YELLOW
        print(f"Windows Startup: {_c(state, color_fn, enabled=args.color)}")
        print(f"  Task Name: {status['task_name']}")
        print(f"  Schedule : {status['schedule']}")
        return 0


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="jarvis-cli",
        description="JARVIS – Privacy-first personal AI assistant",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
            Examples:
              jarvis-cli health
              jarvis-cli ask "What is the capital of France?"
              jarvis-cli chat --stream --challenge assertive
              jarvis-cli audit --limit 20 --type file_op
              jarvis-cli db --init
              jarvis-cli train-wakeword
              jarvis-cli voice
        """),
    )
    parser.add_argument("--version", action="version", version="JARVIS 1.0.0")
    parser.add_argument(
        "--color", dest="color", action="store_true", default=True,
        help="Enable colour output (default: on)",
    )
    parser.add_argument(
        "--no-color", dest="color", action="store_false",
        help="Disable colour output",
    )
    parser.add_argument(
        "--url", default=OLLAMA_URL,
        help=f"Ollama base URL (default: {OLLAMA_URL})",
    )
    parser.add_argument(
        "--log-level", default="WARNING",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Python log level (default: WARNING)",
    )

    sub = parser.add_subparsers(dest="command", metavar="COMMAND")

    # ── health ────────────────────────────────────────────────────────
    sub.add_parser("health", help="Check Ollama server health")

    # ── models ────────────────────────────────────────────────────────
    sub.add_parser("models", help="List installed Ollama models")

    # ── ask ───────────────────────────────────────────────────────────
    p_ask = sub.add_parser("ask", help="Single-shot question")
    p_ask.add_argument("question", help="Question to ask JARVIS")
    p_ask.add_argument("--model", default=DEFAULT_MODEL)
    p_ask.add_argument("--temperature", type=float, default=0.7)
    p_ask.add_argument(
        "--challenge", default="balanced",
        choices=["minimal", "balanced", "assertive"],
    )

    # ── chat ──────────────────────────────────────────────────────────
    p_chat = sub.add_parser("chat", help="Interactive REPL")
    p_chat.add_argument("--model", default=DEFAULT_MODEL)
    p_chat.add_argument("--temperature", type=float, default=0.7)
    p_chat.add_argument(
        "--challenge", default="balanced",
        choices=["minimal", "balanced", "assertive"],
    )
    p_chat.add_argument(
        "--stream", action="store_true", default=True,
        help="Stream responses (default: on)",
    )
    p_chat.add_argument("--no-stream", dest="stream", action="store_false")

    # ── audit ─────────────────────────────────────────────────────────
    p_audit = sub.add_parser("audit", help="Show audit log")
    p_audit.add_argument("--limit", "-n", type=int, default=20,
                         help="Number of records (default: 20)")
    p_audit.add_argument("--type", "-t", dest="type", default=None,
                         help="Filter by action_type")

    # ── permissions ───────────────────────────────────────────────────
    p_perms = sub.add_parser("permissions", help="Manage session permissions")
    p_perms.add_argument("--revoke", action="store_true",
                         help="Revoke all in-memory WRITE grants")

    # ── db ────────────────────────────────────────────────────────────
    p_db = sub.add_parser("db", help="Database management")
    p_db.add_argument("--init", action="store_true", help="Initialise the database")
    p_db.add_argument("--tables", action="store_true", help="List all tables")

    # ── train-wakeword ────────────────────────────────────────────────
    p_tw = sub.add_parser("train-wakeword", help="Train custom 'Hey Beckie' wake word ONNX model")
    p_tw.add_argument("--output", default="models/hey_beckie.onnx", help="Path to output ONNX file")
    p_tw.add_argument("--eval-fpr", action="store_true", help="Evaluate false positive rate")

    # ── voice ─────────────────────────────────────────────────────────
    sub.add_parser("voice", help="Run JARVIS voice assistant pipeline")

    # ── brightness ────────────────────────────────────────────────────
    p_bright = sub.add_parser("brightness", help="Manage display brightness across monitors")
    p_bright.add_argument("--level", "-l", type=int, help="Brightness level (0-100)")
    p_bright.add_argument("--display", "-d", help="Display index or name")
    p_bright.add_argument("--list", action="store_true", help="List connected monitors")

    # ── volume ────────────────────────────────────────────────────────
    p_vol = sub.add_parser("volume", help="Manage master audio volume and mute")
    p_vol.add_argument("--level", "-l", type=int, help="Volume level (0-100)")
    p_vol.add_argument("--mute", action="store_true", help="Mute master audio")
    p_vol.add_argument("--unmute", action="store_true", help="Unmute master audio")

    # ── file-ops ──────────────────────────────────────────────────────
    p_fops = sub.add_parser("file-ops", help="Approved apps and file operations")
    p_fops.add_argument("--launch", help="Launch approved application")
    p_fops.add_argument("--search", help="Search user folders for matching files")
    p_fops.add_argument("--metadata", help="Show file/directory metadata")
    p_fops.add_argument("--list-apps", action="store_true", help="List approved applications")

    # ── recycle-bin ───────────────────────────────────────────────────
    p_rb = sub.add_parser("recycle-bin", help="Safely move item to Windows Recycle Bin")
    p_rb.add_argument("path", help="Path to file or folder to delete")

    # ── startup ───────────────────────────────────────────────────────
    p_su = sub.add_parser("startup", help="Configure Windows startup via Task Scheduler")
    p_su.add_argument("--enable", action="store_true", help="Enable startup at user logon")
    p_su.add_argument("--disable", action="store_true", help="Disable startup task")
    p_su.add_argument("--status", action="store_true", help="Show startup status")

    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

_COMMANDS: dict[str, Any] = {
    "health":         cmd_health,
    "models":         cmd_models,
    "ask":            cmd_ask,
    "chat":           cmd_chat,
    "audit":          cmd_audit,
    "permissions":    cmd_permissions,
    "db":             cmd_db,
    "train-wakeword": cmd_train_wakeword,
    "voice":          cmd_voice,
    "brightness":     cmd_brightness,
    "volume":         cmd_volume,
    "file-ops":       cmd_file_ops,
    "recycle-bin":    cmd_recycle_bin,
    "startup":        cmd_startup,
}


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level, logging.WARNING),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if args.command is None:
        parser.print_help()
        return 0

    handler = _COMMANDS.get(args.command)
    if handler is None:
        print(_err(f"Unknown command: {args.command}", args.color))
        return 1

    try:
        return handler(args)
    except KeyboardInterrupt:
        print(f"\n{_dim('Interrupted.', args.color)}")
        return 130


if __name__ == "__main__":
    sys.exit(main())
