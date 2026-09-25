import uuid

from sqlalchemy import text

from app import seed
from app.services.calibration import brier_unchecked
from app.services.calibration_queries import load_predictions


async def test_seed_builds_a_graded_history(db_session):
    users = {
        "ada@demo.local": uuid.uuid4(),
        "grace@demo.local": uuid.uuid4(),
        "linus@demo.local": uuid.uuid4(),
    }
    ws_id = await seed.seed_database(db_session, users, rng_seed=42)
    assert ws_id is not None

    n_projects = await db_session.scalar(
        text("select count(*) from projects where workspace_id = :ws"), {"ws": ws_id}
    )
    n_closed = await db_session.scalar(
        text("select count(*) from projects where workspace_id = :ws and status = 'closed'"),
        {"ws": ws_id},
    )
    n_sealed = await db_session.scalar(
        text(
            "select count(*) from premortem_sessions where workspace_id = :ws and phase = 'sealed'"
        ),
        {"ws": ws_id},
    )
    n_collect = await db_session.scalar(
        text(
            "select count(*) from premortem_sessions where workspace_id = :ws and phase = 'collect'"
        ),
        {"ws": ws_id},
    )
    n_graded_rows = await db_session.scalar(
        text("select count(*) from graded_predictions where workspace_id = :ws"), {"ws": ws_id}
    )
    n_surprises = await db_session.scalar(
        text("select count(*) from risks where workspace_id = :ws and origin = 'surprise'"),
        {"ws": ws_id},
    )
    fully_graded = await db_session.scalar(
        text(
            "select count(*) from premortem_sessions where workspace_id = :ws and fully_graded_at is not null"
        ),
        {"ws": ws_id},
    )
    assert n_projects == 5 and n_closed == 4
    assert n_sealed == 4 and n_collect == 1
    assert fully_graded == 4
    assert n_graded_rows >= 90  # 4 projects x 8 risks x 3 voters = 96
    assert 4 <= n_surprises <= 8

    ada = await load_predictions(db_session, ws_id, users["ada@demo.local"])
    grace = await load_predictions(db_session, ws_id, users["grace@demo.local"])
    linus = await load_predictions(db_session, ws_id, users["linus@demo.local"])
    assert len(ada) == len(grace) == len(linus) == 32
    assert brier_unchecked(ada) < brier_unchecked(grace)
    assert brier_unchecked(ada) < brier_unchecked(linus)

    # Aggregates were frozen on every canonical risk of the sealed sessions.
    missing_agg = await db_session.scalar(
        text(
            "select count(*) from risks r join premortem_sessions s on s.id = r.session_id "
            "where s.workspace_id = :ws and s.phase = 'sealed' and r.duplicate_of is null and r.agg_mean_probability is null"
        ),
        {"ws": ws_id},
    )
    assert missing_agg == 0


async def test_seed_is_idempotent(db_session):
    users = {
        "ada@demo.local": uuid.uuid4(),
        "grace@demo.local": uuid.uuid4(),
        "linus@demo.local": uuid.uuid4(),
    }
    first = await seed.seed_database(db_session, users, rng_seed=42)
    second = await seed.seed_database(db_session, users, rng_seed=42)
    assert first == second
    n = await db_session.scalar(text("select count(*) from workspaces where slug = 'demo'"))
    assert n == 1
