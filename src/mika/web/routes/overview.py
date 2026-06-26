"""Dashboard: a read-only control panel for the bot, its commands and config."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import discord
from discord import app_commands
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from mika.bot.commands import register_all
from mika.core.config import get_settings

router = APIRouter()


@lru_cache(maxsize=1)
def _command_stats() -> tuple[int, list[tuple[str, str, int]]]:
    client = discord.Client(intents=discord.Intents.none())
    tree = app_commands.CommandTree(client)
    register_all(tree)
    total = 0
    groups: list[tuple[str, str, int]] = []
    for command in tree.get_commands():
        if isinstance(command, app_commands.Group):
            count = sum(
                1 for sub in command.walk_commands() if isinstance(sub, app_commands.Command)
            )
            groups.append((command.name, command.description, count))
            total += count
        else:
            total += 1
    return total, sorted(groups)


def _status() -> dict[str, Any]:
    settings = get_settings()
    total, groups = _command_stats()
    return {
        "name": settings.persona.name,
        "commands": total,
        "groups": [{"name": n, "description": d, "count": c} for n, d, c in groups],
        "model": settings.llm.model,
        "memory": "honcho + local" if settings.memory.honcho_enabled else "local",
        "web_search": settings.tools.web_search_enabled,
        "gif_search": bool(settings.media.klipy_api_key),
    }


_STYLE = """
*{margin:0;padding:0;box-sizing:border-box}
:root{--paper:#e8e3d5;--ink:#1a1813;--accent:#d23a1f;--muted:#6f6857;--cell:#efe9db;--green:#3a7d4a}
html,body{background:var(--paper);color:var(--ink)}
body{font-family:ui-monospace,"SF Mono","Cascadia Mono","Liberation Mono",Menlo,Consolas,monospace;
 font-size:14px;line-height:1.5;-webkit-text-size-adjust:100%}
a{color:inherit}
b{color:var(--accent)}
.mast{background:var(--ink);color:var(--paper);padding:clamp(1.3rem,3.5vw,2.4rem) clamp(1rem,4vw,3rem);
 display:flex;justify-content:space-between;align-items:flex-end;gap:1.5rem;flex-wrap:wrap}
.mast .id{display:flex;flex-direction:column;align-items:flex-start;gap:.55rem}
.mast h1{font-size:clamp(2.3rem,7vw,4.2rem);font-weight:800;line-height:.85;letter-spacing:-.04em;
 text-transform:uppercase;display:flex;align-items:center}
.cur{display:inline-block;width:.42em;height:.82em;background:var(--accent);margin-left:.14em;
 animation:blink 1.1s steps(1,end) infinite}
@keyframes blink{50%{opacity:0}}
.mast .sub{font-size:.7rem;letter-spacing:.34em;text-transform:uppercase;color:#a89f8a}
.mast .meta{display:flex;flex-direction:column;align-items:flex-end;gap:.4rem;font-size:.7rem;letter-spacing:.14em}
.mast .stat{display:flex;align-items:center;gap:.55rem;font-weight:700;text-transform:uppercase;letter-spacing:.24em}
.sq{width:.6rem;height:.6rem;background:var(--green);display:inline-block}
.mast .addr,.mast .clock{color:#a89f8a;text-transform:uppercase}
nav{display:flex;flex-wrap:wrap;border-bottom:3px solid var(--ink)}
nav a{display:flex;gap:.55rem;align-items:center;text-decoration:none;font-weight:700;font-size:.72rem;
 letter-spacing:.22em;text-transform:uppercase;padding:.9rem clamp(1rem,2.6vw,1.7rem);border-right:2px solid var(--ink)}
nav a:hover{background:var(--ink);color:var(--paper)}
nav a .n{color:var(--accent)}
nav a:hover .n{color:var(--paper)}
section{padding:clamp(1.5rem,4vw,2.8rem) clamp(1rem,4vw,3rem);border-bottom:3px solid var(--ink)}
.h{display:flex;align-items:center;gap:.9rem;margin-bottom:1.4rem}
.h .n{font-weight:800;color:var(--accent);font-size:.95rem}
.h h2{font-size:.85rem;letter-spacing:.3em;text-transform:uppercase;font-weight:700;white-space:nowrap}
.h .rule{flex:1;height:0;border-top:2px solid var(--ink)}
.lede{max-width:74ch;margin-bottom:1.7rem;line-height:1.65}
.lede code,footer code{background:var(--ink);color:var(--paper);padding:.06rem .42rem}
.strip{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));
 border-top:2px solid var(--ink);border-left:2px solid var(--ink)}
.strip .c{border-right:2px solid var(--ink);border-bottom:2px solid var(--ink);padding:1.1rem 1.25rem}
.strip .num{font-size:clamp(1.9rem,4.5vw,2.9rem);font-weight:800;line-height:1;letter-spacing:-.03em}
.strip .lab{margin-top:.6rem;font-size:.64rem;letter-spacing:.22em;text-transform:uppercase;color:var(--muted)}
.cfg{border:2px solid var(--ink);max-width:680px}
.cfg .row{display:flex;justify-content:space-between;align-items:center;gap:1rem;padding:.9rem 1.25rem;
 border-bottom:2px solid var(--ink)}
.cfg .row:last-child{border-bottom:0}
.cfg .k{font-size:.68rem;letter-spacing:.2em;text-transform:uppercase;color:var(--muted)}
.cfg .v{font-weight:700;text-align:right}
.tag{display:inline-block;padding:.08rem .55rem;border:2px solid var(--ink);font-size:.66rem;font-weight:700;
 letter-spacing:.16em;text-transform:uppercase}
.tag.on{background:var(--ink);color:var(--paper)}
.tag.off{color:var(--muted);border-color:var(--muted)}
.idx{display:grid;grid-template-columns:repeat(auto-fill,minmax(232px,1fr));
 border-top:2px solid var(--ink);border-left:2px solid var(--ink)}
.idx .g{border-right:2px solid var(--ink);border-bottom:2px solid var(--ink);padding:.95rem 1.15rem}
.idx .g:hover{background:var(--cell)}
.idx .top{display:flex;justify-content:space-between;align-items:baseline;gap:.6rem}
.idx .nm{font-weight:700;font-size:.96rem}
.idx .ct{font-weight:800;font-size:1.15rem;color:var(--accent)}
.idx .ds{margin-top:.4rem;font-size:.72rem;color:var(--muted);line-height:1.45}
footer{padding:clamp(1.3rem,4vw,2rem) clamp(1rem,4vw,3rem);font-size:.74rem;color:var(--muted);line-height:1.85}
footer a{text-decoration:underline;text-underline-offset:3px}
"""

_SCRIPT = """
<script>
(function(){var c=document.getElementById('clk');if(!c)return;
function p(n){return(n<10?'0':'')+n;}
function t(){var d=new Date();c.textContent=p(d.getHours())+':'+p(d.getMinutes())+':'+p(d.getSeconds());}
t();setInterval(t,1000);})();
</script>
"""


def _toggle(value: bool) -> str:
    return '<span class="tag on">on</span>' if value else '<span class="tag off">off</span>'


@router.get("/", response_class=HTMLResponse)
async def dashboard() -> str:
    """Render the control panel."""
    data = _status()
    mem_short = "HONCHO" if str(data["memory"]).startswith("honcho") else "LOCAL"
    model_short = str(data["model"]).split("/")[-1].upper()
    stat = (
        f'<div class="c"><div class="num">{data["commands"]}</div>'
        f'<div class="lab">Total commands</div></div>'
        f'<div class="c"><div class="num">{len(data["groups"])}</div>'
        f'<div class="lab">Command groups</div></div>'
        f'<div class="c"><div class="num">{mem_short}</div><div class="lab">Memory</div></div>'
        f'<div class="c"><div class="num">{model_short}</div><div class="lab">Chat model</div></div>'
    )
    groups = "".join(
        f'<div class="g"><div class="top"><span class="nm"><b>/</b>{g["name"]}</span>'
        f'<span class="ct">{g["count"]}</span></div><div class="ds">{g["description"]}</div></div>'
        for g in data["groups"]
    )
    config = (
        f'<div class="row"><span class="k">AI model</span><span class="v">{data["model"]}</span></div>'
        f'<div class="row"><span class="k">Web search</span>'
        f'<span class="v">{_toggle(bool(data["web_search"]))}</span></div>'
        f'<div class="row"><span class="k">GIF search</span>'
        f'<span class="v">{_toggle(bool(data["gif_search"]))}</span></div>'
        f'<div class="row"><span class="k">Memory</span><span class="v">{data["memory"]}</span></div>'
    )
    docs = "https://github.com/neur0map/mika-bot/blob/main/docs"
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{data["name"]} - control panel</title><style>{_STYLE}</style></head><body>
<header class="mast" id="top">
<div class="id"><h1>{data["name"]}<i class="cur"></i></h1><div class="sub">Discord bot &middot; control panel</div></div>
<div class="meta"><div class="stat"><i class="sq"></i>Online</div>
<div class="addr">127.0.0.1:8080 &middot; v0.1.0</div><div class="clock" id="clk">--:--:--</div></div>
</header>
<nav><a href="#overview"><span class="n">01</span>Overview</a>
<a href="#config"><span class="n">02</span>Config</a>
<a href="#commands"><span class="n">03</span>Commands</a>
<a href="{docs}/GETTING-STARTED.md"><span class="n">&rarr;</span>Docs</a></nav>
<main>
<section id="overview"><div class="h"><span class="n">01</span><h2>Overview</h2><span class="rule"></span></div>
<p class="lede">Your bot is online and serving <b>{data["commands"]} commands</b> across {len(data["groups"])} groups.
Everything below is live. Configure per-server features with slash commands; change AI keys or the persona
with <code>mika setup</code>.</p>
<div class="strip">{stat}</div></section>
<section id="config"><div class="h"><span class="n">02</span><h2>Configuration</h2><span class="rule"></span></div>
<div class="cfg">{config}</div></section>
<section id="commands"><div class="h"><span class="n">03</span><h2>Command index</h2><span class="rule"></span></div>
<div class="idx">{groups}</div></section>
</main>
<footer>Set up per-server features with their slash commands &mdash; e.g. <code>/greet</code>,
<code>/antispam</code>, <code>/ticket</code>. Open this panel to the internet safely with
<a href="{docs}/EXPOSE.md">docs/EXPOSE.md</a>.</footer>
{_SCRIPT}</body></html>"""


@router.get("/api/status")
async def api_status() -> dict[str, Any]:
    """Machine-readable bot status."""
    return _status()


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}
