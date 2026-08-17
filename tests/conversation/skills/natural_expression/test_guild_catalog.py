"""Guild emoji identity, profiling, and eligibility."""

from mika.conversation.skills.natural_expression.guild_catalog import (
    GuildEmojiCatalog,
    GuildEmojiDescriptor,
)
from mika.conversation.skills.natural_expression.visual_profile import VisualProfiler


def test_snowflake_identity_survives_rename_and_preserves_description() -> None:
    catalog = GuildEmojiCatalog()
    catalog.sync("g", [GuildEmojiDescriptor("123", "old_name", False, True, ())])
    catalog.set_description("g", "123", "skeptical face", "skepticism", 0.8)
    catalog.sync("g", [GuildEmojiDescriptor("123", "new_name", False, True, ())])

    profile = catalog.profiles("g")[0]
    assert profile.value == "<:new_name:123>"
    assert profile.description == "skeptical face"
    assert profile.family == "skepticism"


def test_unavailable_or_role_restricted_emoji_are_not_candidates() -> None:
    catalog = GuildEmojiCatalog()
    catalog.sync(
        "g",
        [
            GuildEmojiDescriptor("1", "gone", False, False, ()),
            GuildEmojiDescriptor("2", "staff", True, True, ("role",)),
        ],
    )

    assert catalog.profiles("g") == ()
    assert catalog.profiles("g", role_ids=("role",))[0].value == "<a:staff:2>"


def test_visual_fallback_treats_name_as_weak_readable_evidence() -> None:
    evidence = VisualProfiler().describe("side_eye_laugh", animated=True)

    assert evidence.description == "side eye laugh"
    assert evidence.confidence < 0.5
    assert evidence.animated
