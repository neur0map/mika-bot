"""Natural-expression distribution benchmark."""

from mika.conversation.evaluation.expression_benchmark import compare_style
from mika.conversation.skills.natural_expression.human_style import analyze_messages


def test_human_like_candidate_passes_distribution_gates() -> None:
    human = analyze_messages(
        ["hey", "no way", "what happened", "okay 😭", "i know", "that worked", "sure", "fine"]
    )
    candidate = analyze_messages(
        ["hey", "no way", "what happened", "okay 😂", "i know", "that worked", "sure", "fine"]
    )

    report = compare_style(human, candidate)

    assert report.passed
    assert report.failures == ()


def test_bot_like_candidate_fails_emoji_dash_length_and_sentence_gates() -> None:
    human = analyze_messages(["hey", "no way", "what happened", "okay", "i know"])
    candidate = analyze_messages(
        [
            "yeah — that was certainly quite an unexpectedly wild outcome 😏. truly remarkable.",
            "nah — you really managed to do that again 😏. impressive work.",
        ]
    )

    report = compare_style(human, candidate)

    assert not report.passed
    assert {failure.split(":", 1)[0] for failure in report.failures} >= {
        "median_words",
        "emoji_rate",
        "em_dash_rate",
        "multi_sentence_rate",
    }
