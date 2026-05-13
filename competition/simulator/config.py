from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class SimulatorConfig:
    base_url: str
    auth_token: str
    answer_model: str
    judge_model: str
    answer_max_tokens: int = 12000
    judge_max_tokens: int = 4000
    timeout: int = 300


DEFAULT_BASE_URL = "https://toddeverett-ohmyapi.hf.space"
DEFAULT_MODEL = "gpt-5.4"
DEFAULT_TOKEN = "sk-j49z2Ea2zvoLEbo9C"


def load_config() -> SimulatorConfig:
    base_url = os.environ.get("SIMULATOR_BASE_URL") or os.environ.get("ANTHROPIC_BASE_URL") or DEFAULT_BASE_URL
    auth_token = os.environ.get("SIMULATOR_AUTH_TOKEN") or os.environ.get("ANTHROPIC_AUTH_TOKEN") or DEFAULT_TOKEN
    answer_model = os.environ.get("SIMULATOR_ANSWER_MODEL") or os.environ.get("SIMULATOR_MODEL") or os.environ.get("ANTHROPIC_MODEL") or DEFAULT_MODEL
    judge_model = os.environ.get("SIMULATOR_JUDGE_MODEL") or answer_model
    return SimulatorConfig(
        base_url=base_url.rstrip("/"),
        auth_token=auth_token.strip(),
        answer_model=answer_model.strip(),
        judge_model=judge_model.strip(),
    )
