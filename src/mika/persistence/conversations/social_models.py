"""ORM records for explicit user facts and feedback on Mika's messages."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from mika.persistence.base import Base


class UserFact(Base):
    """One explicit, replaceable fact scoped to a Discord user."""

    __tablename__ = "conversation_user_facts"
    __table_args__ = (UniqueConstraint("user_id", "fact_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(32), index=True)
    fact_key: Mapped[str] = mapped_column(String(64))
    fact_value: Mapped[str] = mapped_column(Text)
    source_message_id: Mapped[str] = mapped_column(String(32))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ReactionFeedback(Base):
    """A normalized human reaction to one visible Mika message."""

    __tablename__ = "conversation_reaction_feedback"
    __table_args__ = (UniqueConstraint("message_id", "reactor_id", "emoji"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    message_id: Mapped[str] = mapped_column(String(32), index=True)
    channel_id: Mapped[str] = mapped_column(String(32), index=True)
    reactor_id: Mapped[str] = mapped_column(String(32))
    emoji: Mapped[str] = mapped_column(String(64))
    signal: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
