"""Exercise the spirit AI against the local stub, from inside the bot container.

Proves that ``SAKURA_BOT_OPENAI_BASE_URL`` really redirects the SDK and that the
deterministic answers are the ones the beta tests expect.

    Get-Content spacebar-beta\\spike\\ai_mock_check.py | docker compose --env-file .env.spacebar `
        -f docker-compose.spacebar.yml exec -T sakura-bot-beta python -

Exit code 0 when every call returns a usable answer.
"""

import asyncio
import json
import sys

from systems.spirits.spirit_ai import SpiritAI


async def main() -> int:
    failures = 0

    reply = await SpiritAI.generate_spirit_response(
        spirit_name="Hanami",
        personality="mysterious",
        faction="Moonborn",
        mood="Calm",
        user_message="Hello, spirit.",
    )
    if reply and "petals" in reply.lower():
        print(f"PASS generate_spirit_response -> {reply}")
    else:
        print(f"FAIL generate_spirit_response -> {reply!r}")
        failures += 1

    personality = await SpiritAI.generate_spirit_personality("rare", "Moonborn", "water")
    if isinstance(personality, dict) and personality.get("name") == "Hanami":
        print(f"PASS generate_spirit_personality -> {json.dumps(personality)}")
    else:
        print(f"FAIL generate_spirit_personality -> {personality!r}")
        failures += 1

    emotion = await SpiritAI.analyze_user_emotion(["I feel great today"])
    if isinstance(emotion, dict) and emotion.get("state") == "Blossoming":
        print(f"PASS analyze_user_emotion -> {json.dumps(emotion)}")
    else:
        print(f"FAIL analyze_user_emotion -> {emotion!r}")
        failures += 1

    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
