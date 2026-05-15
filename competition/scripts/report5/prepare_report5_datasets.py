#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = REPO_ROOT / "config" / "report5_datasets.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare internal report5 datasets under competition/")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="Path to report5 dataset config JSON")
    parser.add_argument("--force", action="store_true", help="Remove existing internal dataset directories before copying")
    return parser.parse_args()


def load_config(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("report5 dataset config must be a JSON array")
    return payload


def repo_path(relative_path: str) -> Path:
    return REPO_ROOT / relative_path


def copy_tree(source_dir: Path, target_dir: Path) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    for source_path in sorted(source_dir.iterdir()):
        target_path = target_dir / source_path.name
        if source_path.is_dir():
            shutil.copytree(source_path, target_path, dirs_exist_ok=True)
        else:
            shutil.copy2(source_path, target_path)


def reset_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def write_meta(path: Path, entry: dict[str, Any]) -> None:
    meta = {
        "match_dataset_id": entry["match_dataset_id"],
        "internal_dataset_id": entry["internal_dataset_id"],
        "legacy_dataset_id": entry["legacy_dataset_id"],
        "title": entry["title"],
        "baseline_source_dir": entry["baseline_source_dir"],
        "simulator_source_file": entry["simulator_source_file"],
    }
    path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def prepare_entry(entry: dict[str, Any], *, force: bool) -> None:
    internal_dataset_id = int(entry["internal_dataset_id"])
    baseline_source_dir = repo_path(str(entry["baseline_source_dir"]))
    simulator_source_file = repo_path(str(entry["simulator_source_file"]))
    baseline_target_dir = REPO_ROOT / "data" / "baseline" / str(internal_dataset_id)
    dataset_output_dir = REPO_ROOT / "outputs" / "datasets" / str(internal_dataset_id)
    simulator_target_file = dataset_output_dir / f"simulator_item_ds{internal_dataset_id}.json"

    if not baseline_source_dir.exists():
        raise FileNotFoundError(f"baseline source dir not found: {baseline_source_dir}")
    if not simulator_source_file.exists():
        raise FileNotFoundError(f"simulator source file not found: {simulator_source_file}")

    if force:
        reset_dir(baseline_target_dir)
        reset_dir(dataset_output_dir)
    else:
        baseline_target_dir.mkdir(parents=True, exist_ok=True)
        dataset_output_dir.mkdir(parents=True, exist_ok=True)

    copy_tree(baseline_source_dir, baseline_target_dir)
    shutil.copy2(simulator_source_file, simulator_target_file)

    legacy_output_dir = simulator_source_file.parent
    optional_files = [
        "test_before.md",
        "before_search_results.json",
        "before_search_results_zh.json",
    ]
    for file_name in optional_files:
        source_path = legacy_output_dir / file_name
        if source_path.exists():
            shutil.copy2(source_path, dataset_output_dir / file_name)

    write_meta(dataset_output_dir / "report5_dataset_meta.json", entry)
    print(
        "prepared "
        f"Match{entry['match_dataset_id']} -> DS{internal_dataset_id} "
        f"(legacy DS{entry['legacy_dataset_id']})"
    )


def main() -> None:
    args = parse_args()
    config_path = Path(args.config)
    entries = load_config(config_path)
    for entry in entries:
        prepare_entry(entry, force=args.force)
    print(f"prepared_count={len(entries)}")
    print("report5 datasets are isolated under competition/ only")


if __name__ == "__main__":
    main()
