"""Application configuration loaded from environment / .env (see .env.example).

All tunables flow through here; nothing else should read os.environ directly.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DiscordSettings(BaseSettings):
    """Discord bot credentials and guild allowlist."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_prefix="DISCORD_")

    token: str = ""
    client_id: str = ""
    guild_ids: str = ""

    @property
    def guild_id_list(self) -> list[str]:
        """Allowlisted guild ids, parsed from the comma-separated value."""
        return [gid.strip() for gid in self.guild_ids.split(",") if gid.strip()]


class LLMSettings(BaseSettings):
    """Primary and fallback LLM provider configuration (OpenAI-compatible)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_prefix="MIKA_LLM_")

    provider: str = "openrouter"
    base_url: str = "https://openrouter.ai/api/v1"
    api_key: str = "CHANGEME"
    model: str = "x-ai/grok-4.3"
    fallback_base_url: str = ""
    fallback_api_key: str = ""
    fallback_model: str = ""


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
    web: WebSettings = Field(default_factory=WebSettings)
    persona: PersonaSettings = Field(default_factory=PersonaSettings)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached application settings instance."""
    return Settings()
