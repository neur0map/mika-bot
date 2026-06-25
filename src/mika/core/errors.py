"""Typed error hierarchy. Catch these; never use a bare `except Exception`."""

from __future__ import annotations


class MikaError(Exception):
    """Base class for every error raised by Mika."""


class ConfigError(MikaError):
    """Invalid or missing configuration."""


class ProviderError(MikaError):
    """An LLM provider call failed."""


class PersistenceError(MikaError):
    """A database or storage operation failed."""


class FeatureError(MikaError):
    """A feature module failed in a recoverable way."""
