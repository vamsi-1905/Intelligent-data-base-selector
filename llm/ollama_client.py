import json
import time

from groq import RateLimitError
from llm.groq_utils import FallbackClient, rate_limit_message
from llm.prompts import SYSTEM_PROMPT

MODEL = "openai/gpt-oss-20b"

REQUIREMENTS_SCHEMA = {
    "type": "object",
    "properties": {
        "application_type": {"type": "string"},
        "expected_users": {"type": ["integer", "null"]},
        "latency": {"type": ["integer", "null"]},
        "scalability": {"type": ["integer", "null"]},
        "cost": {"type": ["integer", "null"]},
        "security": {"type": ["integer", "null"]},
        "vector_search": {"type": ["integer", "null"]},
        "transactions": {"type": ["integer", "null"]},
        "availability": {"type": ["integer", "null"]},
        "ai_integration": {"type": ["integer", "null"]},
        "storage_capacity": {"type": ["integer", "null"]},
    },
    "required": [
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
    ],
    "additionalProperties": False,
}


def extract_requirements(user_text: str) -> dict:
    if not isinstance(user_text, str) or not user_text.strip():
        raise ValueError("Enter an application description.")

    if len(user_text) > 3000:
        raise ValueError("Description must be 3000 characters or fewer.")

    client = FallbackClient(timeout=60.0)
    start = time.perf_counter()

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        SYSTEM_PROMPT
                        + "\nReturn every required field. Use null when "
                        "unspecified. Importance scores must be integers "
                        "from 1 to 10."
                    ),
                },
                {"role": "user", "content": user_text},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "application_requirements",
                    "strict": True,
                    "schema": REQUIREMENTS_SCHEMA,
                },
            },
            temperature=0,
            max_completion_tokens=1000,
            reasoning_effort="low",
            reasoning_format="hidden",
        )
    except RateLimitError as exc:
        raise RuntimeError(rate_limit_message(exc)) from exc
    except Exception as exc:
        raise RuntimeError(f"Groq requirement extraction failed: {exc}") from exc

    print(
        f"[Groq] Requirement extraction: "
        f"{time.perf_counter() - start:.2f}s",
        flush=True,
    )

    content = response.choices[0].message.content
    if not content:
        raise ValueError("The model returned an empty response.")

    try:
        result = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError("The model returned invalid JSON.") from exc

    expected_fields = set(REQUIREMENTS_SCHEMA["required"])

    if not isinstance(result, dict) or set(result) != expected_fields:
        raise ValueError("The model returned an unexpected requirements schema.")

    if not result["application_type"].strip():
        raise ValueError("Application type cannot be empty.")

    for field in expected_fields - {"application_type", "expected_users"}:
        value = result[field]
        if value is not None and (
            isinstance(value, bool)
            or not isinstance(value, int)
            or not 1 <= value <= 10
        ):
            raise ValueError(f"Invalid importance score for {field}.")

    users = result["expected_users"]
    if users is not None and (
        isinstance(users, bool)
        or not isinstance(users, int)
        or users < 0
    ):
        raise ValueError("Expected users must be a non-negative integer or null.")

    return result


if __name__ == "__main__":
    sample = (
        "A RAG chatbot for 50000 users requiring fast vector search "
        "and high scalability."
    )
    print(json.dumps(extract_requirements(sample), indent=2))