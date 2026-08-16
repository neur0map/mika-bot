"""Codex as a chat backend, over the Agent Client Protocol (ACP).

Codex has no OpenAI-compatible chat endpoint. It speaks ACP - JSON-RPC 2.0 over
stdio - through the `codex-acp` adapter, which fronts the Codex app server.
Going through ACP lets the bot run on a ChatGPT subscription instead of metered
API credits.

The adapter is expensive to start and cheap to hold, so one process is started
lazily and reused. Each `complete()` opens a *fresh* ACP session, which keeps
this provider stateless like the HTTP ones: Mika already owns the conversation
history and replays it every turn, so a session that remembered the previous
turn would double it.

ACP is a coding-agent protocol, so three of the `ChatProvider` knobs have no
wire equivalent and are deliberately ignored - see `complete()`.
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any

import acp
import httpx
from acp.interfaces import Client
from acp.schema import (
    AgentMessageChunk,
    DeniedOutcome,
    ReadTextFileResponse,
    RequestPermissionResponse,
    WriteTextFileResponse,
)

from mika.ai.llm.providers.base import ChatResult, Message, ResponseFormat
from mika.core.logging import get_logger

logger = get_logger(__name__)

_ROLE_LABELS = {"user": "User", "assistant": "Mika", "tool": "Tool result"}

_MAX_IMAGES = 4
_MAX_IMAGE_BYTES = 8 * 1024 * 1024  # Discord's own attachment ceiling for most users
_IMAGE_TIMEOUT = 20.0
# Some CDNs (Wikimedia among them) 403 a request with no User-Agent.
_IMAGE_HEADERS = {"User-Agent": "mika-bot/1.0 (+https://github.com/neur0map)"}

# Codex is built to explore a repo before answering. A social turn needs none of
# that, and every tool call costs a round-trip, so say so up front.
_CHAT_PREAMBLE = (
    "You are answering a single chat message. Do not read files, run commands, "
    "search the workspace, or call any tool - the answer is already in this "
    "prompt. Reply once, directly, and stop."
)

# When the caller asked for tools, the question needs facts this prompt does not
# contain. Mika's own web_search tool cannot run here (ACP returns no tool calls),
# so Codex has to use its own search or the answer is a guess.
_RESEARCH_PREAMBLE = (
    "You are answering a single chat message that needs current, real-world "
    "information you do not already have. Run your live web search FIRST, then "
    "answer using what it returned. Never say you are 'checking' or 'about to "
    "look' - the search must already be done before you reply, and the facts you "
    "found must be in the reply itself. Do not read files, edit anything, or run "
    "shell commands."
)

# Repeated at the very end of a research prompt. The turn contract in the middle
# ("return strict JSON only") otherwise wins and the model answers from memory
# instead of searching, so the search order has to be the last thing it reads.
_SEARCH_TRAILER = (
    "Before you write the JSON: run your web search now and read the results. The "
    "'reply' field must carry the actual facts you found - real numbers, names, or "
    "dates. A reply that says you are checking, or that you would need to look it "
    "up, is a failed answer."
)

# A research turn carries no persona and no JSON contract: both push the model to
# answer from memory. Asked plainly, it searches.
_RESEARCH_TASK = (
    "Use your live web search to answer this question: {query}\n\n"
    "Reply with only the facts you found - real numbers, names, dates, and when "
    "they are from. No preamble, no caveats, no offer to check later. If the "
    "search returns nothing useful, reply exactly: NO_RESULTS"
)

# Codex defaults to low reasoning effort, which skips tool calls. Research turns
# need enough budget to decide to search at all.
_SEARCH_EFFORT = "medium"


class _ReplyCollector(Client):
    """ACP client callbacks: keep the assistant text, refuse everything else.

    Codex streams several update kinds; only `AgentMessageChunk` is the reply.
    `AgentThoughtChunk` is reasoning and must not reach Discord.
    """

    def __init__(self) -> None:
        self._buffers: dict[str, list[str]] = {}

    def take(self, session_id: str) -> str:
        """Pop and join everything streamed for one session."""
        return "".join(self._buffers.pop(session_id, []))

    async def session_update(self, session_id: str, update: Any, **kwargs: Any) -> None:
        if not isinstance(update, AgentMessageChunk):
            return
        text = getattr(update.content, "text", None)
        if text:
            self._buffers.setdefault(session_id, []).append(text)

    async def request_permission(
        self, session_id: str, tool_call: Any, options: list[Any], **kwargs: Any
    ) -> RequestPermissionResponse:
        # A Discord turn must never authorise a file write or a shell command.
        logger.warning("codex asked for permission (denied): %s", getattr(tool_call, "title", "?"))
        return RequestPermissionResponse(outcome=DeniedOutcome(outcome="cancelled"))

    async def read_text_file(
        self,
        session_id: str,
        path: str,
        line: int | None = None,
        limit: int | None = None,
        **kwargs: Any,
    ) -> ReadTextFileResponse:
        raise acp.RequestError(code=-32601, message="filesystem access is disabled")

    async def write_text_file(
        self, session_id: str, path: str, content: str, **kwargs: Any
    ) -> WriteTextFileResponse | None:
        raise acp.RequestError(code=-32601, message="filesystem access is disabled")


class CodexACPProvider:
    """Drives the Codex CLI through the `codex-acp` stdio adapter."""

    # ACP has no way to hand the agent the caller's functions, so the pipeline
    # runs tools itself and passes the results in as text.
    supports_tool_calls = False

    def __init__(
        self,
        *,
        command: str = "codex-acp",
        cwd: str = "var/codex",
        mode: str = "read-only",
        codex_model: str = "",
        timeout: float = 90.0,
    ) -> None:
        self._command = command
        self._cwd = cwd
        self._mode = mode
        self._codex_model = codex_model
        self._timeout = timeout
        # The SDK's Client leaves terminal/elicitation methods stub-bodied, which
        # mypy reads as abstract. We declare no such capabilities, so Codex never
        # calls them and the inherited stubs are the right behaviour.
        self._collector = _ReplyCollector()  # type: ignore[abstract]
        self._stack: AsyncExitStack | None = None
        self._conn: Any = None
        self._lock = asyncio.Lock()

    async def _connection(self) -> Any:
        """Return the live ACP connection, starting the adapter on first use."""
        async with self._lock:
            if self._conn is not None:
                return self._conn
            # An empty, dedicated directory: Codex sessions are scoped to a cwd,
            # and there is nothing here for a chat turn to wander into.
            await asyncio.to_thread(Path(self._cwd).mkdir, parents=True, exist_ok=True)
            stack = AsyncExitStack()
            env = {
                **os.environ,
                "INITIAL_AGENT_MODE": self._mode,
                "NO_BROWSER": "1",  # never try to open a login browser on a server
            }
            conn, _process = await stack.enter_async_context(
                acp.spawn_agent_process(self._collector, self._command, env=env, cwd=self._cwd)
            )
            await conn.initialize(protocol_version=acp.PROTOCOL_VERSION)
            self._stack = stack
            self._conn = conn
            logger.info("codex-acp adapter ready (mode=%s cwd=%s)", self._mode, self._cwd)
            return conn

    async def _reset(self) -> None:
        """Drop a dead adapter so the next call starts a clean one."""
        async with self._lock:
            stack, self._stack, self._conn = self._stack, None, None
        if stack is not None:
            try:
                await stack.aclose()
            except Exception as error:  # teardown must not mask the real failure
                logger.debug("codex-acp teardown failed: %s", error)

    async def aclose(self) -> None:
        """Shut the adapter down (called on bot shutdown)."""
        await self._reset()

    async def complete(
        self,
        messages: list[Message],
        *,
        model: str,
        tools: list[Message] | None = None,
        temperature: float = 0.8,
        max_tokens: int = 600,
        response_format: ResponseFormat | None = None,
    ) -> ChatResult:
        """Run one Codex turn and return its text.

        Three parameters have no ACP equivalent and are ignored on purpose:

        - `model` is an OpenRouter-style id and means nothing to Codex; the
          Codex-side model comes from `codex_model` (a session config option).
        - `temperature` / `max_tokens` are owned by Codex, not the caller.
        - `response_format` cannot be enforced: ACP has no structured-output
          mode. The turn contract is carried in the prompt instead, and
          `LLMClient._parse_turn` plus `_retry_if_unstructured` already handle a
          model that answers in prose.

        `tools` is read but not forwarded: ACP gives no way to hand Codex the
        caller's functions, and this provider returns no tool calls, so the
        pipeline's tool loop exits after one pass. What it does mean is "this
        question needs facts the prompt lacks", which switches the preamble to
        let Codex use its own web search instead of guessing.
        """
        conn = await self._connection()
        try:
            return await asyncio.wait_for(
                self._run_turn(conn, messages, allow_search=tools is not None),
                timeout=self._timeout,
            )
        except TimeoutError:
            await self._reset()
            raise
        except Exception:
            # A broken pipe or a dead adapter poisons the connection for good.
            await self._reset()
            raise

    async def _run_turn(
        self, conn: Any, messages: list[Message], *, allow_search: bool = False
    ) -> ChatResult:
        text, image_urls = _render_prompt(messages, allow_search=allow_search)
        images = await _image_blocks(image_urls)
        if images:
            text = f"{text}\n\n{_attach_notice(len(images))}"
        blocks: list[Any] = [acp.text_block(text), *images]
        session = await conn.new_session(cwd=self._cwd, mcp_servers=[])
        session_id = session.session_id
        try:
            await self._select_model(conn, session_id)
            if allow_search:
                await self._select_effort(conn, session_id, _SEARCH_EFFORT)
            await conn.prompt(session_id=session_id, prompt=blocks)
            return ChatResult(content=self._collector.take(session_id).strip(), tool_calls=[])
        finally:
            self._collector.take(session_id)  # drop anything left if we failed mid-turn
            try:
                await conn.close_session(session_id=session_id)
            except Exception as error:  # a leaked session must not fail the reply
                logger.debug("closing codex session failed: %s", error)

    async def research(self, query: str) -> str:
        """Look `query` up with Codex's own web search and return the bare facts.

        Run as its own session, free of the persona and the JSON turn contract.
        Both of those pull the model toward answering immediately, and the result
        is an "I'd have to check" non-answer; stripped back to a plain research
        question it searches reliably.
        """
        conn = await self._connection()
        session = await conn.new_session(cwd=self._cwd, mcp_servers=[])
        session_id = session.session_id
        try:
            await self._select_model(conn, session_id)
            await self._select_effort(conn, session_id, _SEARCH_EFFORT)
            await asyncio.wait_for(
                conn.prompt(
                    session_id=session_id,
                    prompt=[acp.text_block(_RESEARCH_TASK.format(query=query))],
                ),
                timeout=self._timeout,
            )
            return self._collector.take(session_id).strip()
        except Exception as error:
            logger.warning("codex research failed for %r: %s", query[:60], error)
            return ""
        finally:
            self._collector.take(session_id)
            try:
                await conn.close_session(session_id=session_id)
            except Exception as error:
                logger.debug("closing research session failed: %s", error)

    async def _select_effort(self, conn: Any, session_id: str, effort: str) -> None:
        """Raise reasoning effort so the model actually reaches for its search tool."""
        try:
            await conn.set_config_option(
                config_id="reasoning_effort", session_id=session_id, value=effort
            )
        except Exception as error:  # keep the Codex default
            logger.warning("codex reasoning_effort %r rejected: %s", effort, error)

    async def _select_model(self, conn: Any, session_id: str) -> None:
        """Pin the Codex-side model when one is configured."""
        if not self._codex_model:
            return
        try:
            await conn.set_config_option(
                config_id="model", session_id=session_id, value=self._codex_model
            )
        except Exception as error:  # fall back to the Codex default
            logger.warning("codex model %r rejected: %s", self._codex_model, error)


def _split_content(content: Any) -> tuple[str, list[str]]:
    """Return (text, image urls) for either a plain string or OpenAI content parts."""
    if isinstance(content, str):
        return content.strip(), []
    if not isinstance(content, list):
        return json.dumps(content), []
    texts: list[str] = []
    images: list[str] = []
    for part in content:
        if not isinstance(part, dict):
            continue
        if part.get("type") == "text":
            texts.append(str(part.get("text") or ""))
        elif part.get("type") == "image_url":
            url = (part.get("image_url") or {}).get("url")
            if url:
                images.append(str(url))
    return "\n".join(t for t in texts if t).strip(), images


def _render_prompt(messages: list[Message], *, allow_search: bool = False) -> tuple[str, list[str]]:
    """Flatten OpenAI-style messages into the single text block ACP accepts.

    ACP has no role array: one prompt is one user turn. The system prompt and the
    replayed history are folded into that turn, labelled so Codex can still tell
    who said what. Images ride alongside as separate ACP blocks, so their URLs are
    pulled out here rather than stringified into the text.
    """
    system: list[str] = []
    history: list[str] = []
    images: list[str] = []
    for message in messages:
        role = str(message.get("role") or "user")
        text, part_images = _split_content(message.get("content"))
        images.extend(part_images)
        if not text:
            continue
        if role == "system":
            system.append(text)
        else:
            history.append(f"{_ROLE_LABELS.get(role, role)}: {text}")

    sections = [_RESEARCH_PREAMBLE if allow_search else _CHAT_PREAMBLE]
    if system:
        sections.append("\n\n".join(system))
    if history:
        current = history[-1]
        earlier = history[:-1]
        if earlier:
            sections.append("Conversation so far:\n" + "\n".join(earlier))
        sections.append("Now reply to this message:\n" + current)
    if allow_search:
        sections.append(_SEARCH_TRAILER)
    return "\n\n".join(sections), images


def _attach_notice(count: int) -> str:
    """Tell the model about images that actually made it into the prompt.

    Written from the fetched-block count, not the requested URLs: promising a
    picture that failed to download makes the model claim it can see something.
    """
    return (
        f"{count} image(s) are attached to this message. Look at them and let what "
        "you see drive your reply."
    )


async def _image_blocks(urls: list[str]) -> list[Any]:
    """Download images and wrap them as ACP image blocks.

    ACP carries image bytes, not links, so each URL is fetched here. A picture
    that will not download is skipped rather than failing the whole reply.
    """
    blocks: list[Any] = []
    if not urls:
        return blocks
    async with httpx.AsyncClient(
        timeout=_IMAGE_TIMEOUT, follow_redirects=True, headers=_IMAGE_HEADERS
    ) as http:
        for url in urls[:_MAX_IMAGES]:
            try:
                response = await http.get(url)
                response.raise_for_status()
                data = response.content
                if len(data) > _MAX_IMAGE_BYTES:
                    logger.warning("skipping %s: %d bytes over limit", url[:80], len(data))
                    continue
                mime = (response.headers.get("content-type") or "").split(";")[0].strip()
                if not mime.startswith("image/"):
                    logger.warning("skipping %s: content-type %r", url[:80], mime)
                    continue
                blocks.append(acp.image_block(base64.b64encode(data).decode(), mime))
            except Exception as error:
                logger.warning("image fetch failed for %s: %s", url[:80], error)
    return blocks
