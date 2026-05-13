from __future__ import annotations

import json
import re
from typing import Any


def extract_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("No JSON object found in model output")
    data = json.loads(match.group(0))
    if not isinstance(data, dict):
        raise ValueError("Parsed JSON is not an object")
    return data


def clamp_score(value: Any) -> float:
    score = float(value)
    if score < 0:
        return 0.0
    if score > 100:
        return 100.0
    return score
