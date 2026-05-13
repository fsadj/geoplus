from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

if __package__ in {None, ""}:
    REPO_ROOT = Path(__file__).resolve().parents[1]
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    from simulator.data import load_json_item, parse_dataset_ids, parse_path_list
    from simulator.objective import OBJECTIVE_PROFILES, get_objective_profile
    from simulator.pipeline import evaluate_before_after, evaluate_item_before_after, evaluate_json_many, evaluate_many
else:
    from .data import load_json_item, parse_dataset_ids, parse_path_list
    from .objective import OBJECTIVE_PROFILES, get_objective_profile
    from .pipeline import evaluate_before_after, evaluate_item_before_after, evaluate_json_many, evaluate_many


def _print_single(result) -> None:
    payload = {
        "item_id": result.before.item_id,
        "before_total": result.before.total,
        "after_total": result.after.total,
        "delta": result.delta,
        "objective_delta": result.objective_delta,
        "ai_delta": result.ai_delta,
        "before_objective": result.before.objective.to_dict(include_aliases=True),
        "after_objective": result.after.objective.to_dict(include_aliases=True),
        "before_judge": result.before.judge.to_dict(include_aliases=True),
        "after_judge": result.after.judge.to_dict(include_aliases=True),
        "before_visibility": result.before.visibility_dict(),
        "after_visibility": result.after.visibility_dict(),
    }
    if result.provided_before_visibility is not None:
        payload["provided_before_visibility"] = asdict(result.provided_before_visibility)
    if result.before_smoke_check is not None:
        payload["before_smoke_check"] = asdict(result.before_smoke_check)
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _print_batch(report) -> None:
    print(json.dumps(asdict(report), ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Competition simulator MVP")
    subparsers = parser.add_subparsers(dest="command", required=True)

    single = subparsers.add_parser("evaluate", help="Evaluate one dataset or one competition JSON item")
    single_inputs = single.add_mutually_exclusive_group(required=True)
    single_inputs.add_argument("--dataset", type=int, help="Dataset id under data/baseline/")
    single_inputs.add_argument("--item-json", help="Path to one competition JSON item")
    single.add_argument("--after-name", help="Optimized file name under outputs/datasets/{id}/")
    single.add_argument("--after-path", help="Absolute or relative path to optimized target file")
    single.add_argument("--input-mode", choices=("strict", "compat"), default="strict")
    single.add_argument("--objective-profile", choices=sorted(OBJECTIVE_PROFILES), default="contest_calibrated_v1")

    batch = subparsers.add_parser("batch", help="Evaluate multiple datasets or competition JSON items")
    batch_inputs = batch.add_mutually_exclusive_group(required=True)
    batch_inputs.add_argument("--datasets", help="Comma-separated dataset ids")
    batch_inputs.add_argument("--items-json", help="Comma-separated competition JSON item paths")
    batch.add_argument("--after-name", help="Optimized file name under outputs/datasets/{id}/")
    batch.add_argument("--after-path", help="Absolute or relative path to optimized target file")
    batch.add_argument("--after-paths", help="Comma-separated optimized target paths for --items-json")
    batch.add_argument("--input-mode", choices=("strict", "compat"), default="strict")
    batch.add_argument("--objective-profile", choices=sorted(OBJECTIVE_PROFILES), default="contest_calibrated_v1")

    args = parser.parse_args()
    objective_profile = get_objective_profile(args.objective_profile)
    if args.command == "evaluate":
        if args.item_json:
            if args.after_name:
                raise SystemExit("--after-name only supports --dataset")
            item = load_json_item(args.item_json, input_mode=args.input_mode)
            after_text = None
            after_label = item.target.label
            if args.after_path:
                after_path = Path(args.after_path)
                after_text = after_path.read_text(encoding="utf-8").strip()
                after_label = after_path.name
            result = evaluate_item_before_after(
                item,
                after_text=after_text,
                after_label=after_label,
                objective_profile=objective_profile,
            )
        else:
            result = evaluate_before_after(
                args.dataset,
                after_name=args.after_name,
                after_path=args.after_path,
                objective_profile=objective_profile,
            )
        _print_single(result)
        return

    if args.items_json:
        if args.after_name or args.after_path:
            raise SystemExit("--after-name and --after-path do not support --items-json")
        item_paths = parse_path_list(args.items_json)
        after_paths = parse_path_list(args.after_paths) if args.after_paths else None
        report = evaluate_json_many(
            item_paths,
            after_paths=after_paths,
            input_mode=args.input_mode,
            objective_profile=objective_profile,
        )
    else:
        report = evaluate_many(
            parse_dataset_ids(args.datasets),
            after_name=args.after_name,
            after_path=args.after_path,
            objective_profile=objective_profile,
        )
    _print_batch(report)


if __name__ == "__main__":
    main()
