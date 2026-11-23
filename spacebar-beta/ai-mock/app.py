# Deterministic local stand-in for the OpenAI Chat Completions API.
#
# It implements only what systems/spirits/spirit_ai.py calls:
#   POST /v1/chat/completions
#   GET  /health
#
# No Internet access is required or attempted; the container runs on the
# internal beta network so the real api.openai.com is unreachable.
#
# Failure injection, to exercise the error paths of the bot:
#   AI_MOCK_FAIL_MODE=429 | 500 | timeout | invalid-json
import json
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get("AI_MOCK_PORT", "8081"))
FAIL_MODE = os.environ.get("AI_MOCK_FAIL_MODE", "").strip().lower()

# Deterministic payloads: the same request always produces the same answer, so
# the beta tests can assert on the content.
SPIRIT_REPLY = "The petals whisper your name, and the wind carries it home. 🌸"
PERSONALITY_JSON = {
    "name": "Hanami",
    "personality": "mysterious",
    "appearance_description": "A pale spirit wrapped in drifting cherry blossoms.",
    "color_scheme": "pink and white",
    "abilities": ["Petal Dance", "Healing Breeze"],
}
EMOTION_JSON = {
    "state": "Blossoming",
    "intensity": 0.7,
    "reasoning": "The messages carry a calm, hopeful tone.",
}


def _completion(content: str, model: str) -> dict:
    """Build a minimal Chat Completions response."""
    return {
        "id": "chatcmpl-local-mock",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model or "local-mock-model",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }


def _answer(payload: dict) -> str:
    """Pick a deterministic answer from the request shape."""
    messages = payload.get("messages") or []
    text = " ".join(str(m.get("content", "")) for m in messages).lower()

    if "respond only with valid json" in text and "emotional" in text:
        return json.dumps(EMOTION_JSON)
    if "respond only with valid json" in text:
        return json.dumps(PERSONALITY_JSON)
    return SPIRIT_REPLY


class Handler(BaseHTTPRequestHandler):
    """Serve the two endpoints used by the bot."""

    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):  # noqa: A003 - stdlib signature
        print(f"ai-mock: {fmt % args}", flush=True)

    def _send(self, status: int, body: dict) -> None:
        data = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):  # noqa: N802 - stdlib signature
        if self.path.rstrip("/") == "/health":
            self._send(200, {"status": "ok", "fail_mode": FAIL_MODE or None})
            return
        self._send(404, {"error": {"message": "not found"}})

    def do_POST(self):  # noqa: N802 - stdlib signature
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw or b"{}")
        except json.JSONDecodeError:
            self._send(400, {"error": {"message": "invalid request body"}})
            return

        if FAIL_MODE == "429":
            self._send(429, {"error": {"message": "rate limited by the local mock"}})
            return
        if FAIL_MODE == "500":
            self._send(500, {"error": {"message": "internal error by the local mock"}})
            return
        if FAIL_MODE == "timeout":
            # Longer than SAKURA_BOT_OPENAI_TIMEOUT_SECONDS so the SDK gives up.
            time.sleep(60)
            self._send(200, _completion(SPIRIT_REPLY, payload.get("model")))
            return
        if FAIL_MODE == "invalid-json":
            body = _completion("this is not json at all", payload.get("model"))
            self._send(200, body)
            return

        self._send(200, _completion(_answer(payload), payload.get("model")))


if __name__ == "__main__":
    print(f"ai-mock listening on 0.0.0.0:{PORT} fail_mode={FAIL_MODE or 'none'}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
