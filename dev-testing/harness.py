"""Headless test harness: run slash-command callbacks with fake Discord objects.

build_tree() registers every command on a real CommandTree. invoke() runs one
command's callback against a fake interaction and returns a Sent capturing what
the command tried to send (content, embeds, files, modals).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import discord
from discord import app_commands

from mika.bot.commands import register_all

_EPOCH = datetime(2022, 1, 1, tzinfo=UTC)
_OPT = discord.AppCommandOptionType


class Fake:
    """Attribute bag: declared attrs are real, anything else returns a lenient mock."""

    def __init__(self, **attrs: Any) -> None:
        self.__dict__.update(attrs)

    def __getattr__(self, name: str) -> Any:
        mock = MagicMock()
        self.__dict__[name] = mock
        return mock

    def __str__(self) -> str:
        return str(self.__dict__.get("name", "fake"))


class _Asset:
    def __init__(self, url: str = "https://cdn.example.com/a.png") -> None:
        self.url = url

    def __str__(self) -> str:
        return self.url


class Sent:
    """Everything a command tried to send during one interaction."""

    def __init__(self) -> None:
        self.payloads: list[dict[str, Any]] = []

    def add(self, content: Any = None, **kwargs: Any) -> None:
        self.payloads.append({"content": content, **kwargs})

    @property
    def text(self) -> str:
        out: list[str] = []
        for payload in self.payloads:
            if payload.get("content"):
                out.append(str(payload["content"]))
            emb = payload.get("embed")
            if isinstance(emb, discord.Embed):
                out.append(_embed_text(emb))
        return "\n".join(out)

    @property
    def file(self) -> Any:
        for payload in self.payloads:
            if payload.get("file") is not None:
                return payload["file"]
            if payload.get("files"):
                return payload["files"][0]
        return None

    def __bool__(self) -> bool:
        return bool(self.payloads)


def _embed_text(emb: discord.Embed) -> str:
    parts = [str(emb.title or ""), str(emb.description or "")]
    parts += [f"{field.name} {field.value}" for field in emb.fields]
    if emb.footer.text:
        parts.append(str(emb.footer.text))
    return "\n".join(part for part in parts if part)


class _Response:
    def __init__(self, sent: Sent) -> None:
        self._sent = sent
        self._done = False

    def is_done(self) -> bool:
        return self._done

    async def send_message(self, content: Any = None, **kwargs: Any) -> None:
        self._done = True
        self._sent.add(content, **kwargs)

    async def defer(self, **kwargs: Any) -> None:
        self._done = True

    async def send_modal(self, modal: Any) -> None:
        self._done = True
        self._sent.payloads.append({"modal": modal})

    async def edit_message(self, **kwargs: Any) -> None:
        self._sent.add(**kwargs)


class _Followup:
    def __init__(self, sent: Sent) -> None:
        self._sent = sent

    async def send(self, content: Any = None, **kwargs: Any) -> Any:
        self._sent.add(content, **kwargs)
        return MagicMock()


def make_member(uid: int = 42, name: str = "tester", *, admin: bool = True) -> Fake:
    perms = discord.Permissions.all() if admin else discord.Permissions.none()
    return Fake(
        id=uid,
        name=name,
        display_name=name,
        mention=f"<@{uid}>",
        bot=False,
        display_avatar=_Asset(),
        avatar=_Asset(),
        created_at=_EPOCH,
        joined_at=_EPOCH,
        roles=[],
        color=discord.Color.default(),
        guild_permissions=perms,
        ban=AsyncMock(),
        kick=AsyncMock(),
        edit=AsyncMock(),
        add_roles=AsyncMock(),
        remove_roles=AsyncMock(),
        timeout=AsyncMock(),
        send=AsyncMock(),
        move_to=AsyncMock(),
    )


def make_role(rid: int = 7, name: str = "Members") -> Fake:
    return Fake(
        id=rid,
        name=name,
        mention=f"<@&{rid}>",
        color=discord.Color.default(),
        position=1,
        created_at=_EPOCH,
        edit=AsyncMock(),
        delete=AsyncMock(),
    )


def make_channel(cid: int = 10, name: str = "general", *, nsfw: bool = False) -> Fake:
    return Fake(
        id=cid,
        name=name,
        mention=f"<#{cid}>",
        is_nsfw=lambda: nsfw,
        created_at=_EPOCH,
        send=AsyncMock(),
        purge=AsyncMock(return_value=[1, 2, 3]),
        edit=AsyncMock(),
        set_permissions=AsyncMock(),
    )


def make_guild() -> Fake:
    member = make_member()
    return Fake(
        id=1,
        name="Test Server",
        member_count=3,
        created_at=_EPOCH,
        icon=_Asset(),
        banner=_Asset(),
        roles=[make_role()],
        emojis=[],
        members=[member],
        me=member,
        owner_id=42,
        premium_subscription_count=0,
        create_text_channel=AsyncMock(return_value=make_channel()),
        create_role=AsyncMock(return_value=make_role()),
        create_custom_emoji=AsyncMock(),
        fetch_ban=AsyncMock(),
        bans=MagicMock(),
    )


def make_bot(user: Fake, guild: Fake) -> Fake:
    return Fake(
        user=user,
        guilds=[guild],
        latency=0.05,
        application_id=123456789,
        llm=Fake(reply=AsyncMock(return_value="ai reply")),
        get_guild=MagicMock(return_value=guild),
    )


def make_interaction(
    *, user: Fake | None = None, guild: Any = ..., channel: Fake | None = None
) -> Any:
    sent = Sent()
    member = user or make_member()
    resolved_guild = make_guild() if guild is ... else guild
    chan = channel or make_channel()
    bot = make_bot(member, resolved_guild or make_guild())
    interaction = Fake(
        response=_Response(sent),
        followup=_Followup(sent),
        user=member,
        guild=resolved_guild,
        guild_id=(resolved_guild.id if resolved_guild else None),
        channel=chan,
        channel_id=chan.id,
        client=bot,
        command=None,
    )
    interaction._sent = sent
    return interaction


def build_tree() -> app_commands.CommandTree[Any]:
    """A CommandTree with every command registered (no Discord connection)."""
    client = discord.Client(intents=discord.Intents.none())
    tree = app_commands.CommandTree(client)
    register_all(tree)
    return tree


def _find(
    tree: app_commands.CommandTree[Any], qualified: str
) -> app_commands.Command[Any, ..., Any]:
    for cmd in tree.walk_commands():
        if isinstance(cmd, app_commands.Command) and cmd.qualified_name == qualified:
            return cmd
    raise KeyError(qualified)


async def invoke(
    tree: app_commands.CommandTree[Any], name: str, *, interaction: Any = None, **kwargs: Any
) -> Sent:
    """Run a command by its qualified name and return what it sent."""
    cmd = _find(tree, name)
    inter = interaction or make_interaction()
    await cmd.callback(inter, **kwargs)
    return inter._sent


def arg_for(param: Any) -> Any:
    """A safe synthesized value for one command parameter (for the smoke walk)."""
    mapping = {
        _OPT.string: "test",
        _OPT.integer: 3,
        _OPT.number: 1.0,
        _OPT.boolean: False,
        _OPT.user: make_member(),
        _OPT.mentionable: make_member(),
        _OPT.channel: make_channel(),
        _OPT.role: make_role(),
    }
    return mapping.get(param.type, "test")


def synth_kwargs(cmd: app_commands.Command[Any, ..., Any]) -> dict[str, Any]:
    """Fill required parameters of a command with safe synthesized values."""
    return {p.name: arg_for(p) for p in cmd.parameters if p.required}
