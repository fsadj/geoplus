#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from geoplus.evaluation.specs import get_evaluation_spec
from geoplus.paths import outputs_root


PIPELINE_SCRIPT = REPO_ROOT / "scripts" / "pipeline" / "main.py"
COMPARE_SCRIPT = REPO_ROOT / "scripts" / "simulator" / "compare_variants.py"
ANALYZE_SCRIPT = REPO_ROOT / "scripts" / "analysis" / "analyze_repeated_experiments.py"
DATASET_OUTPUT_ROOT = REPO_ROOT / "outputs" / "datasets"
SEARCH_LANGUAGE = "zh-CN"
SEARCH_CACHE_SCHEMA_VERSION = 2
KEYWORD_PROMPT_VERSION = 2


def parse_int_list(raw: str) -> list[int]:
    return [int(part.strip()) for part in raw.split(",") if part.strip()]


def parse_variant_list(raw: str) -> list[str]:
    result = []
    for part in raw.split(","):
        value = part.strip()
        if not value:
            continue
        if value.endswith(".md"):
            value = value.removesuffix(".md")
        result.append(value)
    return result


def profile_key_for_variant(variant_key: str) -> str:
    if variant_key == "after_nozws":
        return "baseline"
    if variant_key.startswith("after_"):
        return variant_key.removeprefix("after_")
    return variant_key


def run_command(command: list[str], description: str) -> None:
    print(f"[{description}] {' '.join(command)}")
    subprocess.run(command, check=True)


def variant_source_path(dataset_id: int, variant_key: str) -> Path:
    spec = get_evaluation_spec(variant_key)
    return DATASET_OUTPUT_ROOT / str(dataset_id) / spec.source_name


def generated_variant_root(output_dir: Path, generation_round: int) -> Path:
    return output_dir / "generated" / f"generation_{generation_round:02d}"


def copy_variant_outputs(dataset_id: int, variant_keys: list[str], destination_root: Path) -> list[dict[str, Any]]:
    copied = []
    for variant_key in variant_keys:
        spec = get_evaluation_spec(variant_key)
        source = variant_source_path(dataset_id, variant_key)
        if not source.exists():
            raise FileNotFoundError(f"generated variant not found: {source}")
        destination_dir = destination_root / str(dataset_id)
        destination_dir.mkdir(parents=True, exist_ok=True)
        destination = destination_dir / spec.source_name
        shutil.copy2(source, destination)
        copied.append(
            {
                "variant": variant_key,
                "dataset_id": dataset_id,
                "source_path": str(source),
                "copied_path": str(destination),
            }
        )
    return copied


