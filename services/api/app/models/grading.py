import uuid

from sqlalchemy import ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import GradingOutcome, pg_enum


class Grading(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "gradings"
    __table_args__ = (Index("gradings_project_idx", "project_id"),)

    risk_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("risks.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    graded_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    outcome: Mapped[GradingOutcome] = mapped_column(
        pg_enum(GradingOutcome, "grading_outcome"), nullable=False
    )
    note: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
