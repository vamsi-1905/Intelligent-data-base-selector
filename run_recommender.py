
from llm.ollama_client import extract_requirements
from validation.requirement_validator import validate_requirements
from database.applications import save_application
from decision_engine.weighted_sum import recommend


def main():
    description = input(
        "Describe your AI application: "
    ).strip()

    if not description:
        print("Please enter a description.")
        return

    print("\n1. Extracting requirements with GPT-OSS 20B...")
    raw_requirements = extract_requirements(description)

    print("2. Validating requirements...")
    requirements = validate_requirements(raw_requirements)

    print("3. Saving application to PostgreSQL...")
    application_id = save_application(description, requirements)

    print(f"   Application ID: {application_id}")

    print("4. Calculating WSM recommendations...")
    rankings = recommend(application_id)

    print("\nDATABASE RECOMMENDATIONS")
    print("=" * 48)

    for rank, item in enumerate(rankings, start=1):
        print(
            f"{rank}. {item['database_name']}: "
            f"{item['score']:.3f}/10"
        )

    print("\nRecommendations saved to PostgreSQL.")


if __name__ == "__main__":
    main()
