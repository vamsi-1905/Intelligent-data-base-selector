
import os

import psycopg2
import pandas as pd
from psycopg2.extras import RealDictCursor


def get_connection():
    """Open a connection to the project PostgreSQL database."""
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME", "intelligent_db_selector"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.environ["DB_PASSWORD"],
        connect_timeout=5,
    )


def get_database_capabilities():
    """Retrieve database capability scores using SQL."""
    query = """
        SELECT
            ds.database_id,
            ds.name AS database_name,
            c.criterion_id,
            c.name AS criterion,
            c.weight,
            dcs.score,
            dcs.evidence
        FROM database_systems AS ds
        JOIN database_criteria_scores AS dcs
            ON ds.database_id = dcs.database_id
        JOIN criteria AS c
            ON c.criterion_id = dcs.criterion_id
        WHERE ds.is_active = TRUE
        ORDER BY ds.name, c.criterion_id;
    """

    with get_connection() as conn:
        return pd.read_sql_query(query, conn)


if __name__ == "__main__":
    try:
        data = get_database_capabilities()
        print("Database connection successful!")
        print(f"Rows retrieved: {len(data)}")
        print(data.head(10).to_string(index=False))
    except Exception as exc:
        print(f"Database connection failed: {exc}")
