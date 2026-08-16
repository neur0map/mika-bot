"""ORM models for conversation turn traces."""

from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from mika.persistence.base import Base


class StoredTurnTrace(Base):
    """A persisted trace header and its ordered stages."""

    __tablename__ = "conversation_turn_traces"

    trace_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    message_id: Mapped[str] = mapped_column(String(32), index=True)
    channel_id: Mapped[str] = mapped_column(String(32), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    stages: Mapped[list[StoredStageTrace]] = relationship(
        back_populates="trace",
        cascade="all, delete-orphan",
        order_by="StoredStageTrace.position",
        lazy="selectin",
    )


class StoredStageTrace(Base):
    """One ordered stage belonging to a persisted turn trace."""

    __tablename__ = "conversation_stage_traces"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trace_id: Mapped[str] = mapped_column(
        ForeignKey("conversation_turn_traces.trace_id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(Integer)
    stage: Mapped[str] = mapped_column(String(64))
    outcome: Mapped[str] = mapped_column(String(64))
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[float] = mapped_column(Float)
    details_json: Mapped[str] = mapped_column(Text, default="{}")
    trace: Mapped[StoredTurnTrace] = relationship(back_populates="stages")

    @property
    def details(self) -> dict[str, object]:
        """Return the stored diagnostic details as a mapping."""
        value = json.loads(self.details_json)
        return value if isinstance(value, dict) else {}
