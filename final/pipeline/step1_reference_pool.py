from __future__ import annotations

from final.adapters.search import build_reference_pool


def run(dataset_id: int, *, refresh_cache: bool = False, refresh_questions: bool = False) -> dict:
    return build_reference_pool(dataset_id, refresh_cache=refresh_cache, refresh_questions=refresh_questions)
