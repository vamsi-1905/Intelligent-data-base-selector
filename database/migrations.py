"""Schema upgrades and catalog seeding, safe to run on every start."""

from database.connection import get_connection
from database.seed_catalog import seed

MIGRATIONS = [
    "ALTER TABLE database_criteria_scores ADD COLUMN IF NOT EXISTS reasoning TEXT;",
    "ALTER TABLE database_criteria_scores ADD COLUMN IF NOT EXISTS source_url TEXT;",
    "ALTER TABLE database_criteria_scores ADD COLUMN IF NOT EXISTS origin VARCHAR(20);",
    "ALTER TABLE database_criteria_scores ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP;",
]


def ensure_catalog():
    conn = get_connection()
    try:
        with conn:
            with conn.cursor() as cur:
                for statement in MIGRATIONS:
                    cur.execute(statement)
                seed(cur)
    finally:
        conn.close()