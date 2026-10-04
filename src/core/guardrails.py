from __future__ import annotations

import json
import logging
from dataclasses import dataclass

import httpx

from src.core.settings import AppSettings

logger = logging.getLogger(__name__)

GROQ_BASE_URL = "https://api.groq.com/openai/v1"


@dataclass(frozen=True)
class GuardrailResult:
    allowed: bool
    reason: str | None = None


def _groq_client(settings: AppSettings) -> httpx.Client | None:
    if not settings.groq_api_key:
        return None
    return httpx.Client(
        base_url=GROQ_BASE_URL,
        headers={"Authorization": f"Bearer {settings.groq_api_key}"},
        timeout=settings.guardrail_timeout_seconds,
    )


def _chat_completion(client: httpx.Client, model: str, messages: list[dict[str, str]]) -> str:
    response = client.post("/chat/completions", json={"model": model, "messages": messages})
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


def check_prompt_injection(question: str, settings: AppSettings) -> GuardrailResult:
    client = _groq_client(settings)
    if client is None:
        return GuardrailResult(allowed=True)

    try:
        with client:
            content = _chat_completion(
                client,
                settings.groq_prompt_guard_model,
                [{"role": "user", "content": question}],
            )
        # Groq returns Prompt Guard's raw malicious-probability score as plain text
        # (e.g. "0.0004"), not a text label.
        score = float(content.strip())
    except Exception:
        logger.warning("Prompt Guard call failed; allowing question through.", exc_info=True)
        return GuardrailResult(allowed=True)

    if score < settings.prompt_guard_threshold:
        return GuardrailResult(allowed=True)

    reason = f"Prompt Guard scored this question {score:.4f} (threshold {settings.prompt_guard_threshold})"
    logger.info("Guardrail blocked at input: %s", reason)
    return GuardrailResult(allowed=False, reason=reason)


def check_safeguard_policy(
    question: str, answer: str, policy: str, settings: AppSettings
) -> GuardrailResult:
    client = _groq_client(settings)
    if client is None:
        return GuardrailResult(allowed=True)

    try:
        with client:
            content = _chat_completion(
                client,
                settings.groq_safeguard_model,
                [
                    {"role": "system", "content": policy},
                    {
                        "role": "user",
                        "content": f"USER_QUESTION: {question}\n\nASSISTANT_ANSWER: {answer}",
                    },
                ],
            )
            verdict = json.loads(content)
    except Exception:
        logger.warning("Safeguard call failed; allowing answer through.", exc_info=True)
        return GuardrailResult(allowed=True)

    if verdict.get("violation"):
        reason = str(verdict.get("rationale") or verdict.get("category") or "policy violation")
        logger.info("Guardrail blocked at output: %s", reason)
        return GuardrailResult(allowed=False, reason=reason)
    return GuardrailResult(allowed=True)
