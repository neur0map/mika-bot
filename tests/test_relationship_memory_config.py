"""Safe relationship-memory runtime configuration."""

from mika.bot import client
from mika.core.config import MemorySettings


def test_runtime_policy_uses_configured_dm_visibility_and_truthful_semantics(monkeypatch) -> None:
    class RuntimeSettings:
        memory = MemorySettings(
            _env_file=None,
            relationship_direct_message_enabled=False,
            relationship_semantic_scoring_enabled=True,
        )

    def runtime_settings() -> RuntimeSettings:
        return RuntimeSettings()

    monkeypatch.setattr(client, "get_settings", runtime_settings)

    policy = client._relationship_policy()

    assert policy.visibility_rules["direct_message"] is False
    assert policy.semantic_retrieval_enabled is False


def test_relationship_memory_defaults_to_disabled_shadow_mode() -> None:
    settings = MemorySettings(_env_file=None)

    assert settings.relationship_learning_enabled is False
    assert settings.relationship_provider_extraction_enabled is False
    assert settings.relationship_semantic_scoring_enabled is False
    assert settings.relationship_direct_message_enabled is True
    assert settings.relationship_shadow_mode is True
    assert settings.relationship_batch_size > 0
    assert settings.relationship_consolidation_interval_seconds > 0


def test_relationship_learning_can_be_explicitly_disabled() -> None:
    settings = MemorySettings(_env_file=None, relationship_learning_enabled=False)

    assert settings.relationship_learning_enabled is False
