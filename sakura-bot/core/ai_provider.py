"""AI provider selection.

``SAKURA_BOT_AI_PROVIDER`` decides where the spirit AI answers come from:

* ``openai`` (default) keeps the production behaviour: an ``AsyncOpenAI`` client
  is created on first use and every call reaches the configured endpoint;
* ``stub`` answers inside the process with deterministic text and never creates
  a client, so a beta cannot spend credit, leak prompts or fail because the
  network is unreachable.

The stub payloads are the ones served by ``spacebar-beta/ai-mock``, so both
betas produce the same embeds and the tests can assert on the exact strings.
Every call site declares a ``kind``: an unknown kind raises instead of returning
a generic answer that would hide the omission.
"""

import json
import logging
from typing import Any, Optional

from openai import AsyncOpenAI

from core.config import STUB_PROVIDER, SUPPORTED_AI_PROVIDERS, Settings, settings

logger = logging.getLogger(__name__)

SPIRIT_RESPONSE_KIND = "spirit_response"
SPIRIT_PERSONALITY_KIND = "spirit_personality"
ROAMING_MESSAGE_KIND = "roaming_message"
USER_EMOTION_KIND = "user_emotion"

# Deterministic answers, identical to the local Spacebar stub.
STUB_ANSWERS = {
    SPIRIT_RESPONSE_KIND: "The petals whisper your name, and the wind carries it home. 🌸",
    SPIRIT_PERSONALITY_KIND: json.dumps(
        {
            "name": "Hanami",
            "personality": "mysterious",
            "appearance_description": "A pale spirit wrapped in drifting cherry blossoms.",
            "color_scheme": "pink and white",
            "abilities": ["Petal Dance", "Healing Breeze"],
        }
    ),
    ROAMING_MESSAGE_KIND: "🌸 *Hanami drifts into the channel on a gust of petals*",
    USER_EMOTION_KIND: json.dumps(
        {
            "state": "Blossoming",
            "intensity": 0.7,
            "reasoning": "The messages carry a calm, hopeful tone.",
        }
    ),
}

_client: Optional[AsyncOpenAI] = None


class AIProviderConfigurationError(RuntimeError):
    """Raised when the selected AI provider cannot be configured safely."""


def validate_ai_provider(settings: Settings) -> None:
    """Reject an unknown provider before the bot logs in."""
    provider = (settings.ai_provider or "").strip().lower()
    if provider not in SUPPORTED_AI_PROVIDERS:
        raise AIProviderConfigurationError(
            f"SAKURA_BOT_AI_PROVIDER must be one of {', '.join(SUPPORTED_AI_PROVIDERS)}, "
            f"got '{settings.ai_provider}'"
        )


def is_stub_provider() -> bool:
    """True when answers must come from the deterministic local stub."""
    return (settings.ai_provider or "").strip().lower() == STUB_PROVIDER


def _get_client() -> AsyncOpenAI:
    """Create the OpenAI client on first use.

    Building it lazily keeps module import free of network-related side effects
    and lets tests import the module without a real API key. ``base_url`` is
    only set when configured, so production keeps the SDK default.
    """
    global _client
    if _client is None:
        options: dict[str, Any] = {
            "api_key": settings.openai_api_key,
            "timeout": settings.openai_timeout_seconds,
        }
        if settings.openai_base_url:
            options["base_url"] = settings.openai_base_url
        _client = AsyncOpenAI(**options)
    return _client


def _stub_completion(kind: str) -> str:
    """Return the deterministic answer registered for ``kind``."""
    try:
        return STUB_ANSWERS[kind]
    except KeyError:
        raise ValueError(f"No stub answer is defined for AI request kind '{kind}'") from None


async def complete(
    *,
    kind: str,
    messages: list[dict[str, str]],
    max_tokens: int,
    temperature: float,
) -> str:
    """Return the completion text for one request.

    ``kind`` selects the deterministic stub answer and is ignored by the real
    provider, which only needs the messages.
    """
    if is_stub_provider():
        logger.debug("AI provider 'stub': answering '%s' locally", kind)
        return _stub_completion(kind)

    response = await _get_client().chat.completions.create(
        model=settings.openai_model,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return response.choices[0].message.content.strip()
