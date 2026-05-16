#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from geoplus.paths import outputs_root

CONFIG_PATH = REPO_ROOT / "config" / "report5_datasets.json"
COMPARE_SCRIPT = REPO_ROOT / "scripts" / "simulator" / "compare_variants.py"
ANALYZE_SCRIPT = REPO_ROOT / "scripts" / "analysis" / "analyze_repeated_experiments.py"
CHART_SCRIPT = REPO_ROOT / "scripts" / "charts" / "generate_repeated_experiment_charts.py"
DEFAULT_VARIANTS = [
    "after_simulator_consensus",
    "after_coverage_floor",
    "after_query_anchored_novelty_gap",
    "after_rebuttal",
    "after_nozws",
]
DEFAULT_EXPERIMENT_NAME = "report5_simulator_consensus_compare"
DEFAULT_CHART_PREFIX = "report5_simulator_consensus"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate report5 simulator consensus variant")
    parser.add_argument("--config", default=str(CONFIG_PATH), help="Path to report5 dataset config JSON")
    parser.add_argument("--datasets", default=None, help="Comma-separated internal dataset ids")
    parser.add_argument(
        "--variants",
        default=",".join(DEFAULT_VARIANTS),
        help="Comma-separated variant keys or markdown file stems",
    )
    parser.add_argument("--experiment-name", default=DEFAULT_EXPERIMENT_NAME, help="Output directory name")
    parser.add_argument("--chart-prefix", default=DEFAULT_CHART_PREFIX, help="Chart output prefix")
    parser.add_argument(
        "--variant-root",
        default=str(REPO_ROOT / "outputs" / "datasets"),
        help="Root directory containing per-dataset variant markdown files",
    )
    return parser.parse_args()


def parse_int_list(raw: str) -> list[int]:
    return [int(part.strip()) for part in raw.split(",") if part.strip()]


def parse_variant_list(raw: str) -> list[str]:
    values = []
    for part in raw.split(","):
        value = part.strip()
        if not value:
            continue
        values.append(value.removesuffix(".md"))
    return values


def load_config(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("report5 dataset config must be a JSON array")
    return payload


def selected_dataset_ids(config_entries: list[dict[str, Any]], dataset_ids: list[int] | None) -> list[int]:
    if dataset_ids is not None:
        return dataset_ids
    return [int(entry["internal_dataset_id"]) for entry in config_entries]


def run_command(command: list[str], description: str) -> None:
    print(f"[{description}] {' '.join(command)}")
    subprocess.run(command, check=True)


def write_manifest(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_raw_results(compare_summary: dict[str, Any], raw_results_path: Path) -> None:
    datasets = compare_summary["datasets"]
    with raw_results_path.open("w", encoding="utf-8") as handle:
        for variant_row in compare_summary["variants"]:
            for dataset_id, item in zip(datasets, variant_row["item_results"]):
                payload = {
                    "dataset_id": dataset_id,
                    "variant": variant_row["variant"],
                    "file": variant_row["file"],
                    "generation_round": 1,
                    "sim_round": 1,
                    "before_total": item["before_total"],
                    "after_total": item["after_total"],
                    "delta": item["delta"],
                    "objective_delta": item["objective_delta"],
                    "ai_delta": item["ai_delta"],
                    "before_answer_path": item.get("before_answer_path"),
                    "after_answer_path": item.get("after_answer_path"),
                    "summary_variant_count": variant_row["count"],
                }
                handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def main() -> None:
    args = parse_args()
    config_entries = load_config(Path(args.config))
    dataset_ids = selected_dataset_ids(config_entries, parse_int_list(args.datasets) if args.datasets else None)
    variants = parse_variant_list(args.variants)

    output_dir = outputs_root() / "repeated_experiments" / args.experiment_name
    output_dir.mkdir(parents=True, exist_ok=True)
    compare_summary_path = output_dir / "compare_summary.json"
    raw_results_path = output_dir / "raw_results.jsonl"
    answer_output_dir = output_dir / "answers"
    manifest_path = output_dir / "manifest.json"

    compare_command = [
        sys.executable,
        str(COMPARE_SCRIPT),
        "--datasets",
        ",".join(str(dataset_id) for dataset_id in dataset_ids),
        "--variants",
        ",".join(variants),
        "--variant-root",
        args.variant_root,
        "--answer-output-dir",
        str(answer_output_dir),
        "--output",
        str(compare_summary_path),
    ]
    run_command(compare_command, "compare simulator consensus variants")

    compare_summary = json.loads(compare_summary_path.read_text(encoding="utf-8"))
    write_raw_results(compare_summary, raw_results_path)
    manifest = {
        "experiment_name": args.experiment_name,
        "datasets": dataset_ids,
        "variants": variants,
        "generation_rounds": 1,
        "sim_rounds": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "compare_script": str(COMPARE_SCRIPT),
        "analyze_script": str(ANALYZE_SCRIPT),
        "chart_script": str(CHART_SCRIPT),
        "dataset_manifest": str(Path(args.config)),
        "compare_summary": str(compare_summary_path),
    }
    write_manifest(manifest_path, manifest)

    analyze_command = [
        sys.executable,
        str(ANALYZE_SCRIPT),
        "--input",
        str(raw_results_path),
        "--output-dir",
        str(output_dir),
        "--dataset-manifest",
        str(Path(args.config)),
    ]
    run_command(analyze_command, "analyze simulator consensus compare")
    chart_command = [
        sys.executable,
        str(CHART_SCRIPT),
        "--experiment-dir",
        str(output_dir),
        "--prefix",
        args.chart_prefix,
    ]
    run_command(chart_command, "chart simulator consensus compare")
    manifest["completed_at"] = datetime.now(timezone.utc).isoformat()
    write_manifest(manifest_path, manifest)
    print(f"output_dir={output_dir}")


if __name__ == "__main__":
    main()
