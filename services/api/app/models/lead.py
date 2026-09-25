from sqlalchemy import Text
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import LeadStatus, LeadTeamSize, pg_enum


class Lead(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A design-partner application from the public landing page."""

    __tablename__ = "leads"

    name: Mapped[str] = mapped_column(Text, nullable=False)
    email: Mapped[str] = mapped_column(CITEXT(), unique=True, nullable=False)
    company: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    team_size: Mapped[LeadTeamSize] = mapped_column(
        pg_enum(LeadTeamSize, "lead_team_size"), nullable=False
    )
    story: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(Text)
    status: Mapped[LeadStatus] = mapped_column(
        pg_enum(LeadStatus, "lead_status"),
        nullable=False,
        default=LeadStatus.new,
        server_default=LeadStatus.new.value,
    )
