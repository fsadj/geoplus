#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from simulator.client import GPTMessagesClient
from simulator.config import load_config
from simulator.data import load_json_item, parse_dataset_ids
from simulator.pipeline import _build_smoke_check, _evaluate_single_state
from simulator.reporting import aggregate_results
from simulator.schemas import ContestItem, EvaluationResult, EvaluationSnapshot


DEFAULT_VARIANTS = [
    "after_nozws",
    "after_skeleton",
    "after_stance",
    "after_dimensions",
    "after_evidence",
    "after_rebuttal",
]


def normalize_variant_name(raw: str) -> str:
    value = raw.strip()
    if not value:
        raise ValueError("variant name cannot be empty")
    return value if value.endswith(".md") else f"{value}.md"


def variant_label(file_name: str) -> str:
    return file_name.removesuffix(".md")


def item_json_path(dataset_id: int) -> Path:
    return REPO_ROOT / "outputs" / "datasets" / str(dataset_id) / f"simulator_item_ds{dataset_id}.json"


def variant_path(dataset_id: int, file_name: str, variant_root: Path) -> Path:
    return variant_root / str(dataset_id) / file_name


def persist_answer_texts(results: list[EvaluationResult], item_results: list[dict], base_dir: Path, variant_name: str) -> None:
    before_dir = base_dir / "before"
    after_dir = base_dir / variant_name
    before_dir.mkdir(parents=True, exist_ok=True)
    after_dir.mkdir(parents=True, exist_ok=True)

    for result, item_payload in zip(results, item_results):
        item_id = result.before.item_id
        before_path = before_dir / f"{item_id}.md"
        after_path = after_dir / f"{item_id}.md"
        before_path.write_text(result.before.answer, encoding="utf-8")
        after_path.write_text(result.after.answer, encoding="utf-8")
        item_payload["before_answer_path"] = str(before_path)
        item_payload["after_answer_path"] = str(after_path)


def load_dataset_contexts(dataset_ids: list[int], client: GPTMessagesClient) -> list[dict]:
    contexts = []
    config = client.config
    for dataset_id in dataset_ids:
        item = load_json_item(item_json_path(dataset_id), input_mode="strict")
        before_label = "provided_original_answer" if item.generated_original_answer else item.target.label
        before_snapshot = _evaluate_single_state(
            client,
            config,
            item,
            before_label,
            answer_override=item.generated_original_answer,
        )
        contexts.append(
            {
                "dataset_id": dataset_id,
                "item": item,
                "before_snapshot": before_snapshot,
                "before_smoke_check": _build_smoke_check(before_snapshot, item.visibility_before),
            }
        )
        print(f"prepared dataset={dataset_id} before_total={before_snapshot.total:.2f}")
    return contexts


def summarize_variant_results(
    dataset_contexts: list[dict],
    variant_file: str,
    client: GPTMessagesClient,
    *,
    variant_root: Path,
    answer_output_dir: Path | None = None,
) -> dict:
    config = client.config
    results: list[EvaluationResult] = []
    for context in dataset_contexts:
        dataset_id = context["dataset_id"]
        item: ContestItem = context["item"]
        before_snapshot: EvaluationSnapshot = context["before_snapshot"]
        after_file = variant_path(dataset_id, variant_file, variant_root)
        after_text = after_file.read_text(encoding="utf-8").strip()
        after_item = item.with_target_content(after_text, target_label=after_file.name)
        after_snapshot = _evaluate_single_state(client, config, after_item, after_file.name)
        results.append(
            EvaluationResult(
                before=before_snapshot,
                after=after_snapshot,
                provided_before_visibility=item.visibility_before,
                before_smoke_check=context["before_smoke_check"],
            )
        )
    report = aggregate_results(results)
    item_results = report.item_results
    variant_name = variant_label(variant_file)
    if answer_output_dir is not None:
        persist_answer_texts(results, item_results, answer_output_dir, variant_name)
    return {
        "variant": variant_name,
        "file": variant_file,
        "count": report.count,
        "avg_before_total": report.avg_before_total,
        "avg_after_total": report.avg_after_total,
        "avg_delta": report.avg_delta,
        "avg_objective_delta": report.avg_objective_delta,
        "avg_ai_delta": report.avg_ai_delta,
        "win_rate": report.win_rate,
        "item_results": item_results,
    }


def render_text(summary_rows: list[dict], dataset_ids: list[int]) -> None:
    print(f"SIMULATOR VARIANT COMPARISON datasets={','.join(str(x) for x in dataset_ids)}")
    print("=" * 96)
    print(f"{'Variant':<20} {'After':>8} {'Delta':>8} {'ObjΔ':>8} {'AIΔ':>8} {'Win':>8}")
    print("-" * 96)
    for row in sorted(summary_rows, key=lambda item: item['avg_delta'], reverse=True):
        print(
            f"{row['variant']:<20}"
            f" {row['avg_after_total']:>7.2f}"
            f" {row['avg_delta']:>+7.2f}"
            f" {row['avg_objective_delta']:>+7.2f}"
            f" {row['avg_ai_delta']:>+7.2f}"
            f" {row['win_rate']:>6.1f}%"
        )
    print("\nPer-dataset delta:")
    header = f"{'Variant':<20}" + "".join(f" {dataset_id:>9}" for dataset_id in dataset_ids)
    print(header)
    print("-" * len(header))
    for row in sorted(summary_rows, key=lambda item: item['avg_delta'], reverse=True):
        deltas = "".join(f" {item['delta']:>+8.2f}" for item in row['item_results'])
        print(f"{row['variant']:<20}{deltas}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare content variants with the simulator")
    parser.add_argument("--datasets", default="3,9,10,12", help="Comma-separated dataset ids")
    parser.add_argument(
        "--variants",
        default=",".join(DEFAULT_VARIANTS),
        help="Comma-separated variant file stems or .md file names",
    )
    parser.add_argument(
        "--output",
        default=str(REPO_ROOT / "outputs" / "simulator_variant_summary.json"),
        help="Where to write the JSON summary",
    )
    parser.add_argument(
        "--variant-root",
        default=str(REPO_ROOT / "outputs" / "datasets"),
        help="Root directory containing per-dataset variant markdown files",
    )
    parser.add_argument(
        "--answer-output-dir",
        default=None,
        help="Optional directory for before/after answer markdown outputs",
    )
    args = parser.parse_args()

    dataset_ids = parse_dataset_ids(args.datasets)
    variant_files = [normalize_variant_name(part) for part in args.variants.split(",") if part.strip()]

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    variant_root = Path(args.variant_root)
    answer_output_dir = Path(args.answer_output_dir) if args.answer_output_dir else output_path.parent / f"{output_path.stem}_answers"
    answer_output_dir.mkdir(parents=True, exist_ok=True)

    config = load_config()
    client = GPTMessagesClient(config)
    dataset_contexts = load_dataset_contexts(dataset_ids, client)
    summary_rows = []
    for variant_file in variant_files:
        row = summarize_variant_results(
            dataset_contexts,
            variant_file,
            client,
            variant_root=variant_root,
            answer_output_dir=answer_output_dir,
        )
        summary_rows.append(row)
        print(f"finished variant={row['variant']} avg_delta={row['avg_delta']:+.2f}")

    payload = {
        "datasets": dataset_ids,
        "variants": summary_rows,
        "variant_root": str(variant_root),
        "answer_output_dir": str(answer_output_dir),
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    render_text(summary_rows, dataset_ids)
    print(f"\nsummary_path={output_path}")


if __name__ == "__main__":
    main()
