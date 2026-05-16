#!/usr/bin/env python3

import json
import os
import urllib.request

DEFAULT_BASE_URL = "https://api.deepseek.com/anthropic"
DEFAULT_MODEL = "deepseek-v4-flash"


def _api_url() -> str:
    base_url = os.environ.get("ANTHROPIC_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    if base_url.endswith("/v1/messages"):
        return base_url
    return f"{base_url}/v1/messages"


def _auth_token() -> str:
    token = os.environ.get("ANTHROPIC_AUTH_TOKEN")
    if not token:
        raise RuntimeError(
            "ANTHROPIC_AUTH_TOKEN environment variable is required."
        )
    return token.strip()


def _model() -> str:
    model = os.environ.get("ANTHROPIC_MODEL", DEFAULT_MODEL).strip()
    if not model:
        raise RuntimeError("ANTHROPIC_MODEL is empty")
    return model


def _normalize_content(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text_parts.append(block.get("text", ""))
                continue
            raise ValueError(f"Unsupported content block: {block!r}")
        return "\n".join(part for part in text_parts if part)
    return str(content)


def _normalize_messages(messages: list[dict]) -> tuple[str | None, list[dict[str, str]]]:
    system_parts = []
    normalized_messages = []
    for message in messages:
        role = message.get("role")
        content = _normalize_content(message.get("content", ""))
        if role == "system":
            if content:
                system_parts.append(content)
            continue
        if role not in {"user", "assistant"}:
            raise ValueError(f"Unsupported role: {role!r}")
        normalized_messages.append({"role": role, "content": content})

    if not normalized_messages:
        raise ValueError("At least one non-system message is required")
    if normalized_messages[0]["role"] != "user":
        raise ValueError("Conversation must start with a user message")

    system_prompt = "\n\n".join(system_parts) if system_parts else None
    return system_prompt, normalized_messages


def call_model(messages: list[dict], *, max_tokens: int, timeout: int = 300) -> str:
    system_prompt, normalized_messages = _normalize_messages(messages)
    payload = {
        "model": _model(),
        "max_tokens": max_tokens,
        "messages": normalized_messages,
    }
    if system_prompt:
        payload["system"] = system_prompt

    token = _auth_token()
    request = urllib.request.Request(
        _api_url(),
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
            "x-api-key": token,
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )

    opener = urllib.request.build_opener(urllib.request.ProxyHandler())
    with opener.open(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        data = json.loads(response.read().decode(charset))

    if data.get("error"):
        error = data["error"]
        if isinstance(error, dict):
            raise RuntimeError(error.get("message") or json.dumps(error, ensure_ascii=False))
        raise RuntimeError(str(error))

    text_parts = [
        block.get("text", "")
        for block in data.get("content", [])
        if isinstance(block, dict) and block.get("type") == "text"
    ]
    return "\n".join(part for part in text_parts if part).strip()
