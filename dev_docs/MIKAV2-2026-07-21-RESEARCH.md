# MikaV2 conversational-bot research — 2026-07-21

## Scope and evidence standard

This report uses sources available through July 2026. Vendor benchmark claims are labeled as vendor claims; Text Arena is included as large-scale human-preference evidence, not proof of a universal winner. Raw Discord logs and message content are deliberately not committed to the repository.

## Model recommendations

There is no defensible claim that one model is universally and permanently “the absolute best.” The July 16, 2026 Text Arena snapshot contains several close frontier models with different confidence intervals and vote counts. These recommendations optimize for Mika's specific need: social judgment, persona consistency, concise structured actions, and operational reliability.

| Role | Recommendation | Why | Integration decision |
|---|---|---|---|
| Premium evaluation/control | Claude Opus 4.8 | Best premium candidate for nuanced judgment, long-session style adherence, self-correction, and social ambiguity. Anthropic released it May 28, 2026; its Text Arena family has high human-preference positions with large vote samples. | Use only through a tested OpenAI-compatible gateway or a native provider adapter. Do not make it default before contract tests pass. |
| Hosted production default | GPT-5.4 mini | Strong capability/cost/latency balance, native OpenAI-compatible tool calling and strict structured output, with minimal migration risk for Mika's current provider abstraction. | Primary migration candidate. Use strict JSON Schema for social turns and low/no reasoning effort for normal chat. |
| Local A/B candidate on one 20 GB GPU | Qwen3.6-35B-A3B at IQ3/Q3 GGUF | Apache-2.0 MoE model with 35B total / 3B active parameters, making it the strongest plausible fast local candidate under the VRAM cap. | Text/social-only experimental route at 4K–8K context, one concurrent request; keep hosted fallback for current-fact tools and malformed tool calls. |

### Premium: Claude Opus 4.8

- Released May 28, 2026. Anthropic positions it as stronger at judgment, style direction, tool efficiency, and self-correction.
- The July 16 Text Arena leaderboard places several mature Opus variants near the top with tens of thousands of votes. Opus 4.8 itself is close to the leaders, but that is not proof of universal superiority.
- Public price/context at research time: $5/M input and $25/M output, 1M context. This is a quality-control or premium-route candidate, not a default for every Discord message.
- Mika compatibility: its first-party transport is Anthropic Messages API, while Mika currently uses OpenAI Chat Completions. Keep the provider boundary clean: either test an OpenAI-compatible gateway carefully or add a native Anthropic adapter with contract fixtures.

Sources:
- <https://www.anthropic.com/news/claude-opus-4-8>
- <https://platform.claude.com/docs/en/about-claude/pricing>
- <https://docs.anthropic.com/en/docs/build-with-claude/tool-use>
- <https://arena.ai/leaderboard/text>

### Hosted default: GPT-5.4 mini

- Released March 17, 2026. OpenAI reports it is over 2× faster than GPT-5 mini and reports strong tool-use/reasoning benchmarks. Those benchmark numbers are vendor-reported, but the model also has a large public Text Arena sample.
- Public price/context at research time: $0.75/M input and $4.50/M output, 400K context.
- It is the lowest-risk upgrade from the current OpenAI-compatible pipeline. More importantly, OpenAI supports strict JSON Schema structured outputs, while Mika currently asks only for `json_object` and experiences a high fallback rate.
- Use `reasoning_effort=none` or low for ordinary conversation. Higher effort belongs behind a deliberate route for substantial questions, not social banter.

Sources:
- <https://openai.com/index/introducing-gpt-5-4-mini-and-nano/>
- <https://platform.openai.com/docs/guides/structured-outputs>
- <https://arena.ai/leaderboard/text>

### Local candidate: Qwen3.6-35B-A3B