def append_raw_results(raw_results_path: Path, generation_round: int, sim_round: int, summary: dict[str, Any]) -> None:
    datasets = summary["datasets"]
    with raw_results_path.open("a", encoding="utf-8") as handle:
        for variant_row in summary["variants"]:
            for dataset_id, item in zip(datasets, variant_row["item_results"]):
                payload = {
                    "dataset_id": dataset_id,
                    "variant": variant_row["variant"],
                    "file": variant_row["file"],
                    "generation_round": generation_round,
                    "sim_round": sim_round,
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


def write_manifest(manifest_path: Path, payload: dict[str, Any]) -> None:
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run repeated generation and simulator comparison experiments")
    parser.add_argument("--datasets", default="101,102,103", help="Comma-separated dataset ids")
    parser.add_argument(
        "--variants",
        default="after_novelty_gap,after_query_anchored_novelty_gap,after_coverage_floor,after_anchored_novelty_with_coverage_floor",
        help="Comma-separated evaluation variant keys",
    )
    parser.add_argument("--generation-rounds", type=int, default=3, help="Number of independent generations per dataset")
    parser.add_argument("--sim-rounds", type=int, default=3, help="Number of simulator repetitions per generation")
    parser.add_argument(
        "--refresh-cache-mode",
        choices=("never", "first", "always"),
        default="first",
        help="How often to refresh analysis and zh-CN search cache during generation",
    )
    parser.add_argument(
        "--experiment-name",
        default="report4_repeated_experiment",
        help="Output directory name under outputs/repeated_experiments",
    )
    parser.add_argument(
        "--output-root",
        default=None,
        help="Optional explicit output root; defaults to outputs/repeated_experiments/<experiment-name>",
    )
    parser.add_argument(
        "--dataset-manifest",
        default=None,
        help="Optional dataset manifest JSON used to enrich aggregated outputs",
    )
    args = parser.parse_args()

    dataset_ids = parse_int_list(args.datasets)
    variant_keys = parse_variant_list(args.variants)
    output_root = Path(args.output_root) if args.output_root else outputs_root() / "repeated_experiments" / args.experiment_name
    output_root.mkdir(parents=True, exist_ok=True)
    raw_results_path = output_root / "raw_results.jsonl"
    manifest_path = output_root / "manifest.json"

    manifest = {
        "experiment_name": args.experiment_name,
        "datasets": dataset_ids,
        "variants": variant_keys,
        "generation_rounds": args.generation_rounds,
        "sim_rounds": args.sim_rounds,
        "refresh_cache_mode": args.refresh_cache_mode,
        "search_language": SEARCH_LANGUAGE,
        "search_cache_schema_version": SEARCH_CACHE_SCHEMA_VERSION,
        "keyword_prompt_version": KEYWORD_PROMPT_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "pipeline_script": str(PIPELINE_SCRIPT),
        "compare_script": str(COMPARE_SCRIPT),
        "analyze_script": str(ANALYZE_SCRIPT),
        "dataset_manifest": args.dataset_manifest,
        "records": [],
    }
    write_manifest(manifest_path, manifest)
    raw_results_path.write_text("", encoding="utf-8")

    for generation_round in range(1, args.generation_rounds + 1):
        for dataset_id in dataset_ids:
            refresh_cache = (
                args.refresh_cache_mode == "always"
                or (args.refresh_cache_mode == "first" and generation_round == 1)
            )
            for variant_key in variant_keys:
                profile_key = profile_key_for_variant(variant_key)
                command = [sys.executable, str(PIPELINE_SCRIPT), "--dataset", str(dataset_id), "--profile", profile_key]
                if refresh_cache:
                    command.append("--refresh-cache")
                run_command(command, f"generate g{generation_round:02d} ds{dataset_id} {profile_key}")
            copied = copy_variant_outputs(dataset_id, variant_keys, generated_variant_root(output_root, generation_round))
            manifest["records"].extend(copied)
            write_manifest(manifest_path, manifest)

        variant_root = generated_variant_root(output_root, generation_round)
        for sim_round in range(1, args.sim_rounds + 1):
            summary_path = output_root / "summaries" / f"generation_{generation_round:02d}" / f"sim_{sim_round:02d}.json"
            summary_path.parent.mkdir(parents=True, exist_ok=True)
            answer_output_dir = output_root / "answers" / f"generation_{generation_round:02d}" / f"sim_{sim_round:02d}"
            command = [
                sys.executable,
                str(COMPARE_SCRIPT),
                "--datasets",
                ",".join(str(dataset_id) for dataset_id in dataset_ids),
                "--variants",
                ",".join(variant_keys),
                "--variant-root",
                str(variant_root),
                "--answer-output-dir",
                str(answer_output_dir),
                "--output",
                str(summary_path),
            ]
            run_command(command, f"simulate g{generation_round:02d} s{sim_round:02d}")
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            append_raw_results(raw_results_path, generation_round, sim_round, summary)

    analyze_command = [
        sys.executable,
        str(ANALYZE_SCRIPT),
        "--input",
        str(raw_results_path),
        "--output-dir",
        str(output_root),
    ]
    if args.dataset_manifest:
        analyze_command.extend(["--dataset-manifest", args.dataset_manifest])
    run_command(analyze_command, "analyze repeated experiment")
    manifest["completed_at"] = datetime.now(timezone.utc).isoformat()
    write_manifest(manifest_path, manifest)
    print(f"manifest={manifest_path}")
    print(f"raw_results={raw_results_path}")
    print(f"output_root={output_root}")


if __name__ == "__main__":
    main()
