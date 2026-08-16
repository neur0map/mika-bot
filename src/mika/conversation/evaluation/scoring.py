"""Deterministic, offline scoring for visible benchmark outcomes."""

from __future__ import annotations

from mika.conversation.evaluation.cases import HiddenExpectations, VisibleTurn


def score_turn(turn: VisibleTurn, expected: HiddenExpectations) -> tuple[float, tuple[str, ...]]:
    """Return a normalized score and stable failure codes."""
    checks: list[bool] = []
    failures: list[str] = []
    actions = turn.normalized_actions
    participated = bool(actions)

    participation_ok = participated == expected.participate
    checks.append(participation_ok)
    if not participation_ok:
        failures.append("unexpected_participation" if participated else "missing_participation")

    invalid = tuple(action for action in actions if action not in expected.allowed_actions)
    checks.append(not invalid)
    failures.extend(f"disallowed_action:{action}" for action in invalid)

    length_ok = len(turn.reply) <= expected.max_reply_chars
    checks.append(length_ok)
    if not length_ok:
        failures.append("reply_too_long")

    matched = tuple(
        phrase
        for phrase in expected.forbidden_phrases
        if phrase.casefold() in turn.reply.casefold()
    )
    checks.append(not matched)
    failures.extend(f"forbidden_phrase:{phrase}" for phrase in matched)

    if expected.expected_tool is not None:
        tool_ok = bool(turn.used_tools) == expected.expected_tool
        checks.append(tool_ok)
        if not tool_ok:
            failure = "missing_expected_tool" if expected.expected_tool else "unexpected_tool"
            failures.append(failure)

    if expected.expected_media_context is not None:
        media_ok = turn.used_media_context == expected.expected_media_context
        checks.append(media_ok)
        if not media_ok:
            failures.append("media_context_mismatch")

    score = sum(checks) / len(checks) if checks else 1.0
    return round(score, 4), tuple(sorted(failures))
