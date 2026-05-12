#!/usr/bin/env python3
"""Compare content-focused experimental variants against the default baseline."""
import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from geoplus.analysis.experiment_stats import summarize_variant_family

EXPERIMENT_VARIANTS = [
    "after_nozws",
    "after_skeleton",
    "after_stance",
    "after_dimensions",
    "after_evidence",
    "after_rebuttal",
]

VARIANT_LABELS = {
    "after_nozws": "Baseline",
    "after_skeleton": "Path 1 Skeleton",
    "after_stance": "Path 2 Stance",
    "after_dimensions": "Path 3 Dimensions",
    "after_evidence": "Path 4 Evidence",
    "after_rebuttal": "Path 5 Rebuttal",
}


def parse_datasets(raw: str) -> list[int]:
    return [int(part.strip()) for part in raw.split(",") if part.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare content experiment variants")
    parser.add_argument(
        "--datasets",
        default="3,9,10,12",
        help="Comma-separated dataset ids (default: 3,9,10,12)",
    )
    args = parser.parse_args()

    dataset_ids = parse_datasets(args.datasets)
    summary = summarize_variant_family(EXPERIMENT_VARIANTS, dataset_ids=dataset_ids)
    labels = summary["labels"]
    before_ref = summary["before_ref_pct"]
    before_word = summary["before_word_pct"]
    baseline = summary["variants"]["after_nozws"]

    sep = "=" * 108
    print(sep)
    print(f"  CONTENT EXPERIMENT COMPARISON: datasets={','.join(labels)}")
    print(sep)

    print(f"\n{'Dataset':<8} {'Before':>8} {'Baseline':>10} {'P1':>8} {'P2':>8} {'P3':>8} {'P4':>8} {'P5':>8}")
    print("-" * 74)
    for index, label in enumerate(labels):
        print(
            f"{label:<8}"
            f" {before_ref[index]:>7.1f}%"
            f" {baseline['ref_pct'][index]:>9.1f}%"
            f" {summary['variants']['after_skeleton']['ref_pct'][index]:>7.1f}%"
            f" {summary['variants']['after_stance']['ref_pct'][index]:>7.1f}%"
            f" {summary['variants']['after_dimensions']['ref_pct'][index]:>7.1f}%"
            f" {summary['variants']['after_evidence']['ref_pct'][index]:>7.1f}%"
            f" {summary['variants']['after_rebuttal']['ref_pct'][index]:>7.1f}%"
        )

    print(f"\n{'Variant':<22} {'Avg Cit%':>10} {'Avg Word%':>11} {'vs Before':>11} {'vs Baseline':>13}")
    print("-" * 74)
    baseline_avg_ref = baseline["avg_ref"]
    avg_before_ref = sum(before_ref) / len(before_ref) if before_ref else 0.0
    for variant_key in EXPERIMENT_VARIANTS:
        variant = summary["variants"][variant_key]
        print(
            f"{VARIANT_LABELS[variant_key]:<22}"
            f" {variant['avg_ref']:>9.1f}%"
            f" {variant['avg_word']:>10.1f}%"
            f" {variant['avg_ref'] - avg_before_ref:>+10.1f}pp"
            f" {variant['avg_ref'] - baseline_avg_ref:>+12.1f}pp"
        )

    print("\nPer-dataset delta vs baseline:")
    header = f"{'Variant':<22}" + "".join(f" {label:>8}" for label in labels)
    print(header)
    print("-" * len(header))
    for variant_key in EXPERIMENT_VARIANTS[1:]:
        variant = summary["variants"][variant_key]
        deltas = [ref - base for ref, base in zip(variant["ref_pct"], baseline["ref_pct"])]
        delta_cells = "".join(f" {delta:>+7.1f}pp" for delta in deltas)
        print(f"{VARIANT_LABELS[variant_key]:<22}{delta_cells}")

    print(f"\nBefore Avg Word%: {sum(before_word) / len(before_word) if before_word else 0.0:.1f}%")
    print(sep)


if __name__ == "__main__":
    main()
