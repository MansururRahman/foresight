"""leads: design-partner applications from the landing page

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
TS = sa.DateTime(timezone=True)
NOW = sa.func.now()


def _enum(name: str) -> postgresql.ENUM:
    return postgresql.ENUM(name=name, create_type=False)


def upgrade() -> None:
    op.execute("CREATE TYPE lead_team_size AS ENUM ('1-10', '11-50', '51-200', '200+')")
    op.execute("CREATE TYPE lead_status AS ENUM ('new', 'contacted', 'accepted', 'declined')")
    op.create_table(
        "leads",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("email", postgresql.CITEXT(), nullable=False, unique=True),
        sa.Column("company", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("team_size", _enum("lead_team_size"), nullable=False),
        sa.Column("story", sa.Text(), nullable=True),
        sa.Column("source", sa.Text(), nullable=True),
        sa.Column("status", _enum("lead_status"), nullable=False, server_default="new"),
        sa.Column("created_at", TS, nullable=False, server_default=NOW),
        sa.Column("updated_at", TS, nullable=False, server_default=NOW),
        sa.CheckConstraint("length(name) BETWEEN 1 AND 120", name="leads_name_len"),
        sa.CheckConstraint("length(company) BETWEEN 1 AND 160", name="leads_company_len"),
        sa.CheckConstraint("length(role) BETWEEN 1 AND 120", name="leads_role_len"),
        sa.CheckConstraint("story IS NULL OR length(story) <= 2000", name="leads_story_len"),
        sa.CheckConstraint("source IS NULL OR length(source) <= 100", name="leads_source_len"),
    )


def downgrade() -> None:
    op.drop_table("leads")
    op.execute("DROP TYPE IF EXISTS lead_status")
    op.execute("DROP TYPE IF EXISTS lead_team_size")