- Qwen's official model card describes an Apache-2.0 35B-total, 3B-active MoE model with 262K native context, tool support, and OpenAI-compatible serving.
- A 20 GB GPU does not safely fit Q4_K_M once runtime/KV cache are included. Q3_K_M is roughly 17–18 GB and IQ3/calibrated 3-bit variants around 13–16 GB, leaving limited practical context headroom.
- Start with text-only, non-thinking Q3/IQ3, 4K–8K context, and a single concurrent generation. Do not claim the 262K context is usable on this hardware.
- Tool/function-call parsing on constrained GGUF/llama.cpp deployments remains an experimental risk. Mika's social turns can still work because its current-fact tools are intentionally rare; retain a hosted fallback for fact/tool routing.

Sources:
- <https://huggingface.co/Qwen/Qwen3.6-35B-A3B>
- <https://huggingface.co/prithivMLmods/Qwen3.6-35B-A3B-MTP-GGUF>
- <https://github.com/ggml-org/llama.cpp/issues/22684>
- <https://github.com/ggml-org/llama.cpp/issues/21771>

## Current quality baseline

Latest observed live MikaV2 quality score: **52/100**. This is an evidence-based baseline, not a judgment of the unobserved `af8df01` deployment.

| Area | Score | Evidence |
|---|---:|---|
| Structured-turn reliability | 9/20 | 61/105 clean JSON (58.1%), 44/105 fallbacks (41.9%) after July 8. |
| Concision and Discord fit | 4/15 | Median 123 characters; 58/105 exceeded 120; maximum 643. |
| Reactions/GIFs/media | 3/15 | One action on five inbound-media turns; no matching GIF. |
| Provider/runtime reliability | 12/15 | 543 successful OpenRouter completion calls; two tracebacks and unexplained exit 137 remain. |
| Learning/reflection in practice | 4/15 | Feedback is collected, but no active reflection state or demonstrated closed loop. |
| Observability/regression coverage | 12/15 | Useful turn telemetry and deterministic tests exist. |

### Improvement timeline

| Period | What changed | What was actually observed |
|---|---|---|
| Before July 8 | Initial persona/media work | More reactions/GIFs in sparse earlier telemetry, but little modern structured telemetry. |
| July 8–19 | MiniMax structured-output/GIF hotfixes | 58.1% JSON compliance, high fallback/verbosity, zero outbound media actions in the measured window. |
| July 19 `af8df01` | Tool gating, true silence, 180-character social cap | Built/deployed while Mika is off; no post-deploy live traffic, so no behavioral credit yet. |

## Conversation-only audit

The current repository exposes 348 registered slash commands. The final conversation product should remove the complete `src/mika/bot/commands/` package and registration path, but retain message events, media search, reactions-as-feedback, scheduler/reflection, LLM/memory/persistence, and operational CLI commands.

Critical migration fact: removing registration does not guarantee that Discord deletes already-registered global/guild commands. A one-time authenticated empty-command-tree/bulk-overwrite cleanup must be staged and verified in Discord before the commandless release is declared complete.

See `docs/plans/2026-07-21-mika-conversation-only.md` for the execution order and exact paths.

## Controlled provider smoke benchmark — 2026-07-21

The stopped VPS image was tested without Discord connectivity using six synthetic Mika-shaped prompts: casual mishap, explicit GIF request, banter, comfort, simple question, and inbound-media context. Each provider was asked through the same strict `mika_turn.v2` pipeline. The output below contains aggregate behavior only; no user/archive message content was used.

| Route | Attempts | Strict-contract turns | Errors | ≤180-char turns | Reaction turns | Selected media |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `minimax/minimax-m3` | 6 | 4 | 2 | 4 | 4 | 1 |
| `openai/gpt-5.4-mini` | 6 | 5 | 1 | 5 | 5 | 2 |

The sample is too small to prove a live conversational win, but GPT-5.4 mini improved strict-contract compliance by one turn and reduced errors by one on identical inputs. It is configured as the stopped deployment's primary model. The existing media gate and a future controlled Discord cohort remain required before evaluating discretionary GIF behavior.
