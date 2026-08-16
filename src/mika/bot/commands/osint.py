"""Open-source intelligence helpers: public profile, DNS, RDAP, CVE, IP, UA, email."""

from __future__ import annotations

import asyncio
import re
from typing import Any

from discord import Interaction, app_commands

from mika.bot.commands import helpers
from mika.core.logging import get_logger

logger = get_logger(__name__)

_SHERLOCK_SITES: tuple[tuple[str, str], ...] = (
    ("GitHub", "https://github.com/{u}"),
    ("Twitter", "https://twitter.com/{u}"),
    ("Instagram", "https://instagram.com/{u}"),
    ("Reddit", "https://reddit.com/user/{u}"),
    ("TikTok", "https://tiktok.com/@{u}"),
    ("Twitch", "https://twitch.tv/{u}"),
    ("YouTube", "https://youtube.com/@{u}"),
    ("Pinterest", "https://pinterest.com/{u}"),
    ("Steam", "https://steamcommunity.com/id/{u}"),
    ("Medium", "https://medium.com/@{u}"),
    ("SoundCloud", "https://soundcloud.com/{u}"),
    ("DevTo", "https://dev.to/{u}"),
    ("GitLab", "https://gitlab.com/{u}"),
    ("Keybase", "https://keybase.io/{u}"),
    ("Flickr", "https://flickr.com/people/{u}"),
    ("AboutMe", "https://about.me/{u}"),
)

_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")

_BROWSERS: tuple[tuple[str, str], ...] = (
    ("Edge", "Edg/"),
    ("Opera", "OPR/"),
    ("Chrome", "Chrome/"),
    ("Firefox", "Firefox/"),
    ("Safari", "Safari/"),
    ("Internet Explorer", "MSIE"),
)

_OPERATING_SYSTEMS: tuple[tuple[str, str], ...] = (
    ("Windows", "Windows"),
    ("iOS", "iPhone"),
    ("iPadOS", "iPad"),
    ("macOS", "Mac OS X"),
    ("Android", "Android"),
    ("Linux", "Linux"),
)


async def _probe(label: str, url: str) -> tuple[str, str, bool]:
    """Return (label, url, found) for one public profile candidate."""
    try:
        await helpers.fetch_text(url)
    except Exception:
        return label, url, False
    return label, url, True


def _detect(ua: str, table: tuple[tuple[str, str], ...]) -> str:
    """First label whose token is in the user-agent, else 'unknown'."""
    for label, token in table:
        if token in ua:
            return label
    return "unknown"


