import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import SessionPhase, pg_enum


class PremortemSession(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "premortem_sessions"
    __table_args__ = (
        CheckConstraint(
            "(phase = 'sealed') = (sealed_at IS NOT NULL)", name="sessions_sealed_consistency"
        ),
        Index("premortem_sessions_ws_idx", "workspace_id", "phase"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    created_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    facilitator_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    phase: Mapped[SessionPhase] = mapped_column(
        pg_enum(SessionPhase, "session_phase"), nullable=False, default=SessionPhase.collect
    )
    phase_changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    sealed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fully_graded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SessionParticipant(Base):
    __tablename__ = "session_participants"
    __table_args__ = (Index("session_participants_user_idx", "user_id"),)

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("premortem_sessions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True
    )
    added_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
