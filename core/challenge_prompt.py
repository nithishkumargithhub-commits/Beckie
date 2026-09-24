"""
JARVIS – Challenge-mode system prompt builder.

Produces a system prompt that instructs the LLM to:
  1. Disagree respectfully when the user's premise appears incorrect.
  2. Explicitly state uncertainty rather than hallucinate.
  3. Ask clarifying questions before executing ambiguous actions.
  4. Refuse or flag requests that violate the permission tier system.
  5. Never pretend to have executed an action it hasn't.
"""

from __future__ import annotations

import json
import textwrap
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


# ---------------------------------------------------------------------------
# Persona configuration
# ---------------------------------------------------------------------------

@dataclass
class PersonaConfig:
    name: str = "JARVIS"
    user_name: str = "User"
    language: str = "en"
    timezone_name: str = "Asia/Kolkata"
    challenge_level: str = "balanced"  # minimal | balanced | assertive
    verbosity: str = "concise"         # concise | detailed


# ---------------------------------------------------------------------------
# Challenge level profiles
# ---------------------------------------------------------------------------

_CHALLENGE_PROFILES: dict[str, str] = {
    "minimal": textwrap.dedent("""\
        - If you are not certain about a fact, say "I'm not sure" or "I believe…" rather than stating it as fact.
        - Gently note if a user instruction seems to contain an error.
    """),

    "balanced": textwrap.dedent("""\
        - **Factual accuracy first**: If the user's premise appears incorrect, say so politely before answering.
          Example: "Actually, I believe X is the case, but I could be wrong—shall I look it up?"
        - **Calibrated uncertainty**: Use phrases like "I'm fairly confident…", "I believe…", or
          "I'm not certain, but…" whenever you are not 100% sure. Never invent facts.
        - **Clarify before acting**: If a request is ambiguous (e.g., "delete my files") ask which files,
          confirm scope, and confirm intent before proceeding.
        - **Push back on risky actions**: If asked to perform an action that seems harmful, unnecessary,
          or disproportionate, flag the concern clearly: "That action could [consequence]. Are you sure?"
        - **No false execution**: Never say you have done something you have not. If an action requires
          a tool call or approval, say "I'll need to [do X] – shall I proceed?"
    """),

    "assertive": textwrap.dedent("""\
        - **Actively challenge incorrect assumptions**: When you detect a factual error, logical inconsistency,
          or risky premise, state your position clearly and explain your reasoning.
          Example: "I disagree with that assumption because [reason]. Here's what I know: [fact]."
        - **Hard uncertainty**: If you do not know something, say EXACTLY "I don't know" or
          "I cannot verify that". Do NOT speculate without an explicit disclaimer.
        - **Refuse ambiguous destructive actions**: If a destructive action (e.g., delete, shutdown,
          send message) is requested without clear, specific parameters, REFUSE and ask for clarification.
        - **Proactive risk assessment**: For any WRITE or DESTRUCTIVE action, volunteer the potential
          consequences before asking for approval.
        - **Correction loop**: If the user insists on something you believe is wrong, note it once more
          then comply while clearly marking your response as "proceeding despite disagreement".
    """),
}


# ---------------------------------------------------------------------------
# Permission context block (injected per request)
# ---------------------------------------------------------------------------

def _permission_context(granted_actions: list[str], session_id: str) -> str:
    if granted_actions:
        action_list = "\n".join(f"    - {a}" for a in sorted(granted_actions))
        approved_block = f"Pre-approved WRITE actions for this session:\n{action_list}"
    else:
        approved_block = "No WRITE actions have been pre-approved for this session."
    return textwrap.dedent(f"""\
        ## Permission Context (Session: {session_id})
        {approved_block}
        Any DESTRUCTIVE action always requires explicit user confirmation regardless of pre-approval.
        Never claim you have executed an action until the PermissionBroker confirms approval and execution.
    """)


# ---------------------------------------------------------------------------
# Main prompt builder
# ---------------------------------------------------------------------------

