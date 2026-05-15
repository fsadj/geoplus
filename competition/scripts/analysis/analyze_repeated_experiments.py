#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import math
import random
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any


def load_raw_records(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            records.append(json.loads(text))
    return records


def load_dataset_manifest(path: Path | None) -> dict[int, dict[str, Any]]:
    if path is None:
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("dataset manifest must be a JSON array")
    manifest: dict[int, dict[str, Any]] = {}
    for entry in payload:
        dataset_id = int(entry["internal_dataset_id"])
        manifest[dataset_id] = {
            "dataset_id": dataset_id,
            "match_dataset_id": int(entry["match_dataset_id"]),
            "legacy_dataset_id": int(entry["legacy_dataset_id"]),
            "dataset_label": f"Match{entry['match_dataset_id']}",
            "legacy_label": f"DS{entry['legacy_dataset_id']}",
            "title": entry["title"],
        }
    return manifest


def dataset_meta(dataset_id: int, manifest: dict[int, dict[str, Any]]) -> dict[str, Any]:
    return manifest.get(
        dataset_id,
        {
            "dataset_id": dataset_id,
            "match_dataset_id": None,
            "legacy_dataset_id": None,
            "dataset_label": f"DS{dataset_id}",
            "legacy_label": None,
            "title": None,
        },
    )


def mean(values: list[float]) -> float:
    return statistics.fmean(values) if values else 0.0


def sample_std(values: list[float]) -> float:
    return statistics.stdev(values) if len(values) >= 2 else 0.0


def variance(values: list[float]) -> float:
    return statistics.pvariance(values) if len(values) >= 2 else 0.0


def covariance(xs: list[float], ys: list[float]) -> float:
    if len(xs) < 2 or len(xs) != len(ys):
        return 0.0
    mean_x = mean(xs)
    mean_y = mean(ys)
    return sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / len(xs)


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def bootstrap_mean_ci(values: list[float], *, samples: int = 1000, seed: int = 7) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    if len(values) == 1:
        return values[0], values[0]
    rng = random.Random(seed)
    estimates = []
    for _ in range(samples):
        draw = [values[rng.randrange(len(values))] for _ in range(len(values))]
        estimates.append(mean(draw))
    return percentile(estimates, 0.025), percentile(estimates, 0.975)


def wilson_ci(successes: int, total: int, *, z: float = 1.96) -> tuple[float, float]:
    if total <= 0:
        return 0.0, 0.0
    phat = successes / total
    denominator = 1 + z * z / total
    center = (phat + z * z / (2 * total)) / denominator
    margin = z * math.sqrt((phat * (1 - phat) + z * z / (4 * total)) / total) / denominator
    return 100.0 * max(0.0, center - margin), 100.0 * min(1.0, center + margin)


def grouped(records: list[dict[str, Any]], *keys: str) -> dict[tuple[Any, ...], list[dict[str, Any]]]:
    buckets: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        buckets[tuple(record[key] for key in keys)].append(record)
    return buckets


def summarize_variance_decomposition(records: list[dict[str, Any]], manifest: dict[int, dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    by_variant_dataset_generation = grouped(records, "variant", "dataset_id", "generation_round")
    by_variant_dataset = grouped(records, "variant", "dataset_id")
    variants = sorted({record["variant"] for record in records})
    for variant in variants:
        sim_vars = []
        generation_vars = []
        datasets = set()
        for (bucket_variant, dataset_id), bucket in by_variant_dataset.items():
            if bucket_variant != variant:
                continue
            datasets.add(dataset_id)
            generation_means = []
            for (variant_key, grouped_dataset_id, _generation_round), nested in by_variant_dataset_generation.items():
                if variant_key != variant or grouped_dataset_id != dataset_id:
                    continue
                nested_deltas = [row["delta"] for row in nested]
                sim_vars.append(variance(nested_deltas))
                generation_means.append(mean(nested_deltas))
            generation_vars.append(variance(generation_means))
        rows.append(
            {
                "variant": variant,
                "dataset_count": len(datasets),
                "mean_generation_variance": mean(generation_vars),
                "mean_simulation_variance": mean(sim_vars),
                "mean_total_variance": mean(generation_vars) + mean(sim_vars),
            }
        )
    return rows


def summarize_by_variant(
    records: list[dict[str, Any]],
    manifest: dict[int, dict[str, Any]],
    variance_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = []
    by_variant = grouped(records, "variant")
    by_variant_dataset_generation = grouped(records, "variant", "dataset_id", "generation_round")
    variance_map = {row["variant"]: row for row in variance_rows}
    for (variant,), variant_records in sorted(by_variant.items()):
        deltas = [row["delta"] for row in variant_records]
        objective = [row["objective_delta"] for row in variant_records]
        ai = [row["ai_delta"] for row in variant_records]
        generation_vars = []
        sim_vars = []
        grouped_generation_means: dict[int, list[float]] = defaultdict(list)
        dataset_ids = sorted({int(row["dataset_id"]) for row in variant_records})
        for (bucket_variant, dataset_id, _generation_round), bucket in by_variant_dataset_generation.items():
            if bucket_variant != variant:
                continue
            bucket_deltas = [row["delta"] for row in bucket]
            sim_vars.append(variance(bucket_deltas))
            grouped_generation_means[dataset_id].append(mean(bucket_deltas))
        for generation_means in grouped_generation_means.values():
            generation_vars.append(variance(generation_means))
        delta_ci_low, delta_ci_high = bootstrap_mean_ci(deltas)
        objective_ci_low, objective_ci_high = bootstrap_mean_ci(objective)
        ai_ci_low, ai_ci_high = bootstrap_mean_ci(ai)
        win_count = sum(1 for value in deltas if value > 0)
        win_rate = 100.0 * win_count / len(deltas)
        win_rate_ci_low, win_rate_ci_high = wilson_ci(win_count, len(deltas))
        rows.append(
            {
                "variant": variant,
                "count": len(variant_records),
                "dataset_ids": dataset_ids,
                "dataset_labels": [dataset_meta(dataset_id, manifest)["dataset_label"] for dataset_id in dataset_ids],
                "avg_delta": mean(deltas),
                "std_delta": sample_std(deltas),
                "avg_objective_delta": mean(objective),
                "avg_ai_delta": mean(ai),
                "win_count": win_count,
                "win_rate": win_rate,
                "delta_p10": percentile(deltas, 0.10),
                "delta_p50": percentile(deltas, 0.50),
                "delta_p90": percentile(deltas, 0.90),
                "delta_min": min(deltas),
                "delta_max": max(deltas),
                "ci95_low": delta_ci_low,
                "ci95_high": delta_ci_high,
                "objective_ci95_low": objective_ci_low,
                "objective_ci95_high": objective_ci_high,
                "ai_ci95_low": ai_ci_low,
                "ai_ci95_high": ai_ci_high,
                "win_rate_ci95_low": win_rate_ci_low,
                "win_rate_ci95_high": win_rate_ci_high,
                "generation_variance_mean": mean(generation_vars),
                "simulation_variance_mean": mean(sim_vars),
                "mean_total_variance": variance_map.get(variant, {}).get("mean_total_variance", mean(generation_vars) + mean(sim_vars)),
                "objective_ai_covariance": covariance(objective, ai),
            }
        )
    return rows


def summarize_by_dataset(records: list[dict[str, Any]], manifest: dict[int, dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for (variant, dataset_id), bucket in sorted(grouped(records, "variant", "dataset_id").items()):
        deltas = [row["delta"] for row in bucket]
        objective = [row["objective_delta"] for row in bucket]
        ai = [row["ai_delta"] for row in bucket]
        delta_ci_low, delta_ci_high = bootstrap_mean_ci(deltas)
        objective_ci_low, objective_ci_high = bootstrap_mean_ci(objective)
        ai_ci_low, ai_ci_high = bootstrap_mean_ci(ai)
        win_count = sum(1 for value in deltas if value > 0)
        meta = dataset_meta(int(dataset_id), manifest)
        rows.append(
            {
                "variant": variant,
                "dataset_id": int(dataset_id),
                "dataset_label": meta["dataset_label"],
                "match_dataset_id": meta["match_dataset_id"],
                "legacy_dataset_id": meta["legacy_dataset_id"],
                "legacy_label": meta["legacy_label"],
                "title": meta["title"],
                "count": len(bucket),
                "avg_delta": mean(deltas),
                "std_delta": sample_std(deltas),
                "delta_p10": percentile(deltas, 0.10),
                "delta_p50": percentile(deltas, 0.50),
                "delta_p90": percentile(deltas, 0.90),
                "ci95_low": delta_ci_low,
                "ci95_high": delta_ci_high,
                "win_count": win_count,
                "win_rate": 100.0 * win_count / len(deltas),
                "win_rate_ci95_low": wilson_ci(win_count, len(deltas))[0],
                "win_rate_ci95_high": wilson_ci(win_count, len(deltas))[1],
                "avg_objective_delta": mean(objective),
                "objective_ci95_low": objective_ci_low,
                "objective_ci95_high": objective_ci_high,
                "avg_ai_delta": mean(ai),
                "ai_ci95_low": ai_ci_low,
                "ai_ci95_high": ai_ci_high,
            }
        )
    return rows


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_win_rate_matrix(path: Path, dataset_rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "variant",
                "dataset_id",
                "dataset_label",
                "match_dataset_id",
                "legacy_dataset_id",
                "title",
                "count",
                "win_rate",
                "win_rate_ci95_low",
                "win_rate_ci95_high",
                "avg_delta",
                "avg_objective_delta",
                "avg_ai_delta",
            ]
        )
        for row in dataset_rows:
            writer.writerow(
                [
                    row["variant"],
                    row["dataset_id"],
                    row["dataset_label"],
                    row["match_dataset_id"],
                    row["legacy_dataset_id"],
                    row["title"],
                    row["count"],
                    f"{row['win_rate']:.4f}",
                    f"{row['win_rate_ci95_low']:.4f}",
                    f"{row['win_rate_ci95_high']:.4f}",
                    f"{row['avg_delta']:.6f}",
                    f"{row['avg_objective_delta']:.6f}",
                    f"{row['avg_ai_delta']:.6f}",
                ]
            )


def analyze_records(
    records: list[dict[str, Any]],
    output_dir: Path,
    dataset_manifest: dict[int, dict[str, Any]],
) -> dict[str, Any]:
    variance_decomposition = summarize_variance_decomposition(records, dataset_manifest)
    summary_by_variant = summarize_by_variant(records, dataset_manifest, variance_decomposition)
    summary_by_dataset = summarize_by_dataset(records, dataset_manifest)
    write_json(output_dir / "summary_by_variant.json", summary_by_variant)
    write_json(output_dir / "summary_by_dataset.json", summary_by_dataset)
    write_json(output_dir / "variance_decomposition.json", variance_decomposition)
    write_win_rate_matrix(output_dir / "win_rate_matrix.csv", summary_by_dataset)
    return {
        "summary_by_variant": summary_by_variant,
        "summary_by_dataset": summary_by_dataset,
        "variance_decomposition": variance_decomposition,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze repeated simulator experiment outputs")
    parser.add_argument("--input", required=True, help="Path to raw_results.jsonl")
    parser.add_argument("--output-dir", required=True, help="Directory for aggregated outputs")
    parser.add_argument("--dataset-manifest", default=None, help="Optional report5 dataset manifest JSON")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    records = load_raw_records(input_path)
    if not records:
        raise SystemExit("raw_results.jsonl is empty")

    dataset_manifest = load_dataset_manifest(Path(args.dataset_manifest)) if args.dataset_manifest else {}
    payload = analyze_records(records, output_dir, dataset_manifest)
    print(f"analyzed_records={len(records)}")
    print(f"summary_by_variant={output_dir / 'summary_by_variant.json'}")
    print(f"summary_by_dataset={output_dir / 'summary_by_dataset.json'}")
    print(f"variance_decomposition={output_dir / 'variance_decomposition.json'}")
    print(f"variants={len(payload['summary_by_variant'])}")


if __name__ == "__main__":
    main()
