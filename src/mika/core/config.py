"""Application configuration loaded from environment / .env (see .env.example).

All tunables flow through here; nothing else should read os.environ directly.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


class DiscordSettings(BaseSettings):
    """Discord bot credentials and where the bot is allowed to operate."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_prefix="DISCORD_")

    token: str = ""
    client_id: str = ""
    guild_ids: str = ""
    response_channel_ids: str = ""

    @property
    def guild_id_list(self) -> list[str]:
        """Guild ids the bot will serve (empty = every guild it joins)."""
        return _csv(self.guild_ids)

    @property
    def response_channel_id_list(self) -> list[str]:
        """Channels where the bot chats without being mentioned."""
        return _csv(self.response_channel_ids)


class LLMSettings(BaseSettings):
    """Primary and fallback LLM provider configuration (OpenAI-compatible)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_prefix="MIKA_LLM_")

    provider: str = "openrouter"
    base_url: str = "https://openrouter.ai/api/v1"
    api_key: str = ""
    model: str = "openai/gpt-4o-mini"
    temperature: float = 0.8
    max_tokens: int = 600
    fallback_base_url: str = ""
    fallback_api_key: str = ""
    fallback_model: str = ""

    @property
    def has_fallback(self) -> bool:
        return bool(self.fallback_api_key and self.fallback_base_url and self.fallback_model)


class MemorySettings(BaseSettings):
    """Conversation memory: a local recent-window plus optional Honcho recall."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_prefix="MIKA_MEMORY_")

    recent_window: int = 20
    honcho_enabled: bool = False
    honcho_base_url: str = "http://127.0.0.1:8000"
    honcho_workspace: str = "default"
    honcho_session: str = "default"


class ToolSettings(BaseSettings):
    """LLM tool access (the bot's window onto the internet)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_prefix="MIKA_TOOLS_")

    web_search_enabled: bool = True
    web_search_max_results: int = 4
    web_search_timeout: float = 8.0


class WebSettings(BaseSettings):
    """Localhost settings / overview web server."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_prefix="MIKA_WEB_")

    host: str = "127.0.0.1"
    port: int = 8080
    secret: str = ""


class PersonaSettings(BaseSettings):
    """The bot's user-facing identity. The only place its name/persona is defined."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_prefix="MIKA_PERSONA_")

    name: str = "Mika"
    file: Path = Path("./config/persona.md")


class Settings(BaseSettings):
    """Top-level application settings, composed from the sections above."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_prefix="MIKA_")

    env: str = "production"
    log_level: str = "info"
    data_dir: Path = Path("./var")
    database_url: str = "sqlite+aiosqlite:///./var/mika.sqlite3"
    discord: DiscordSettings = Field(default_factory=DiscordSettings)
    llm: LLMSettings = Field(default_factory=LLMSettings)
    memory: MemorySettings = Field(default_factory=MemorySettings)
    tools: ToolSettings = Field(default_factory=ToolSettings)
    web: WebSettings = Field(default_factory=WebSettings)
    persona: PersonaSettings = Field(default_factory=PersonaSettings)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached application settings instance."""
    return Settings()