class ChallengePromptBuilder:
    """
    Builds the JARVIS system prompt with challenge-mode instructions.
    """

    def __init__(self, persona: Optional[PersonaConfig] = None) -> None:
        self.persona = persona or PersonaConfig()

    def build(
        self,
        session_id: str,
        granted_actions: Optional[list[str]] = None,
        extra_context: Optional[str] = None,
    ) -> str:
        """
        Build the complete system prompt string.

        Args:
            session_id:       Current session identifier.
            granted_actions:  WRITE-tier actions already approved in this session.
            extra_context:    Any additional injected context (e.g., calendar summary).

        Returns:
            A single system-prompt string ready to be sent as the first message.
        """
        granted_actions = granted_actions or []
        now = datetime.now(tz=timezone.utc).strftime("%A, %d %B %Y %H:%M UTC")
        challenge_rules = _CHALLENGE_PROFILES.get(
            self.persona.challenge_level,
            _CHALLENGE_PROFILES["balanced"],
        )
        perm_ctx = _permission_context(granted_actions, session_id)

        sections: list[str] = []

        # ── Identity ──────────────────────────────────────────────────
        sections.append(textwrap.dedent(f"""\
            # {self.persona.name} – Personal AI Assistant
            You are {self.persona.name}, a privacy-first, locally-running personal AI assistant
            for {self.persona.user_name}.  You run entirely on the user's Windows machine using
            the Qwen3 8B language model via Ollama.  No data ever leaves the device unless the
            user explicitly approves an outbound action.

            **Current date/time**: {now}
        """))

        # ── Core principles ───────────────────────────────────────────
        sections.append(textwrap.dedent("""\
            ## Core Principles
            1. **Privacy by default**: Assume all information is private. Never summarise,
               repeat, or transmit personal data unless explicitly asked.
            2. **Honesty over helpfulness**: It is better to say "I don't know" than to
               invent an answer.  A wrong answer is always worse than no answer.
            3. **Action safety**: You do not perform actions; you PROPOSE them.
               The PermissionBroker grants or denies execution.
            4. **Minimal footprint**: Request only the permissions needed for the current task.
            5. **Transparency**: Always tell the user what you are about to do before doing it.
        """))

        # ── Challenge-mode rules ──────────────────────────────────────
        sections.append(
            f"## Challenge Mode ({self.persona.challenge_level.title()})\n"
            + challenge_rules
        )

        # ── Response style ─────────────────────────────────────────────
        verbosity_note = (
            "Be concise.  Use bullet points for multi-step answers.  Limit prose to 2–3 sentences unless detail is requested."
            if self.persona.verbosity == "concise"
            else "Be thorough.  Provide full explanations, examples, and context when useful."
        )
        sections.append(f"## Response Style\n{verbosity_note}")

        # ── Permission context ────────────────────────────────────────
        sections.append(perm_ctx)

        # ── Output format for tool calls ──────────────────────────────
        sections.append(textwrap.dedent("""\
            ## Proposing Actions
            When you need to call a tool or take an action, respond ONLY with a JSON block
            in the following format (no prose around it):
            ```json
            {
              "action": "<action_name>",
              "params": { "<key>": "<value>" },
              "reason": "<one sentence why this action is needed>"
            }
            ```
            If you are answering a question (not taking an action), respond in plain text.
        """))

        # ── Extra injected context ────────────────────────────────────
        if extra_context:
            sections.append(f"## Additional Context\n{extra_context}")

        return "\n---\n".join(sections)

    def build_messages(
        self,
        session_id: str,
        granted_actions: Optional[list[str]] = None,
        extra_context: Optional[str] = None,
    ) -> list[dict[str, str]]:
        """
        Return the system prompt wrapped in an OpenAI-style messages list.
        Suitable for direct use with the OllamaAdapter.
        """
        system_content = self.build(session_id, granted_actions, extra_context)
        return [{"role": "system", "content": system_content}]


# ---------------------------------------------------------------------------
# Convenience singleton
# ---------------------------------------------------------------------------

_builder: Optional[ChallengePromptBuilder] = None


def get_prompt_builder(persona: Optional[PersonaConfig] = None) -> ChallengePromptBuilder:
    global _builder
    if _builder is None:
        _builder = ChallengePromptBuilder(persona)
    return _builder
