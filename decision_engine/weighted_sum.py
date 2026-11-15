
import sys

from database.connection import get_connection


def recommend(application_id: int) -> list[dict]:
    """
    Rank candidate databases using a requirement-weighted
    Weighted Sum Model.

    Capability scores range from 1 to 10.
    User importance values determine the relative weights.
    """

    query = """
        SELECT
            ds.database_id,
            ds.name AS database_name,
            c.name AS criterion,
            dcs.score AS capability_score,
            ar.importance
        FROM application_requirements ar
        JOIN criteria c
            ON c.criterion_id = ar.criterion_id
        JOIN database_criteria_scores dcs
            ON dcs.criterion_id = c.criterion_id
        JOIN database_systems ds
            ON ds.database_id = dcs.database_id
        WHERE ar.application_id = %s
          AND ds.is_active = TRUE
        ORDER BY ds.database_id, c.criterion_id;
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (application_id,))
            rows = cur.fetchall()

    if not rows:
        raise ValueError(
            f"No requirements or capability scores found "
            f"for application ID {application_id}."
        )

    # Each database accumulates its weighted capability scores.
    totals = {}
    weight_sum = 0.0
    seen_criteria = set()

    for database_id, name, criterion, score, importance in rows:
        if criterion not in seen_criteria:
            seen_criteria.add(criterion)
            weight_sum += float(importance)

        if database_id not in totals:
            totals[database_id] = {
                "database_id": database_id,
                "database_name": name,
                "weighted_sum": 0.0,
            }

        totals[database_id]["weighted_sum"] += (
            float(score) * float(importance)
        )

    if weight_sum <= 0:
        raise ValueError("The total requirement importance must be positive.")

    results = []

    for item in totals.values():
        # Normalize by total importance so the result is on a 1–10 scale.
        final_score = item["weighted_sum"] / weight_sum

        results.append({
            "database_id": item["database_id"],
            "database_name": item["database_name"],
            "score": final_score,
        })

    results.sort(key=lambda x: x["score"], reverse=True)

    # Store this run's ranked recommendations in PostgreSQL.
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM recommendations
                WHERE application_id = %s AND method = 'WSM';
                """,
                (application_id,),
            )

            for rank, item in enumerate(results, start=1):
                explanation = (
                    f"Weighted Sum score: {item['score']:.3f}/10. "
                    f"Based on {len(seen_criteria)} specified criteria."
                )

                cur.execute(
                    """
                    INSERT INTO recommendations (
                        application_id,
                        database_id,
                        method,
                        score,
                        rank,
                        explanation
                    )
                    VALUES (%s, %s, 'WSM', %s, %s, %s);
                    """,
                    (
                        application_id,
                        item["database_id"],
                        item["score"],
                        rank,
                        explanation,
                    ),
                )

    return results


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python -m decision_engine.weighted_sum APPLICATION_ID")
        sys.exit(1)

    try:
        application_id = int(sys.argv[1])
        rankings = recommend(application_id)

        print(f"\nWSM rankings for application {application_id}\n")
        print(f"{'Rank':<6}{'Database':<20}{'Score / 10':>12}")
        print("-" * 38)

        for rank, item in enumerate(rankings, start=1):
            print(
                f"{rank:<6}"
                f"{item['database_name']:<20}"
                f"{item['score']:>12.3f}"
            )

        print("\nRecommendations saved to PostgreSQL.")

    except (ValueError, TypeError) as exc:
        print(f"Error: {exc}")
        sys.exit(1)
    except Exception as exc:
        print(f"Unexpected error: {exc}")
        sys.exit(1)
