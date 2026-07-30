"""
Every agent node prompts the LLM to reply with JSON-only so its output
can drive the API response shape directly (reply/draft_scope/etc).
This helper tolerates the ```json fences models add despite being told
not to, and degrades to an empty dict on genuinely malformed output
rather than raising -- a bad model reply should fall back to a safe
default for that turn, not 500 the whole chat.
"""

import json
import logging

logger = logging.getLogger(__name__)


def parse_json_reply(text: str) -> dict:
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned[:4].lower() == "json":
            cleaned = cleaned[4:]
    cleaned = cleaned.strip()

    if not cleaned:
        return {}

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning("agent_json_parse_failed", extra={"raw_preview": cleaned[:500]})
        return {}

    return parsed if isinstance(parsed, dict) else {}
