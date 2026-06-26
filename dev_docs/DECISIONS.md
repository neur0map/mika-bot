# Build decisions

Autonomous calls made while building toward the roadmap. Recorded so the rationale
survives and a buyer/auditor can see the boundaries baked into the product.

## Command catalog (the "340")

The studied reference (Nighty, `nighty-commands-340.md`) is 340 commands tagged
**273 [S] safe** · **30 [U] selfbot** · **37 [X] abusive**.

- **Build the 273 [S] safe** as proper slash commands.
- **Add roadmap features** (moderation, tickets, giveaways, OSINT, anime, GIFs,
  image-gen, presence, emoji clone, server templates, …) so the **compliant** total
  reaches and exceeds **340 working commands**.
- **Skip all 37 [X] abusive** — nuke, mass-spam, ghostping, token/nitro generators,
  session-spoof, detection evasion. They get the bot (and the buyer) banned and are
  unsellable. A sold product must not ship them.
- **Skip pure account-automation [U]** (AFK loops, status loops, giveaway-joiner,
  account backups, mass-leave). Where an item has a compliant *server-side* shape
  (e.g. bot-side snipe limited to channels the bot sees), build that instead.

## Explicit skips (per owner)

- Spotify music integration, voice calls, TTS.
- Music streaming overall: it is voice-dependent (needs a voice client), which the
  above skip implies; left deferred in the roadmap.

## Safety gating

- **NSFW fetch commands**: implemented but gated to age-restricted channels **and**
  off behind a config flag by default.
- **OSINT / username / enumeration**: green-area only — public lookups, no intrusion;
  documented as educational/lawful use.

## Testing

- A headless harness (`dev-testing/`) registers every command on a real
  `CommandTree` and invokes each callback with fake Discord objects, so the full
  catalog is smoke-tested offline each pass.
- Commands with real Discord side effects (ban/kick/purge/role/channel ops) are
  exercised for arg-handling and permission gating against fakes; their live effect
  is verified by the owner in Discord as the final step.
