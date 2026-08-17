"""Runtime provider extraction trust boundaries."""

from datetime import UTC, datetime

from mika.bot.client import _ProviderExtractor
from mika.conversation.relationships.contracts import RelationDecision
from mika.conversation.relationships.service import ObservationInput


class Client:
    def __init__(self) -> None:
        self.calls = 0

    async def summarize(self, instruction: str, content: str) -> str:
        self.calls += 1
        return (
            '[{"kind":"preference","key":"game","value":"Hades",'
            '"evidence_class":"explicit","confidence":0.99,"reason":"provider"}]'
        )


class InvalidClient(Client):
    async def summarize(self, instruction: str, content: str) -> str:
        self.calls += 1
        return "not json"


def observation(text: str) -> ObservationInput:
    return ObservationInput(
        "discord", "1", "1", "user", text, datetime.now(UTC), "guild", "guild", "channel"
    )


async def test_provider_claims_are_inference_only_and_sensitive_text_is_rejected() -> None:
    client = Client()
    extractor = _ProviderExtractor(client)  # type: ignore[arg-type]

    proposals = await extractor.extract(
        observation("I like Hades"), RelationDecision("follow_up", 0.5, "test")
    )
    sensitive = await extractor.extract(
        observation("I was diagnosed with ADHD"), RelationDecision("follow_up", 0.5, "test")
    )

    assert proposals[0].evidence_class == "inference"
    assert proposals[0].confidence <= 0.6
    assert sensitive == ()
    assert client.calls == 1


async def test_invalid_provider_output_marks_deterministic_fallback() -> None:
    extractor = _ProviderExtractor(InvalidClient())  # type: ignore[arg-type]

    proposals = await extractor.extract(
        observation("I like Hades"), RelationDecision("follow_up", 0.5, "test")
    )

    assert proposals
    assert proposals[0].reason.startswith("provider_fallback:invalid_output:")
