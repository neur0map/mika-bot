# What it costs to run

The bot itself is free. The only thing you pay for is the **AI** - and only when the
bot actually answers a message or performs an optional reflection. GIF search is an
optional external service; Discord itself does not charge for the bot API.

## How AI billing works

You bring your own **OpenRouter** key (one key, hundreds of models). OpenRouter is
pay-as-you-go: you're billed per *token* (roughly per word) of input and output. No
subscription, no monthly minimum - if the bot sits idle, you pay nothing.

## Two models, two jobs

1. **Your main chat model** - answers everyday messages. *You pick this* during `mika
   setup`. This is where almost all spend goes, so the choice is yours: cheap and fast,
   or smart and pricier.


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

The local dashboard and Discord bot API have no Mika usage charge. A Klipy key may be
needed for optional GIF, sticker, or clip search; check that provider's current terms.
