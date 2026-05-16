from __future__ import annotations

from pathlib import Path

from simulator.config import load_config
from simulator.data import load_json_item
from simulator.pipeline import evaluate_item_before_after
from simulator.reporting import aggregate_results

from final.adapters.datasets import REPO_ROOT, final_after_path, final_dataset_dir, get_dataset_mapping, list_dataset_ids
from final.common import timestamp, write_json, write_text


def build_item(dataset_id: int):
    mapping = get_dataset_mapping(dataset_id)
    item_path = REPO_ROOT / "competition" / mapping.simulator_source_file
    return load_json_item(item_path)


def evaluate_single(dataset_id: int, *, after_path: Path | None = None) -> dict:
    item = build_item(dataset_id)
    actual_after_path = after_path or final_after_path(dataset_id)
    after_text = actual_after_path.read_text(encoding="utf-8").strip()
    config = load_config()
    result = evaluate_item_before_after(item, after_text=after_text, after_label=actual_after_path.name, config=config)
    report = aggregate_results([result])
    item_result = report.item_results[0]

    test_after_path = final_dataset_dir(dataset_id) / "test_after.md"
    score_path = final_dataset_dir(dataset_id) / "score.json"
    write_text(test_after_path, result.after.answer)
    after_only_result = {
        "item_id": item_result["item_id"],
        "after_total": item_result["after_total"],
        "after_answer": item_result["after_answer"],
        "after_objective": item_result["after_objective"],
        "after_judge": item_result["after_judge"],
        "after_visibility": item_result["after_visibility"],
    }
    payload = {
        "version": 2,
        "dataset_id": dataset_id,
        "after_path": str(actual_after_path),
        "test_after_path": str(test_after_path),
        "generated_at": timestamp(),
        "summary": {
            "after_total": report.avg_after_total,
            "after_objective": item_result["after_objective"],
            "after_judge": item_result["after_judge"],
            "after_visibility": item_result["after_visibility"],
        },
        "result": after_only_result,
        "raw_after_only": {
            "count": 1,
            "avg_after_total": report.avg_after_total,
            "item_results": [after_only_result],
        },
    }
    write_json(score_path, payload)
    return payload


def evaluate_batch(dataset_ids: list[int] | None = None) -> dict:
    ids = dataset_ids or list_dataset_ids()
    results = [evaluate_single(dataset_id) for dataset_id in ids]
    summary = {
        "count": len(results),
        "avg_after_total": sum(result["summary"]["after_total"] for result in results) / max(len(results), 1),
        "datasets": [result["dataset_id"] for result in results],
        "generated_at": timestamp(),
    }
    output_path = final_dataset_dir(ids[0]).parents[1] / "batch_after_scores.json"
    write_json(output_path, {"summary": summary, "items": results})
    return {"summary": summary, "items": results, "output_path": str(output_path)}
