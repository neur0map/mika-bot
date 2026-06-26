# What it costs to run

The bot itself is free. The only thing you pay for is the **AI** - and only when the
bot actually answers an AI message (`/ask`, mentions, persona creation). Everything
else (slash commands, moderation, GIFs, games, tools) is free and unlimited.

## How AI billing works

You bring your own **OpenRouter** key (one key, hundreds of models). OpenRouter is
pay-as-you-go: you're billed per *token* (roughly per word) of input and output. No
subscription, no monthly minimum - if the bot sits idle, you pay nothing.

## Two models, two jobs

1. **Your main chat model** - answers everyday messages. *You pick this* during `mika
   setup`. This is where almost all spend goes, so the choice is yours: cheap and fast,
   or smart and pricier.
2. **The persona creator model** - only runs when you use `/persona create` to generate
   a new character. The bot presets a strong, well-priced model for this so personas
   come out good without you having to tune it. It runs rarely (once per persona), so
   its cost is negligible.

## Rough cost estimates

Prices change, so check [openrouter.ai/models](https://openrouter.ai/models) for the
live numbers. As a ballpark, for the **main chat model**:

| Tier | Example models | ~Cost per 1,000 replies* |
|---|---|---|
| Budget | small/fast models | a few cents |
| Balanced | mid-size models | ~$0.10 - $0.50 |
| Premium | frontier models | ~$1 - $5+ |

\* A "reply" assumes a short question and a short answer plus recent memory as context.
Long conversations and big context windows cost more.

## Keeping costs down

- **Pick a budget or balanced main model** - they're great for chat; save premium models
  for when you really want them.
- **Memory window** controls how much past conversation is sent each time. Smaller =
  cheaper. Set it in `.env` (`MIKA_MEMORY_RECENT_WINDOW`).
- **Web search** adds a little context when the bot looks things up. Turn it off
  (`MIKA_TOOLS_WEB_SEARCH_ENABLED=false`) if you want the cheapest possible replies.
- **Set a spend limit on OpenRouter** itself - it supports hard caps so you can never be
  surprised by a bill.

## What's always free

Slash commands, moderation, anti-spam, tickets, giveaways, welcome messages, GIFs
(with a free Klipy key), games, text tools, image effects, downloads, and the dashboard
- none of these call the AI, so none of them cost anything.
