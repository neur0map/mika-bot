"""Rename-safe guild emoji discovery and eligibility."""

from __future__ import annotations

from dataclasses import dataclass

from mika.conversation.skills.natural_expression.contracts import EmojiProfile


@dataclass(frozen=True, slots=True)
class GuildEmojiDescriptor:
    """Discord metadata needed without importing Discord into the skill."""

    emoji_id: str
    name: str
    animated: bool
    available: bool
    role_ids: tuple[str, ...]


@dataclass(slots=True)
class _CatalogEntry:
    descriptor: GuildEmojiDescriptor
    description: str = "custom emoji"
    family: str = "unknown"
    confidence: float = 0.0


class GuildEmojiCatalog:
    """Store current guild metadata while preserving learned snowflake profiles."""

    def __init__(self) -> None:
        self._entries: dict[tuple[str, str], _CatalogEntry] = {}

    def sync(self, guild_id: str, descriptors: list[GuildEmojiDescriptor]) -> None:
        """Refresh mutable metadata and mark absent emoji unavailable."""
        seen: set[tuple[str, str]] = set()
        for descriptor in descriptors:
            key = (guild_id, descriptor.emoji_id)
            seen.add(key)
            existing = self._entries.get(key)
            if existing is None:
                self._entries[key] = _CatalogEntry(descriptor)
            else:
                existing.descriptor = descriptor
        for key, entry in self._entries.items():
            if key[0] == guild_id and key not in seen:
                old = entry.descriptor
                entry.descriptor = GuildEmojiDescriptor(
                    old.emoji_id, old.name, old.animated, False, old.role_ids
                )

    def set_description(
        self,
        guild_id: str,
        emoji_id: str,
        description: str,
        family: str,
        confidence: float,
    ) -> None:
        """Attach learned evidence to an existing snowflake."""
        entry = self._entries[(guild_id, emoji_id)]
        entry.description = description
        entry.family = family
        entry.confidence = confidence

    def profiles(
        self, guild_id: str, *, role_ids: tuple[str, ...] = ()
    ) -> tuple[EmojiProfile, ...]:
        """Return only emoji available to the current member context."""
        roles = set(role_ids)
        profiles: list[EmojiProfile] = []
        for (entry_guild, _), entry in self._entries.items():
            descriptor = entry.descriptor
            if entry_guild != guild_id or not descriptor.available:
                continue
            if descriptor.role_ids and not roles.intersection(descriptor.role_ids):
                continue
            prefix = "a" if descriptor.animated else ""
            profiles.append(
                EmojiProfile(
                    f"<{prefix}:{descriptor.name}:{descriptor.emoji_id}>",
                    entry.family,
                    entry.description,
                    entry.confidence,
                    kind="guild",
                    guild_id=guild_id,
                )
            )
        return tuple(profiles)