def setup(tree: app_commands.CommandTree[Any]) -> None:
    """Register the OSINT commands."""

    @tree.command(
        name="sherlock",
        description="Educational: probe public profile pages for a username.",
    )
    @app_commands.describe(username="public username to look for across known sites")
    async def sherlock(interaction: Interaction, username: str) -> None:
        await interaction.response.defer()
        try:
            probes = [_probe(label, tpl.format(u=username)) for label, tpl in _SHERLOCK_SITES]
            results = await asyncio.gather(*probes)
            found = [(label, url) for label, url, ok in results if ok]
            if not found:
                await interaction.followup.send("no public profiles reachable for that name")
                return
            body = "\n".join(f"[{label}]({url})" for label, url in found)
            await interaction.followup.send(
                embed=helpers.embed(f"public profiles for {username}", helpers.clip(body))
            )
        except Exception as error:
            logger.warning("sherlock failed: %s", error)
            await interaction.followup.send("couldn't run the public profile sweep")

    @tree.command(
        name="dns",
        description="Resolve DNS records via the public Google DoH endpoint.",
    )
    @app_commands.describe(domain="domain name", record="record type, e.g. A, AAAA, MX, TXT")
    async def dns(interaction: Interaction, domain: str, record: str = "A") -> None:
        await interaction.response.defer()
        try:
            data = await helpers.fetch_json(
                f"https://dns.google/resolve?name={domain}&type={record}"
            )
            answers = data.get("Answer") or []
            entries = [str(item.get("data")) for item in answers if item.get("data")]
            body = "\n".join(entries) if entries else "no records returned"
            await interaction.followup.send(
                embed=helpers.embed(f"{record} {domain}", helpers.clip(body))
            )
        except Exception as error:
            logger.warning("dns lookup failed: %s", error)
            await interaction.followup.send("couldn't resolve that name")

    @tree.command(
        name="whois",
        description="RDAP lookup of public domain registration data.",
    )
    @app_commands.describe(domain="domain name")
    async def whois(interaction: Interaction, domain: str) -> None:
        await interaction.response.defer()
        try:
            data = await helpers.fetch_json(f"https://rdap.org/domain/{domain}")
            handle = str(data.get("handle") or data.get("ldhName") or domain)
            embed = helpers.embed(f"RDAP {domain}", handle)
            for event in data.get("events") or []:
                action = str(event.get("eventAction") or "event")
                when = str(event.get("eventDate") or "n/a")
                embed.add_field(name=action, value=when, inline=False)
            await interaction.followup.send(embed=embed)
        except Exception as error:
            logger.warning("whois lookup failed: %s", error)
            await interaction.followup.send("couldn't reach RDAP for that domain")

    @tree.command(
        name="cve",
        description="Look up a CVE record from a public vulnerability feed.",
    )
    @app_commands.describe(cve_id="CVE identifier, e.g. CVE-2021-44228")
    async def cve(interaction: Interaction, cve_id: str) -> None:
        await interaction.response.defer()
        try:
            data = await helpers.fetch_json(f"https://cve.circl.lu/api/cve/{cve_id}")
            summary = str(data.get("summary") or "no summary available")
            score = str(data.get("cvss") or "n/a")
            embed = helpers.embed(cve_id, helpers.clip(summary))
            embed.add_field(name="CVSS", value=score)
            await interaction.followup.send(embed=embed)
        except Exception as error:
            logger.warning("cve lookup failed: %s", error)
            await interaction.followup.send("couldn't find that CVE")

    @tree.command(
        name="ipinfo",
        description="Look up public geolocation and ASN data for an IP address.",
    )
    @app_commands.describe(ip="IPv4 or IPv6 address to inspect")
    async def ipinfo(interaction: Interaction, ip: str) -> None:
        await interaction.response.defer()
        try:
            data = await helpers.fetch_json(f"http://ip-api.com/json/{ip}")
            embed = helpers.embed(f"ip lookup {ip}")
            for field in ("country", "city", "isp", "org", "as"):
                embed.add_field(name=field, value=str(data.get(field) or "n/a"), inline=False)
            await interaction.followup.send(embed=embed)
        except Exception as error:
            logger.warning("ipinfo lookup failed: %s", error)
            await interaction.followup.send("couldn't look up that ip")

    @tree.command(
        name="useragent",
        description="Parse a User-Agent string locally (no network calls).",
    )
    @app_commands.describe(ua="raw User-Agent header value")
    async def useragent(interaction: Interaction, ua: str) -> None:
        browser = _detect(ua, _BROWSERS)
        platform = _detect(ua, _OPERATING_SYSTEMS)
        embed = helpers.embed("user-agent", helpers.clip(ua))
        embed.add_field(name="browser", value=browser)
        embed.add_field(name="os", value=platform)
        await helpers.send(interaction, embed=embed)

    @tree.command(
        name="emailcheck",
        description="Validate an email address format locally (no network calls).",
    )
    @app_commands.describe(email="email address to validate")
    async def emailcheck(interaction: Interaction, email: str) -> None:
        valid = _EMAIL_RE.match(email) is not None
        domain = email.rsplit("@", 1)[-1] if "@" in email else "n/a"
        embed = helpers.embed("email check", helpers.clip(email))
        embed.add_field(name="valid", value="yes" if valid else "no")
        embed.add_field(name="domain", value=domain)
        await helpers.send(interaction, embed=embed)
