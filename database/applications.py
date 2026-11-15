
from database.connection import get_connection
from validation.requirement_validator import CRITERION_MAPPING


def save_application(description: str, requirements: dict) -> int:
    """Save an application and its known requirements."""

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO applications (
                    application_type,
                    description,
                    expected_users
                )
                VALUES (%s, %s, %s)
                RETURNING application_id;
                """,
                (
                    requirements["application_type"],
                    description,
                    requirements["expected_users"],
                ),
            )

            application_id = cur.fetchone()[0]

            for field, criterion_name in CRITERION_MAPPING.items():
                importance = requirements[field]

                # Unknown priorities are omitted rather than invented.
                if importance is None:
                    continue

                cur.execute(
                    """
                    INSERT INTO application_requirements (
                        application_id,
                        criterion_id,
                        importance
                    )
                    SELECT %s, criterion_id, %s
                    FROM criteria
                    WHERE name = %s;
                    """,
                    (application_id, importance, criterion_name),
                )

        return application_id
