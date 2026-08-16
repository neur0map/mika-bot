"""Conservative structural and lexical social-invitation planning."""

from __future__ import annotations

import re

from mika.conversation.context import SelectedContext
from mika.conversation.contracts import ConversationEnvelope
from mika.conversation.participation.contracts import ParticipationDecision

_PRIVATE_LOGISTICS = re.compile(
    r"\b(?:message|dm|call|text|send) (?:me|you)|\b(?:the )?(?:address|file|link)\b",
    re.I,
)
_EXPLICIT_MEDIA = re.compile(r"\b(?:send|post|drop|find|give).{0,40}\b(?:gif|sticker|clip)\b", re.I)
_ROOM_INVITATION = re.compile(
    r"\b(?:anyone|everybody|everyone|you all|y'all|what do (?:you|we) think)\b", re.I
)
_COMFORT = re.compile(
    r"\b(?:rough day|was (?:honestly )?rough|feeling (?:pretty )?(?:alone|awful|bad)|"
    r"tried hard.{0,30}(?:failed|didn't work)|I(?:'m| am) (?:sad|upset))\b",
    re.I,
)
_CALLBACK = re.compile(r"\b(?:remember|again|saga|energy|not the .+ again)\b", re.I)
_SOCIAL_MEDIA_REPLY = re.compile(
    r"\b(?:literally (?:you|me)|me when|actual footage|energy|this is (?:us|you|me))\b", re.I
)
_CELEBRATION = re.compile(
    r"\b(?:I got the|finally (?:shipped|passed|landed|finished)|we are so back|it worked)\b", re.I
)
_PUNCHLINE = re.compile(
    r"\b(?:with witnesses|works on (?:his|my) machine|handcrafted bug|speedrun|"
    r"deleted the (?:bug|feature)|meeting about meetings)\b|\b(?:lol|lmao|lmfao|bruh)\b",
    re.I,
)


class ParticipationPlanner:
    """Choose whether a turn merits generation without pretending certainty."""

    def plan(
        self, envelope: ConversationEnvelope, context: SelectedContext
    ) -> ParticipationDecision:
        """Return a conservative candidate mode using visible social signals."""
        text = envelope.text.strip()
        rules = (
            self._empty,
            self._private_logistics,
            self._direct,
            self._explicit_media,
            self._room_invitation,
            self._comfort,
            self._referenced_media,
            self._callback,
            self._celebration,
            self._punchline,
        )
        for rule in rules:
            decision = rule(envelope, context, text)
            if decision is not None:
                return decision
        return ParticipationDecision("observe", "no_social_invitation", 0.75)

    @staticmethod
    def _empty(
        envelope: ConversationEnvelope, context: SelectedContext, text: str
    ) -> ParticipationDecision | None:
        if not text and not envelope.visual_inputs:
            return ParticipationDecision("observe", "empty_turn", 1.0)
        return None

    @staticmethod
    def _private_logistics(
        envelope: ConversationEnvelope, context: SelectedContext, text: str
    ) -> ParticipationDecision | None:
        if _PRIVATE_LOGISTICS.search(text) and not envelope.mentioned:
            return ParticipationDecision("observe", "private_logistics", 0.95)
        return None

    @staticmethod
    def _direct(
        envelope: ConversationEnvelope, context: SelectedContext, text: str
    ) -> ParticipationDecision | None:
        if envelope.mentioned:
            return ParticipationDecision("reply", "direct_address", 1.0)
        return None

    @staticmethod
    def _explicit_media(
        envelope: ConversationEnvelope, context: SelectedContext, text: str
    ) -> ParticipationDecision | None:
        if _EXPLICIT_MEDIA.search(text):
            return ParticipationDecision("media", "explicit_media_request", 1.0)
        return None

    @staticmethod
    def _room_invitation(
        envelope: ConversationEnvelope, context: SelectedContext, text: str
    ) -> ParticipationDecision | None:
        if _ROOM_INVITATION.search(text):
            return ParticipationDecision("reply", "room_invitation", 0.9)
        return None

    @staticmethod
    def _comfort(
        envelope: ConversationEnvelope, context: SelectedContext, text: str
    ) -> ParticipationDecision | None:
        if _COMFORT.search(text):
            return ParticipationDecision("reply", "support_opportunity", 0.78)
        return None

    @staticmethod
    def _referenced_media(
        envelope: ConversationEnvelope, context: SelectedContext, text: str
    ) -> ParticipationDecision | None:
        if envelope.referenced is not None and envelope.referenced.media:
            if _SOCIAL_MEDIA_REPLY.search(text):
                return ParticipationDecision("react", "reply_to_media_bit", 0.88)
            return ParticipationDecision("observe", "directed_media_reply", 0.8)
        return None

    @staticmethod
    def _callback(
        envelope: ConversationEnvelope, context: SelectedContext, text: str
    ) -> ParticipationDecision | None:
        if _CALLBACK.search(text):
            has_history = bool(context.history)
            return ParticipationDecision("reply", "callback", 0.84 if has_history else 0.7)
        return None

    @staticmethod
    def _celebration(
        envelope: ConversationEnvelope, context: SelectedContext, text: str
    ) -> ParticipationDecision | None:
        if _CELEBRATION.search(text):
            return ParticipationDecision("react", "celebration", 0.86)
        return None

    @staticmethod
    def _punchline(
        envelope: ConversationEnvelope, context: SelectedContext, text: str
    ) -> ParticipationDecision | None:
        if _PUNCHLINE.search(text):
            return ParticipationDecision("react", "punchline", 0.8)
        return None
