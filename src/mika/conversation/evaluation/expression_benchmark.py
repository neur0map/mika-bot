"""Distribution gates for human-like conversational expression."""

from __future__ import annotations

from dataclasses import dataclass

from mika.conversation.skills.natural_expression.human_style import HumanStyleProfile

_WORD_TOLERANCE = 2
_EMOJI_TOLERANCE = 0.02
_DASH_TOLERANCE = 0.005
_SENTENCE_TOLERANCE = 0.05


@dataclass(frozen=True, slots=True)
class ExpressionBenchmarkReport:
    """Candidate style distances and rollout failures."""

    human: HumanStyleProfile
    candidate: HumanStyleProfile
    failures: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return not self.failures


def compare_style(
    human: HumanStyleProfile, candidate: HumanStyleProfile
) -> ExpressionBenchmarkReport:
    """Compare candidate output with held-out human distribution gates."""
    failures: list[str] = []
    if abs(candidate.median_words - human.median_words) > _WORD_TOLERANCE:
        failures.append(f"median_words:{candidate.median_words}:{human.median_words}")
    if abs(candidate.emoji_rate - human.emoji_rate) > _EMOJI_TOLERANCE:
        failures.append(f"emoji_rate:{candidate.emoji_rate:.4f}:{human.emoji_rate:.4f}")
    if candidate.em_dash_rate > human.em_dash_rate + _DASH_TOLERANCE:
        failures.append(f"em_dash_rate:{candidate.em_dash_rate:.4f}:{human.em_dash_rate:.4f}")
    if candidate.multi_sentence_rate > human.multi_sentence_rate + _SENTENCE_TOLERANCE:
        failures.append(
            "multi_sentence_rate:"
            f"{candidate.multi_sentence_rate:.4f}:{human.multi_sentence_rate:.4f}"
        )
    return ExpressionBenchmarkReport(human, candidate, tuple(failures))
