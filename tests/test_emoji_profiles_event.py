"""Discord custom emoji metadata adaptation."""

from types import SimpleNamespace

from mika.bot.events.emoji_profiles import descriptors


def test_discord_emoji_are_reduced_to_stable_descriptors() -> None:
    emoji = SimpleNamespace(
        id=123,
        name="face",
        animated=True,
        available=True,
        roles=[SimpleNamespace(id=9)],
    )

    assert descriptors([emoji])[0].emoji_id == "123"
    assert descriptors([emoji])[0].role_ids == ("9",)
