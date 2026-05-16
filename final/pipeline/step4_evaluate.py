from __future__ import annotations

from final.adapters.evaluator import evaluate_batch, evaluate_single


def run(dataset_id: int) -> dict:
    return evaluate_single(dataset_id)


def run_batch(dataset_ids: list[int] | None = None) -> dict:
    return evaluate_batch(dataset_ids)
