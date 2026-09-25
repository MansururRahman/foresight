"""domain: workspaces, projects, sessions, risks, votes, gradings, graded_predictions view

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)
TS = sa.DateTime(timezone=True)
NOW = sa.func.now()


def _enum(name: str) -> postgresql.ENUM:
    return postgresql.ENUM(name=name, create_type=False)


def upgrade() -> None:
    op.execute("CREATE TYPE workspace_role AS ENUM ('owner', 'admin', 'member')")
    op.execute("CREATE TYPE project_status AS ENUM ('planning', 'active', 'closed')")
    op.execute("CREATE TYPE session_phase AS ENUM ('collect', 'merge', 'vote', 'sealed')")
    op.execute("CREATE TYPE risk_origin AS ENUM ('participant', 'suggestion', 'surprise')")
    op.execute("CREATE TYPE grading_outcome AS ENUM ('yes', 'no', 'partial')")

    op.create_table(
        "workspaces",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("slug", postgresql.CITEXT(), nullable=False, unique=True),
        sa.Column("created_by", UUID, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", TS, nullable=False, server_default=NOW),
        sa.Column("updated_at", TS, nullable=False, server_default=NOW),
        sa.CheckConstraint("length(name) BETWEEN 1 AND 120", name="workspaces_name_len"),
    )

    op.create_table(
        "workspace_members",
        sa.Column(
            "workspace_id",
            UUID,
            sa.ForeignKey("workspaces.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("role", _enum("workspace_role"), nullable=False, server_default="member"),
        sa.Column("created_at", TS, nullable=False, server_default=NOW),
        sa.Column("updated_at", TS, nullable=False, server_default=NOW),
    )
    op.create_index("workspace_members_user_idx", "workspace_members", ["user_id"])

    op.create_table(
        "projects",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "workspace_id", UUID, sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("tags", postgresql.ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("planned_start", sa.Date()),
        sa.Column("planned_end", sa.Date()),
        sa.Column("status", _enum("project_status"), nullable=False, server_default="planning"),
        sa.Column("activated_at", TS),
        sa.Column("closed_at", TS),
        sa.Column("closed_by", UUID, sa.ForeignKey("users.id")),
        sa.Column("archived_at", TS),
        sa.Column("created_by", UUID, sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "search_text",
            sa.Text(),
            sa.Computed("title || ' ' || description", persisted=True),
            nullable=False,
        ),
        sa.Column("created_at", TS, nullable=False, server_default=NOW),
        sa.Column("updated_at", TS, nullable=False, server_default=NOW),
        sa.CheckConstraint("length(title) BETWEEN 1 AND 200", name="projects_title_len"),
        sa.CheckConstraint(
            "planned_end IS NULL OR planned_start IS NULL OR planned_end >= planned_start",
            name="projects_planned_order",
        ),
        sa.CheckConstraint(
            "(status = 'closed') = (closed_at IS NOT NULL)", name="projects_closed_consistency"
        ),
    )
    op.create_index(
        "projects_ws_status_idx", "projects", ["workspace_id", "status", sa.text("created_at DESC")]
    )
    op.create_index("projects_tags_gin", "projects", ["tags"], postgresql_using="gin")
    op.create_index(
        "projects_search_trgm_gin",
        "projects",
        ["search_text"],
        postgresql_using="gin",
        postgresql_ops={"search_text": "gin_trgm_ops"},
    )

    op.create_table(
        "premortem_sessions",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "project_id",
            UUID,
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "workspace_id", UUID, sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("created_by", UUID, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("facilitator_id", UUID, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("phase", _enum("session_phase"), nullable=False, server_default="collect"),
        sa.Column("phase_changed_at", TS, nullable=False, server_default=NOW),
        sa.Column("sealed_at", TS),
        sa.Column("fully_graded_at", TS),
        sa.Column("created_at", TS, nullable=False, server_default=NOW),
        sa.Column("updated_at", TS, nullable=False, server_default=NOW),
        sa.CheckConstraint(
            "(phase = 'sealed') = (sealed_at IS NOT NULL)", name="sessions_sealed_consistency"
        ),
    )
    op.create_index("premortem_sessions_ws_idx", "premortem_sessions", ["workspace_id", "phase"])

    op.create_table(
        "session_participants",
        sa.Column(
            "session_id",
            UUID,
            sa.ForeignKey("premortem_sessions.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("added_by", UUID, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", TS, nullable=False, server_default=NOW),
    )
    op.create_index("session_participants_user_idx", "session_participants", ["user_id"])

    op.create_table(
        "risks",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "project_id", UUID, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("session_id", UUID, sa.ForeignKey("premortem_sessions.id", ondelete="CASCADE")),
        sa.Column(
            "workspace_id", UUID, sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("author_id", UUID, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("origin", _enum("risk_origin"), nullable=False, server_default="participant"),
        sa.Column("statement", sa.Text(), nullable=False),
        sa.Column("submitted_statement", sa.Text(), nullable=False),
        sa.Column("tags", postgresql.ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("duplicate_of", UUID, sa.ForeignKey("risks.id", ondelete="SET NULL")),
        sa.Column("source_risk_id", UUID, sa.ForeignKey("risks.id", ondelete="SET NULL")),
        sa.Column("agg_vote_count", sa.Integer()),
        sa.Column("agg_mean_probability", sa.Numeric(5, 2)),
        sa.Column("agg_median_probability", sa.Numeric(5, 2)),
        sa.Column("agg_probability_stddev", sa.Numeric(5, 2)),
        sa.Column("agg_mean_impact", sa.Numeric(3, 2)),
        sa.Column("agg_risk_score", sa.Numeric(6, 3)),
        sa.Column("created_at", TS, nullable=False, server_default=NOW),
        sa.Column("updated_at", TS, nullable=False, server_default=NOW),
        sa.CheckConstraint("length(statement) BETWEEN 3 AND 500", name="risks_statement_len"),
        sa.CheckConstraint("duplicate_of IS NULL OR duplicate_of <> id", name="risks_not_self_dup"),
        sa.CheckConstraint(
            "(origin = 'surprise') = (session_id IS NULL)", name="risks_surprise_no_session"
        ),
        sa.CheckConstraint(
            "origin <> 'surprise' OR duplicate_of IS NULL", name="risks_surprise_no_dup"
        ),
    )
    op.create_index("risks_session_idx", "risks", ["session_id"])
    op.create_index("risks_project_idx", "risks", ["project_id"])
    op.create_index(
        "risks_canonical_idx",
        "risks",
        ["session_id"],
        postgresql_where=sa.text("duplicate_of IS NULL"),
    )
    op.create_index("risks_ws_origin_idx", "risks", ["workspace_id", "origin"])
    op.create_index("risks_tags_gin", "risks", ["tags"], postgresql_using="gin")
    op.create_index(
        "risks_statement_trgm_gin",
        "risks",
        ["statement"],
        postgresql_using="gin",
        postgresql_ops={"statement": "gin_trgm_ops"},
    )

    op.create_table(
        "votes",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("risk_id", UUID, sa.ForeignKey("risks.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "session_id",
            UUID,
            sa.ForeignKey("premortem_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "workspace_id", UUID, sa.ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("probability", sa.SmallInteger(), nullable=False),
        sa.Column("impact", sa.SmallInteger(), nullable=False),
        sa.Column("created_at", TS, nullable=False, server_default=NOW),
        sa.Column("updated_at", TS, nullable=False, server_default=NOW),
        sa.UniqueConstraint("risk_id", "user_id", name="votes_risk_user_key"),
        sa.CheckConstraint("probability BETWEEN 0 AND 100", name="votes_probability_range"),
        sa.CheckConstraint("impact BETWEEN 1 AND 5", name="votes_impact_range"),
    )
    op.create_index("votes_session_user_idx", "votes", ["session_id", "user_id"])
    op.create_index("votes_ws_user_idx", "votes", ["workspace_id", "user_id"])

    op.create_table(
        "gradings",
        sa.Column("id", UUID, primary_key=True),
        sa.Column(
            "risk_id",
            UUID,
            sa.ForeignKey("risks.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "project_id", UUID, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("graded_by", UUID, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("outcome", _enum("grading_outcome"), nullable=False),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", TS, nullable=False, server_default=NOW),
        sa.Column("updated_at", TS, nullable=False, server_default=NOW),
    )
    op.create_index("gradings_project_idx", "gradings", ["project_id"])

    op.execute(
        """
        CREATE VIEW graded_predictions AS
        SELECT
          v.id                                  AS vote_id,
          v.workspace_id,
          v.user_id,
          v.session_id,
          r.project_id,
          r.id                                  AS risk_id,
          v.probability,
          v.probability / 100.0                 AS p,
          CASE g.outcome WHEN 'yes' THEN 1.0 WHEN 'partial' THEN 0.5 ELSE 0.0 END AS o,
          g.outcome,
          v.impact,
          COALESCE(NULLIF(r.tags, '{}'::text[]), pr.tags) AS tags,
          pr.closed_at
        FROM votes v
        JOIN risks r     ON r.id = v.risk_id AND r.duplicate_of IS NULL
        JOIN gradings g  ON g.risk_id = r.id
        JOIN projects pr ON pr.id = r.project_id AND pr.archived_at IS NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS graded_predictions")
    for table in (
        "gradings",
        "votes",
        "risks",
        "session_participants",
        "premortem_sessions",
        "projects",
        "workspace_members",
        "workspaces",
    ):
        op.drop_table(table)
    for enum_name in (
        "grading_outcome",
        "risk_origin",
        "session_phase",
        "project_status",
        "workspace_role",
    ):
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")
