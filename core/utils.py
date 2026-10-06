import json
import re
from typing import Any


def extract_json(text: str) -> Any:
    """Leniently parse JSON out of an LLM's text response, tolerating
    markdown code fences or minor surrounding chatter."""
    if text is None:
        raise ValueError("Cannot extract JSON from empty response.")
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    match = re.search(r"(\{.*\}|\[.*\])", cleaned, re.DOTALL)
    if match:
        return json.loads(match.group(1))

    raise ValueError(f"Could not parse JSON from LLM response: {text[:300]!r}")
