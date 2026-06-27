"""The AI chat is locked to allowed servers and never answers DMs."""

from __future__ import annotations

from types import SimpleNamespace

from mika.bot.events.message import _in_scope


def _msg(guild_id: int | None) -> SimpleNamespace:
    guild = None if guild_id is None else SimpleNamespace(id=guild_id)
    return SimpleNamespace(guild=guild)


def test_dms_are_ignored() -> None:
    assert _in_scope(_msg(None), {"123"}) is False


def test_allowed_guild_responds() -> None:
    assert _in_scope(_msg(123), {"123"}) is True


def test_other_guild_ignored() -> None:
    assert _in_scope(_msg(999), {"123"}) is False


def test_no_allowlist_means_any_guild_but_still_no_dms() -> None:
    assert _in_scope(_msg(555), set()) is True
    assert _in_scope(_msg(None), set()) is False
