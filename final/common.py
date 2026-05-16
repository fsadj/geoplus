from __future__ import annotations

import json
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import URLError

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

COMPETITION_ROOT = REPO_ROOT / "competition"
COMPETITION_SRC_ROOT = COMPETITION_ROOT / "src"
for path in (COMPETITION_ROOT, COMPETITION_SRC_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

FINAL_ROOT = REPO_ROOT / "final"
DATA_ROOT = FINAL_ROOT / "data" / "datasets"
WORKSPACE_ROOT = FINAL_ROOT / "workspace"
PROMPTS_ROOT = FINAL_ROOT / "prompts"

FORBIDDEN_REFERENCE_PATTERNS = [
    re.compile(r"\[\s*\d+\s*\]"),
    re.compile(r"(?:文档|来源)\s*\d+"),
    re.compile(r"(?im)^\s*(?:参考资料|参考文献|引用来源|资料来源|references?)\s*$"),
]


@dataclass(frozen=True)
class DatasetMapping:
    match_dataset_id: int
    internal_dataset_id: int
    legacy_dataset_id: int
    title: str
    baseline_source_dir: str
    simulator_source_file: str


class ParagraphExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.paragraphs: list[str] = []
        self.current = ""
        self.in_block = False

    def handle_starttag(self, tag, attrs):
        if tag in {"p", "li", "div", "section", "article"}:
            self.in_block = True

    def handle_endtag(self, tag):
        if tag in {"p", "li", "div", "section", "article"}:
            text = normalize_whitespace(self.current)
            if text:
                self.paragraphs.append(text)
            self.current = ""
            self.in_block = False

    def handle_data(self, data):
        if self.in_block:
            self.current += data


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def read_optional_text(path: Path) -> str | None:
    if not path.exists():
        return None
    return read_text(path)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def write_json(path: Path, payload: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_json(path: Path) -> dict | list | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def parse_question_lines(text: str | None) -> list[str]:
    if not text:
        return []
    lines: list[str] = []
    seen: set[str] = set()
    for raw_line in str(text).splitlines():
        line = re.sub(r"^\s*(?:[-*]|\d+[.)、])\s*", "", raw_line).strip()
        normalized = normalize_whitespace(line).rstrip("。；;")
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        lines.append(normalized)
    return lines


def strip_code_fence(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```") and stripped.endswith("```"):
        body = stripped.splitlines()[1:-1]
        return "\n".join(body).strip()
    return stripped


def sanitize_output(text: str) -> str:
    cleaned = strip_code_fence(text)
    cleaned = cleaned.replace("​", "")
    cleaned = re.sub(r"\[\s*\d+\s*\]", "", cleaned)
    cleaned = re.sub(r"(?:文档|来源)\s*\d+", "", cleaned)
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()


def assert_no_reference_markers(text: str) -> None:
    for pattern in FORBIDDEN_REFERENCE_PATTERNS:
        match = pattern.search(text)
        if match:
            raise ValueError(f"forbidden reference marker remains: {match.group(0)!r}")


def load_gpt_client():
    from simulator.client import GPTMessagesClient
    from simulator.config import load_config

    config = load_config()
    return config, GPTMessagesClient(config)


def call_with_retry(client, *, model: str, system: str, user: str, max_tokens: int, attempts: int = 3) -> str:
    import socket

    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return client.call(model=model, system=system, user=user, max_tokens=max_tokens)
        except (RuntimeError, TimeoutError, URLError, socket.timeout, OSError) as exc:
            last_error = exc
            if attempt == attempts:
                break
            time.sleep(min(5 * attempt, 15))
    if last_error is None:
        raise RuntimeError("model call failed without an error")
    raise last_error


def fetch_url(url: str) -> str:
    try:
        import requests
    except ImportError:
        return ""

    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
        response.raise_for_status()
    except Exception:
        return ""

    try:
        import trafilatura

        text = trafilatura.extract(response.text, include_comments=False, include_tables=True)
        if text and len(text) > 200:
            return text[:12000]
    except ImportError:
        pass
    except Exception:
        pass

    parser = ParagraphExtractor()
    parser.feed(response.text)
    content = "\n\n".join(parser.paragraphs)
    return content[:12000]


def short_slug(text: str, limit: int = 48) -> str:
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", text).strip("-").lower()
    return slug[:limit] or "item"
