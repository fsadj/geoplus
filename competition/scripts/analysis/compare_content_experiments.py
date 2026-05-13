#!/usr/bin/env python3
"""Compare content-focused experimental variants across two evaluation rounds."""
import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from geoplus.analysis.experiment_stats import summarize_variant_family_two_rounds
from geoplus.evaluation.specs import get_evaluation_spec

EXPERIMENT_VARIANTS = [
    "after_skeleton",
    "after_stance",
    "after_dimensions",
    "after_evidence",
    "after_rebuttal",
]

DISPLAY_ORDER = ["after_nozws", *EXPERIMENT_VARIANTS]

VARIANT_LABELS = {
    "after_nozws": "Default Baseline",
    "after_skeleton": "Path 1 Skeleton",
    "after_stance": "Path 2 Stance",
    "after_dimensions": "Path 3 Dimensions",
    "after_evidence": "Path 4 Evidence",
    "after_rebuttal": "Path 5 Rebuttal",
}


def parse_datasets(raw: str) -> list[int]:
    return [int(part.strip()) for part in raw.split(",") if part.strip()]


def _variant_data(summary: dict, variant_key: str) -> dict:
    if variant_key == summary["baseline_key"]:
        return summary["baseline"]
    return summary["variants"][variant_key]


def _variant_rows(summary: dict) -> list[tuple[str, str, dict]]:
    rows = []
    for variant_key in DISPLAY_ORDER:
        spec = get_evaluation_spec(variant_key)
        rows.append((variant_key, VARIANT_LABELS[variant_key], {"file": spec.source_name, **_variant_data(summary, variant_key)}))
    return rows


def render_text(summary: dict) -> None:
    labels = summary["labels"]
    round_a = summary["round_a"]
    round_b = summary["round_b"]
    rows = _variant_rows(summary)

    sep = "=" * 132
    print(sep)
    print(f"  CONTENT EXPERIMENT TWO-ROUND COMPARISON: datasets={','.join(labels)} rounds={round_a},{round_b}")
    print(sep)

    print(
        f"\n{'Variant':<22} {'R1 Cit%':>8} {'R2 Cit%':>8} {'2R Avg':>8} {'2R Word':>9} {'vs Base':>9} {'|Δ| Avg':>9}"
    )
    print("-" * 86)
    for variant_key, label, data in rows:
        delta_vs_baseline = data.get("delta_vs_baseline_2round", 0.0)
        print(
            f"{label:<22}"
            f" {data['avg_ref_r1']:>7.1f}%"
            f" {data['avg_ref_r2']:>7.1f}%"
            f" {data['avg_ref_2round']:>7.1f}%"
            f" {data['avg_word_2round']:>8.1f}%"
            f" {delta_vs_baseline:>+8.1f}pp"
            f" {data['mean_abs_ref_delta']:>8.1f}pp"
        )

    print("\nPer-dataset two-round delta vs baseline:")
    header = f"{'Variant':<22}" + "".join(f" {label:>8}" for label in labels)
    print(header)
    print("-" * len(header))
    for variant_key, label, data in rows[1:]:
        delta_cells = "".join(f" {delta:>+7.1f}pp" for delta in data["per_dataset_delta_vs_baseline_2round"])
        print(f"{label:<22}{delta_cells}")

    print("\nStability summary:")
    print(f"{'Variant':<22} {'Mean |Δ| Cit':>12} {'Max |Δ| Cit':>12} {'Mean |Δ| Word':>13}")
    print("-" * 64)
    for _, label, data in rows:
        print(
            f"{label:<22}"
            f" {data['mean_abs_ref_delta']:>11.1f}pp"
            f" {data['max_abs_ref_delta']:>11.1f}pp"
            f" {data['mean_abs_word_delta']:>12.1f}pp"
        )
    print(sep)


def render_markdown(summary: dict) -> None:
    labels = summary["labels"]
    round_a = summary["round_a"]
    round_b = summary["round_b"]
    rows = _variant_rows(summary)

    print(f"Two-round summary for datasets `{','.join(labels)}` with rounds `{round_a}` and `{round_b}`.\n")

    print("### Two-Round Summary")
    print()
    print("| 路线 | 对应文件 | R1 平均引用次数占比 | R2 平均引用次数占比 | 两轮平均引用次数占比 | 两轮平均引用内容字数占比 | 相对默认基线 | 平均绝对引用偏差 |")
    print("|------|------|:--:|:--:|:--:|:--:|:--:|:--:|")
    for variant_key, label, data in rows:
        delta_vs_baseline = data.get("delta_vs_baseline_2round", 0.0)
        print(
            f"| {label} | `{data['file']}` | {data['avg_ref_r1']:.1f}% | {data['avg_ref_r2']:.1f}% | "
            f"{data['avg_ref_2round']:.1f}% | {data['avg_word_2round']:.1f}% | {delta_vs_baseline:+.1f}pp | "
            f"{data['mean_abs_ref_delta']:.1f}pp |"
        )

    print()
    print("### Two-Round Delta Vs Baseline")
    print()
    header = "| 路线 | " + " | ".join(labels) + " |"
    align = "|------|" + "|".join([":--:"] * len(labels)) + "|"
    print(header)
    print(align)
    for _, label, data in rows[1:]:
        delta_cells = " | ".join(f"{delta:+.1f}pp" for delta in data["per_dataset_delta_vs_baseline_2round"])
        print(f"| {label} | {delta_cells} |")

    print()
    print("### Stability Summary")
    print()
    print("| 路线 | 平均绝对引用偏差 | 最大绝对引用偏差 | 平均绝对字数偏差 |")
    print("|------|:--:|:--:|:--:|")
    for _, label, data in rows:
        print(
            f"| {label} | {data['mean_abs_ref_delta']:.1f}pp | {data['max_abs_ref_delta']:.1f}pp | "
            f"{data['mean_abs_word_delta']:.1f}pp |"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare content experiment variants across two rounds")
    parser.add_argument(
        "--datasets",
        default="3,9,10,12",
        help="Comma-separated dataset ids (default: 3,9,10,12)",
    )
    parser.add_argument("--round-a", type=int, default=1, help="First evaluation round number")
    parser.add_argument("--round-b", type=int, default=2, help="Second evaluation round number")
    parser.add_argument("--format", choices=("text", "markdown"), default="text", help="Output format")
    args = parser.parse_args()

    dataset_ids = parse_datasets(args.datasets)
    summary = summarize_variant_family_two_rounds(
        EXPERIMENT_VARIANTS,
        dataset_ids=dataset_ids,
        round_a=args.round_a,
        round_b=args.round_b,
    )

    if args.format == "markdown":
        render_markdown(summary)
    else:
        render_text(summary)


if __name__ == "__main__":
    main()
