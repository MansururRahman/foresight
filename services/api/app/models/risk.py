import uuid
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, Numeric, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import RiskOrigin, pg_enum


class Risk(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "risks"
    __table_args__ = (
        CheckConstraint("length(statement) BETWEEN 3 AND 500", name="risks_statement_len"),
        CheckConstraint("duplicate_of IS NULL OR duplicate_of <> id", name="risks_not_self_dup"),
        CheckConstraint(
            "(origin = 'surprise') = (session_id IS NULL)", name="risks_surprise_no_session"
        ),
        CheckConstraint(
            "origin <> 'surprise' OR duplicate_of IS NULL", name="risks_surprise_no_dup"
        ),
        Index("risks_session_idx", "session_id"),
        Index("risks_project_idx", "project_id"),
        Index("risks_canonical_idx", "session_id", postgresql_where=text("duplicate_of IS NULL")),
        Index("risks_ws_origin_idx", "workspace_id", "origin"),
        Index("risks_tags_gin", "tags", postgresql_using="gin"),
        Index(
            "risks_statement_trgm_gin",
            "statement",
            postgresql_using="gin",
            postgresql_ops={"statement": "gin_trgm_ops"},
        ),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("premortem_sessions.id", ondelete="CASCADE")
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    origin: Mapped[RiskOrigin] = mapped_column(
        pg_enum(RiskOrigin, "risk_origin"), nullable=False, default=RiskOrigin.participant
    )
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    submitted_statement: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, default=list, server_default="{}"
    )
    duplicate_of: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("risks.id", ondelete="SET NULL")
    )
    source_risk_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("risks.id", ondelete="SET NULL")
    )

    # Frozen at seal time (NULL before seal, NULL after seal when no votes).
    agg_vote_count: Mapped[int | None] = mapped_column(Integer)
    agg_mean_probability: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    agg_median_probability: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    agg_probability_stddev: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    agg_mean_impact: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    agg_risk_score: Mapped[Decimal | None] = mapped_column(Numeric(6, 3))
