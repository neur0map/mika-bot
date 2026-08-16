"""Search developer registries and the web: GitHub, npm, PyPI, xkcd and more."""

from __future__ import annotations

from typing import Any

from discord import Interaction, app_commands

from mika.bot.commands import helpers
from mika.core.logging import get_logger

logger = get_logger(__name__)


def setup(tree: app_commands.CommandTree[Any]) -> None:
    """Register the search commands."""

    @tree.command(name="github", description="Look up a GitHub user.")
    @app_commands.describe(user="GitHub username")
    async def github(interaction: Interaction, user: str) -> None:
        await interaction.response.defer()
        try:
            data = await helpers.fetch_json(f"https://api.github.com/users/{user}")
            embed = helpers.embed(str(data.get("name") or user), str(data.get("bio") or ""))
            embed.add_field(name="Repos", value=str(data.get("public_repos", 0)))
            embed.add_field(name="Followers", value=str(data.get("followers", 0)))
            if data.get("avatar_url"):
                embed.set_thumbnail(url=str(data["avatar_url"]))
            await interaction.followup.send(embed=embed)
        except Exception as error:
            logger.warning("github lookup failed: %s", error)
            await interaction.followup.send("couldn't find that user")

    @tree.command(name="githubrepo", description="Look up a GitHub repository (owner/name).")
    @app_commands.describe(repo="owner/name")
    async def githubrepo(interaction: Interaction, repo: str) -> None:
        await interaction.response.defer()
        try:
            data = await helpers.fetch_json(f"https://api.github.com/repos/{repo}")
            embed = helpers.embed(
                str(data.get("full_name") or repo), str(data.get("description") or "")
            )
            embed.add_field(name="Stars", value=str(data.get("stargazers_count", 0)))
            embed.add_field(name="Forks", value=str(data.get("forks_count", 0)))
            embed.add_field(name="Language", value=str(data.get("language") or "n/a"))
            await interaction.followup.send(embed=embed)
        except Exception as error:
            logger.warning("repo lookup failed: %s", error)
            await interaction.followup.send("couldn't find that repository")

    @tree.command(name="npm", description="Look up an npm package.")
    @app_commands.describe(package="package name")
    async def npm(interaction: Interaction, package: str) -> None:
        await interaction.response.defer()
        try:
            data = await helpers.fetch_json(f"https://registry.npmjs.org/{package}")
            latest = str(data.get("dist-tags", {}).get("latest", "?"))
            description = str(data.get("description") or "")
            await interaction.followup.send(
                embed=helpers.embed(f"{package} v{latest}", helpers.clip(description))
            )
        except Exception as error:
            logger.warning("npm lookup failed: %s", error)
            await interaction.followup.send("couldn't find that package")

    @tree.command(name="pypi", description="Look up a PyPI package.")
    @app_commands.describe(package="package name")
    async def pypi(interaction: Interaction, package: str) -> None:
        await interaction.response.defer()
        try:
            data = await helpers.fetch_json(f"https://pypi.org/pypi/{package}/json")
            info = data.get("info", {})
            version = str(info.get("version", "?"))
            summary = str(info.get("summary") or "")
            await interaction.followup.send(
                embed=helpers.embed(f"{package} {version}", helpers.clip(summary))
            )
        except Exception as error:
            logger.warning("pypi lookup failed: %s", error)
            await interaction.followup.send("couldn't find that package")

    @tree.command(name="xkcd", description="Show an xkcd comic (latest, or by number).")
    @app_commands.describe(number="comic number (0 for the latest)")
    async def xkcd(interaction: Interaction, number: int = 0) -> None:
        await interaction.response.defer()
        url = (
            "https://xkcd.com/info.0.json"
            if number <= 0
            else f"https://xkcd.com/{number}/info.0.json"
        )
        try:
            data = await helpers.fetch_json(url)
            embed = helpers.embed(str(data.get("title") or "xkcd"))
            if data.get("img"):
                embed.set_image(url=str(data["img"]))
            await interaction.followup.send(embed=embed)
        except Exception as error:
            logger.warning("xkcd failed: %s", error)
            await interaction.followup.send("couldn't fetch that comic")

    @tree.command(name="hackernews", description="Show the current top Hacker News story.")
    async def hackernews(interaction: Interaction) -> None:
        await interaction.response.defer()
        try:
            top = await helpers.fetch_json("https://hacker-news.firebaseio.com/v0/topstories.json")
            story_id = top[0]
            item = await helpers.fetch_json(
                f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json"
            )
            title = str(item.get("title") or "story")
            link = str(item.get("url") or f"https://news.ycombinator.com/item?id={story_id}")
            await interaction.followup.send(f"**{title}**\n{link}")
        except Exception as error:
            logger.warning("hackernews failed: %s", error)
            await interaction.followup.send("couldn't reach Hacker News")

    @tree.command(name="reddit", description="Show the top post from a subreddit today.")
    @app_commands.describe(subreddit="subreddit name (without r/)")
    async def reddit(interaction: Interaction, subreddit: str) -> None:
        await interaction.response.defer()
        try:
            data = await helpers.fetch_json(
                f"https://www.reddit.com/r/{subreddit}/top.json", limit=1, t="day"
            )
            post = data["data"]["children"][0]["data"]
            title = str(post.get("title") or "post")
            permalink = str(post.get("permalink") or "")
            await interaction.followup.send(f"**{title}**\nhttps://reddit.com{permalink}")
        except Exception as error:
            logger.warning("reddit failed: %s", error)
            await interaction.followup.send("couldn't reach that subreddit")

    @tree.command(name="country", description="Look up basic facts about a country.")
    @app_commands.describe(name="country name")
    async def country(interaction: Interaction, name: str) -> None:
        await interaction.response.defer()
        try:
            data = await helpers.fetch_json(f"https://restcountries.com/v3.1/name/{name}")
            entry = data[0]
            capital = ", ".join(entry.get("capital", [])) if entry.get("capital") else "n/a"
            embed = helpers.embed(str(entry["name"]["common"]))
            embed.add_field(name="Capital", value=str(capital))
            embed.add_field(name="Region", value=str(entry.get("region") or "n/a"))
            embed.add_field(name="Population", value=str(entry.get("population", 0)))
            await interaction.followup.send(embed=embed)
        except Exception as error:
            logger.warning("country lookup failed: %s", error)
            await interaction.followup.send("couldn't find that country")
