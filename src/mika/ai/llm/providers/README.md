# ai/llm/providers/

Backend adapters, one file per provider, all implementing `base.ChatProvider`.

- `base.py` - the `ChatProvider` protocol and `ChatMessage`.
- `openai_compatible.py` - OpenRouter / Groq / Together / OpenAI.
- `codex_acp.py` - Codex CLI over the Agent Client Protocol (ACP).
- `factory.py` - maps `MIKA_LLM_PROVIDER` to one of the above.

Adding a provider means adding a file and one branch in `factory.py`.

## Codex over ACP

Codex has no OpenAI-compatible chat endpoint. It speaks ACP - JSON-RPC 2.0 over
stdio - through the `codex-acp` adapter, so the bot can run on a ChatGPT
subscription instead of metered API credits.

Setup:

```bash
npm i -g @openai/codex @agentclientprotocol/codex-acp
codex login                 # auth lands in ~/.codex/auth.json
uv sync --extra codex       # installs agent-client-protocol
```

Codex needs live search switched on, or current-fact questions get guesses. Put
this at the **top** of `~/.codex/config.toml`, above any `[table]` header - TOML
would otherwise read it as a key inside that table:

```toml
web_search = "live"
```

Then set `MIKA_LLM_PROVIDER=codex` (or `MIKA_LLM_FALLBACK_PROVIDER=codex`). In
Docker, build with `MIKA_INSTALL_CODEX=true` and mount the host's `~/.codex`
(read-write - Codex refreshes its own tokens).

### What ACP cannot carry

ACP is a coding-agent protocol, so four `ChatProvider` arguments are ignored:

| Argument | Why |
| --- | --- |
| `model` | An OpenRouter-style id means nothing to Codex. Use `MIKA_LLM_CODEX_MODEL`, applied as an ACP session config option. |
| `temperature`, `max_tokens` | Owned by Codex, not the caller. |
| `response_format` | ACP has no structured-output mode. |
| `tools` | Codex owns its own tools; `complete()` returns no tool calls, so the pipeline's tool loop exits after one pass. |

Losing `response_format` is safe because the `mika_turn.v2` contract is also
carried in the prompt, and `LLMClient._parse_turn` plus `_retry_if_unstructured`
already recover from a model that answers in prose. In practice Codex returns
valid JSON.

### Shape

One adapter process is started lazily and reused; each `complete()` opens a
fresh ACP session so the provider stays stateless, like the HTTP ones. Mika
already owns conversation history and replays it every turn, so a session that
remembered the previous turn would double it.

Sessions run in `read-only` mode, permission requests are denied, and the
filesystem methods refuse - a Discord message must never authorise a file write
or a shell command.

Expect ~5-6s per turn, noticeably slower than a chat-completions API.

### Images

Codex accepts pictures over ACP, including animated GIFs, with no conversion.
`run_turn` builds OpenAI-style content parts and this provider downloads each
URL and re-sends it as an ACP image block, because ACP carries bytes rather than
links. The "N image(s) are attached" notice is written from the number that
actually downloaded - promising a picture that 404'd makes the model claim it can
see something it cannot.

### Current-fact questions

ACP cannot hand Codex the caller's functions, so `supports_tool_calls` is False
and `web_search` would never fire. `run_turn` therefore looks the facts up before
the turn and pastes them into the prompt, preferring this provider's `research()`
(Codex's own search, which returns far better material than a snippet scrape)
and falling back to the registry tool.

`research()` runs in its own session with no persona and no JSON contract: both
push the model to answer from memory instead of searching. It sometimes still
ends its turn on a preamble, so `_looks_like_facts` rejects a result carrying
neither a number nor a link and the lookup is retried.
