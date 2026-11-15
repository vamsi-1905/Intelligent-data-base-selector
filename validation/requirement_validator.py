
REQUIREMENT_FIELDS = {
    "application_type",
    "expected_users",
    "latency",
    "scalability",
    "cost",
    "security",
    "vector_search",
    "transactions",
    "availability",
    "ai_integration",
    "storage_capacity",
}

CRITERION_MAPPING = {
    "latency": "Latency",
    "scalability": "Scalability",
    "cost": "Cost",
    "security": "Security",
    "vector_search": "Vector Search",
    "transactions": "Transactions",
    "availability": "Availability",
    "ai_integration": "AI Integration",
    "storage_capacity": "Storage Capacity",
}


def validate_requirements(data: dict) -> dict:
    if not isinstance(data, dict):
        raise ValueError("Requirements must be a JSON object.")

    if set(data.keys()) != REQUIREMENT_FIELDS:
        missing = REQUIREMENT_FIELDS - set(data.keys())
        extra = set(data.keys()) - REQUIREMENT_FIELDS
        raise ValueError(
            f"Invalid fields. Missing: {missing}; extra: {extra}"
        )

    if not isinstance(data["application_type"], str):
        raise ValueError("application_type must be a string.")

    data["application_type"] = data["application_type"].strip()

    if not data["application_type"]:
        raise ValueError("application_type cannot be empty.")

    users = data["expected_users"]

    if users is not None:
        if type(users) is not int or users < 0:
            raise ValueError(
                "expected_users must be a non-negative integer or null."
            )

    for field in CRITERION_MAPPING:
        value = data[field]

        if value is not None:
            if type(value) is not int or not 1 <= value <= 10:
                raise ValueError(
                    f"{field} must be an integer from 1 to 10 or null."
                )

    return data
