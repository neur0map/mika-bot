"""Safe relationship-memory runtime configuration."""

from mika.core.config import MemorySettings


def test_relationship_memory_defaults_to_disabled_shadow_mode() -> None:
    settings = MemorySettings(_env_file=None)

    assert settings.relationship_learning_enabled is False
    assert settings.relationship_provider_extraction_enabled is False
    assert settings.relationship_semantic_scoring_enabled is False
    assert settings.relationship_shadow_mode is True
    assert settings.relationship_batch_size > 0
    assert settings.relationship_consolidation_interval_seconds > 0


def test_relationship_learning_can_be_explicitly_disabled() -> None:
    settings = MemorySettings(_env_file=None, relationship_learning_enabled=False)

    assert settings.relationship_learning_enabled is False
