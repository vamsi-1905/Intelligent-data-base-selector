"""Shared Groq client with automatic model fallback on rate limits."""

import os
import re
import types

from groq import BadRequestError, Groq, RateLimitError

MODELS = ("openai/gpt-oss-20b", "openai/gpt-oss-120b")


def rate_limit_message(exc) -> str:
    text = str(exc)
    wait = re.search(r"try again in ([0-9hms. ]+)", text)
    when = f" Try again in {wait.group(1).strip()}." if wait else ""
    if "TPD" in text or "per day" in text:
        return (
            "Groq's daily token limit is used up for every fallback model."
            f"{when} A paid Groq tier removes the limit."
        )
    return f"Groq rate limit reached.{when}"


class _Completions:
    def __init__(self, owner):
        self._owner = owner

    def create(self, **kwargs):
        kwargs.pop("model", None)
        return self._owner.create(**kwargs)


class FallbackClient:
    """Drop-in for Groq(): tries each model in turn when one is rate limited."""

    def __init__(self, timeout=60.0, models=MODELS):
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY is not set.")
        self._client = Groq(api_key=api_key, timeout=timeout, max_retries=0)
        self._models = models
        self.chat = types.SimpleNamespace(completions=_Completions(self))

    def _try(self, model, kwargs):
        try:
            return self._client.chat.completions.create(model=model, **kwargs)
        except BadRequestError as exc:
            if "reasoning" not in str(exc).lower():
                raise
            slim = {k: v for k, v in kwargs.items() if k not in ("reasoning_format", "reasoning_effort")}
            return self._client.chat.completions.create(model=model, **slim)

    def create(self, **kwargs):
        last = None
        for model in self._models:
            try:
                return self._try(model, kwargs)
            except RateLimitError as exc:
                last = exc
        raise last