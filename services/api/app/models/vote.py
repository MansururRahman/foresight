import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Index, SmallInteger, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Vote(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "votes"
    __table_args__ = (
        UniqueConstraint("risk_id", "user_id", name="votes_risk_user_key"),
        CheckConstraint("probability BETWEEN 0 AND 100", name="votes_probability_range"),
        CheckConstraint("impact BETWEEN 1 AND 5", name="votes_impact_range"),
        Index("votes_session_user_idx", "session_id", "user_id"),
        Index("votes_ws_user_idx", "workspace_id", "user_id"),
    )

    risk_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("risks.id", ondelete="CASCADE"), nullable=False
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("premortem_sessions.id", ondelete="CASCADE"), nullable=False
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    probability: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    impact: Mapped[int] = mapped_column(SmallInteger, nullable=False)
