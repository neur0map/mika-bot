"""Visible action planning and cooldown behavior."""

from __future__ import annotations

from mika.ai.llm.turn import MediaChoice, MikaTurn
from mika.conversation.actions import ActionContext, ActionPlanner, ExecutionResult


def context(*, direct: bool = False, participation_reason: str = "") -> ActionContext:
    return ActionContext(
        "c1",
        mentioned=direct,
        direct_question=direct,
        participation_reason=participation_reason,
    )


def test_planner_preserves_reaction_only_candidate() -> None:
    plan = ActionPlanner().plan(
        MikaTurn("", reactions=("😂",), intent="joke", confidence=0.8),
        context(),
        now=10.0,
    )

    assert plan.reply == ""
    assert plan.reactions == ("😂",)
    assert plan.media is None
    assert plan.silence_reason is None


def test_direct_silence_is_recovered_as_short_reply() -> None:
    plan = ActionPlanner().plan(
        MikaTurn("", intent="silence", confidence=0.8),
        context(direct=True),
        now=10.0,
    )

    assert plan.reply == "i hit a snag—try me again in a sec."
    assert plan.silence_reason is None


def test_reaction_cooldown_does_not_suppress_media() -> None:
    planner = ActionPlanner()
    first = planner.plan(MikaTurn("", reactions=("😂",), intent="joke"), context(), now=10.0)
    planner.record_visible(
        first,
        ExecutionResult(None, ("😂",), None, ()),
        channel_id="c1",
        now=10.0,
    )

    second = planner.plan(
        MikaTurn("", reactions=("🔥",), media=MediaChoice("gif", "victory"), intent="hype"),
        context(),
        now=15.0,
    )

    assert second.reactions == ()
    assert second.media is not None
    assert second.media.query == "victory"


def test_true_silence_carries_reason() -> None:
    plan = ActionPlanner().plan(MikaTurn("", intent="silence"), context(), now=10.0)

    assert plan.is_silent
    assert plan.silence_reason == "model_silence"


def test_strong_proactive_moments_get_media_when_model_omits_it() -> None:
    celebration = ActionPlanner().plan(
        MikaTurn("we are so back", intent="hype", confidence=0.9),
        context(participation_reason="proactive_media_celebration"),
        now=10.0,
    )
    developer_joke = ActionPlanner().plan(
        MikaTurn("of course it does", intent="joke", confidence=0.9),
        context(participation_reason="proactive_media_punchline"),
        now=10.0,
    )

    assert celebration.media is not None
    assert celebration.media.query == "celebration hype reaction"
    assert developer_joke.media is not None
    assert developer_joke.media.query == "developer joke reaction"
