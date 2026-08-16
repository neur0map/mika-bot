"""Visible action planning and cooldown behavior."""

from __future__ import annotations

from mika.ai.llm.turn import MediaChoice, MikaTurn
from mika.conversation.actions import ActionContext, ActionPlanner, ExecutionResult


def context(*, direct: bool = False) -> ActionContext:
    return ActionContext("c1", mentioned=direct, direct_question=direct)


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
