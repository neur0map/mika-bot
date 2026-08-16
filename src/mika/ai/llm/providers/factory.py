"""Build the configured provider from settings.

`MIKA_LLM_PROVIDER` used to be a label nobody read - both the primary and the
fallback were hard-wired to the OpenAI-compatible client. It now selects the
backend, so `codex` can be swapped in without touching call sites.
"""

from __future__ import annotations

from pathlib import Path

from mika.ai.llm.providers.base import ChatProvider
from mika.ai.llm.providers.openai_compatible import OpenAICompatibleProvider
from mika.core.config import LLMSettings

_CODEX_PROVIDERS = {"codex", "codex-acp", "acp"}


def is_codex_provider(name: str) -> bool:
    """Whether a provider name selects the Codex/ACP backend."""
    return name.strip().lower() in _CODEX_PROVIDERS


def build_provider(settings: LLMSettings, *, data_dir: Path | None = None) -> ChatProvider:
    """Return the primary chat backend."""
    if is_codex_provider(settings.provider):
        return _build_codex(settings, data_dir)
    return OpenAICompatibleProvider(base_url=settings.base_url, api_key=settings.api_key)


def build_fallback_provider(
    settings: LLMSettings, *, data_dir: Path | None = None
) -> ChatProvider | None:
    """Return the backup backend, or None when no fallback is configured."""
    if is_codex_provider(settings.fallback_provider):
        return _build_codex(settings, data_dir)
    if not settings.has_fallback:
        return None
    return OpenAICompatibleProvider(
        base_url=settings.fallback_base_url, api_key=settings.fallback_api_key
    )


def _build_codex(settings: LLMSettings, data_dir: Path | None) -> ChatProvider:
    # Imported lazily: agent-client-protocol is an optional extra, so a bot that
    # never uses Codex must not need it installed.
    from mika.ai.llm.providers.codex_acp import CodexACPProvider  # noqa: PLC0415

    return CodexACPProvider(
        command=settings.codex_command,
        cwd=settings.codex_cwd or str((data_dir or Path("./var")) / "codex"),
        mode=settings.codex_mode,
        codex_model=settings.codex_model,
        timeout=settings.codex_timeout,
    )
