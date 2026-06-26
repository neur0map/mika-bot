"""Dashboard: a polished read-only overview of the bot, its commands and config."""

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
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Segoe UI',system-ui,sans-serif;background:#0d0e16;color:#e8e9f0;
 background-image:radial-gradient(1200px 600px at 80% -10%,#2a1d54 0,transparent 60%),
 radial-gradient(900px 500px at -10% 10%,#13294b 0,transparent 55%);min-height:100vh}
.wrap{max-width:1080px;margin:0 auto;padding:3rem 1.25rem 4rem}
.hero{display:flex;align-items:center;gap:1rem;margin-bottom:2rem}
.dot{width:14px;height:14px;border-radius:50%;background:#39d98a;box-shadow:0 0 14px #39d98a}
.hero h1{font-size:2.2rem;font-weight:700;letter-spacing:-.5px}
.hero span{color:#9aa0b4;font-size:.95rem}
.grid{display:grid;gap:1rem}
.stats{grid-template-columns:repeat(auto-fit,minmax(150px,1fr));margin-bottom:2rem}
.card{background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.08);
 border-radius:16px;padding:1.1rem 1.25rem;backdrop-filter:blur(6px)}
.card .big{font-size:1.9rem;font-weight:700;background:linear-gradient(90deg,#a78bfa,#60a5fa);
 -webkit-background-clip:text;background-clip:text;color:transparent}
.card .lbl{color:#9aa0b4;font-size:.82rem;text-transform:uppercase;letter-spacing:.06em;margin-top:.2rem}
h2{font-size:1.05rem;font-weight:600;margin:2rem 0 .9rem;color:#c7cbe0}
.groups{grid-template-columns:repeat(auto-fill,minmax(220px,1fr))}
.grp{background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.07);border-radius:14px;padding:.9rem 1rem}
.grp .top{display:flex;justify-content:space-between;align-items:baseline}
.grp .nm{font-weight:600;color:#dfe2f0}.grp .ct{color:#a78bfa;font-weight:700;font-size:.9rem}
.grp .ds{color:#8c92a8;font-size:.82rem;margin-top:.25rem;line-height:1.35}
table{width:100%;border-collapse:collapse;background:rgba(255,255,255,.03);border-radius:14px;overflow:hidden}
td{padding:.7rem 1rem;border-bottom:1px solid rgba(255,255,255,.06);font-size:.92rem}
td:first-child{color:#9aa0b4;width:40%}tr:last-child td{border-bottom:none}
.pill{display:inline-block;padding:.15rem .6rem;border-radius:999px;font-size:.8rem;font-weight:600}
.on{background:rgba(57,217,138,.15);color:#39d98a}.off{background:rgba(255,255,255,.07);color:#9aa0b4}
.foot{color:#6b7088;font-size:.82rem;margin-top:2.5rem;line-height:1.6}
a{color:#a78bfa}
"""


def _toggle(value: bool) -> str:
    return '<span class="pill on">on</span>' if value else '<span class="pill off">off</span>'


@router.get("/", response_class=HTMLResponse)
async def dashboard() -> str:
    """Render the dashboard."""
    data = _status()
    cards = (
        f'<div class="card"><div class="big">{data["commands"]}</div><div class="lbl">commands</div></div>'
        f'<div class="card"><div class="big">{len(data["groups"])}</div><div class="lbl">groups</div></div>'
        f'<div class="card"><div class="big">{data["memory"]}</div><div class="lbl">memory</div></div>'
    )
    groups = "".join(
        f'<div class="grp"><div class="top"><span class="nm">/{g["name"]}</span>'
        f'<span class="ct">{g["count"]}</span></div><div class="ds">{g["description"]}</div></div>'
        for g in data["groups"]
    )
    config = (
        f"<tr><td>AI model</td><td>{data['model']}</td></tr>"
        f"<tr><td>Web search</td><td>{_toggle(data['web_search'])}</td></tr>"
        f"<tr><td>GIF search</td><td>{_toggle(data['gif_search'])}</td></tr>"
        f"<tr><td>Memory</td><td>{data['memory']}</td></tr>"
    )
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{data["name"]} dashboard</title><style>{_STYLE}</style></head><body><div class="wrap">
<div class="hero"><span class="dot"></span><div><h1>{data["name"]}</h1>
<span>{data["commands"]} commands across {len(data["groups"])} groups - running</span></div></div>
<div class="grid stats">{cards}</div>
<h2>Configuration</h2><table>{config}</table>
<h2>Command groups</h2><div class="grid groups">{groups}</div>
<div class="foot">Set up per-server features with the slash commands (e.g. <code>/greet</code>,
<code>/antispam</code>, <code>/ticket</code>). Change AI keys and the persona with
<code>mika setup</code>. To open this dashboard to the internet safely, see
<a href="https://github.com/neur0map/mika-bot/blob/main/docs/EXPOSE.md">docs/EXPOSE.md</a>.</div>
</div></body></html>"""


@router.get("/api/status")
async def api_status() -> dict[str, Any]:
    """Machine-readable bot status."""
    return _status()


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}
