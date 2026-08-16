"""Task-scoped tool exposure decisions."""

from __future__ import annotations

import re

from mika.conversation.contracts import ConversationEnvelope
from mika.conversation.participation import ParticipationDecision
from mika.conversation.tools.contracts import ToolPlan

_CURRENT_FACT = re.compile(
    r"\b(?:today|current|latest|news|weather|forecast|score|standings|price|release|"
    r"who won|when did|right now)\b",
    re.I,
)


class ToolPlanner:
    """Expose only tools justified by the visible turn and participation mode."""

    def plan(
        self, envelope: ConversationEnvelope, participation: ParticipationDecision
    ) -> ToolPlan:
        """Return a stable, minimal eligibility plan."""
        if participation.mode == "observe":
            return ToolPlan((), "observing")
        if participation.mode == "media":
            return ToolPlan(("media_search",), "media_candidate")
        if _CURRENT_FACT.search(envelope.text):
            return ToolPlan(("web_search",), "current_fact")
        return ToolPlan((), "no_tool_needed")
