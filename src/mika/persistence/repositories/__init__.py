"""Data-access repositories. One file per aggregate; the only place queries run."""

from __future__ import annotations

from mika.persistence.repositories.messages import MessageRepository

__all__ = ["MessageRepository"]
