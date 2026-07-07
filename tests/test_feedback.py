"""Learning feedback normalization."""

from __future__ import annotations

from mika.ai.learning.feedback import reaction_signal


def test_reaction_signal_maps_common_feedback() -> None:
    assert reaction_signal("👍") == "positive"
    assert reaction_signal("💀") == "laugh"
    assert reaction_signal("🤔") == "confused"
    assert reaction_signal("👎") == "negative"
    assert reaction_signal("🫠") == "other"
