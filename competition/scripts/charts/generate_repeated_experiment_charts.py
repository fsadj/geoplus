#!/usr/bin/env python3
"""Generate charts for repeated experiment outputs."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from geoplus.paths import charts_dir

TEXT = "#0f172a"
GRID = "#cbd5e1"
ROUTE_COLORS = {
    "after_nozws": "#1d4ed8",
    "after_dimensions": "#0f766e",
    "after_rebuttal": "#ea580c",
    "after_rebuttal_extended": "#dc2626",
    "after_novelty_gap": "#0ea5e9",
    "after_query_anchored_novelty_gap": "#7c3aed",
    "after_coverage_floor": "#22c55e",
    "after_anchored_novelty_with_coverage_floor": "#f97316",
}
DISPLAY_LABELS = {
    "after_nozws": "No-ZWS Baseline",
    "after_dimensions": "Dimensions",
    "after_rebuttal": "Rebuttal",
    "after_rebuttal_extended": "Rebuttal Extended",
    "after_novelty_gap": "Novelty Gap",
    "after_query_anchored_novelty_gap": "Anchored Novelty",
    "after_coverage_floor": "Coverage Floor",
    "after_anchored_novelty_with_coverage_floor": "Anchored + Floor",
}

plt.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": ["Heiti SC", "STHeiti", "Arial Unicode MS", "DejaVu Sans"],
        "axes.titlesize": 11,
        "axes.labelsize": 9,
        "figure.dpi": 200,
    }
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate charts for repeated experiment outputs")
    parser.add_argument("--experiment-dir", required=True, help="Path to repeated experiment output directory")
    parser.add_argument("--prefix", default="report4_stage1", help="Output file prefix under outputs/charts")
    return parser.parse_args()


def variant_label(variant_key: str) -> str:
    return DISPLAY_LABELS.get(variant_key, variant_key.removeprefix("after_").replace("_", " ").title())


def variant_color(variant_key: str) -> str:
    return ROUTE_COLORS.get(variant_key, "#334155")


def title_prefix(prefix: str) -> str:
    return prefix.replace("_", " ").title()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dataset_label_for_row(row: dict[str, Any]) -> str:
    return row.get("dataset_label") or f"DS{row['dataset_id']}"


def chart_delta_ci(summary_by_variant: list[dict[str, Any]], output_dir: Path, prefix: str) -> str:
    rows = sorted(summary_by_variant, key=lambda row: row["avg_delta"], reverse=True)
    labels = [variant_label(row["variant"]) for row in rows]
    colors = [variant_color(row["variant"]) for row in rows]
    x = np.arange(len(rows))
    values = [row["avg_delta"] for row in rows]
    lower = [row["avg_delta"] - row["ci95_low"] for row in rows]
    upper = [row["ci95_high"] - row["avg_delta"] for row in rows]

    fig, ax = plt.subplots(figsize=(9.0, 4.6))
    bars = ax.bar(x, values, color=colors, edgecolor="white", linewidth=0.6)
    ax.errorbar(x, values, yerr=[lower, upper], fmt="none", ecolor=TEXT, elinewidth=1.0, capsize=4)
    for bar, row in zip(bars, rows):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.7,
            f"{row['avg_delta']:+.1f}\nWR {row['win_rate']:.0f}%",
            ha="center",
            va="bottom",
            fontsize=6,
            color=TEXT,
            fontweight="bold",
        )
    ax.axhline(y=0, color="#475569", linewidth=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=7)
    ax.set_ylabel("Average Delta")
    ax.set_title(f"{title_prefix(prefix)} Mean Delta With 95% CI", fontweight="bold")
    ax.grid(axis="y", alpha=0.3, color=GRID)
    fig.tight_layout()
    filename = f"{prefix}_delta_ci.png"
    fig.savefig(output_dir / filename)
    plt.close(fig)
    return filename


def chart_dataset_delta(summary_by_dataset: list[dict[str, Any]], output_dir: Path, prefix: str) -> str:
    variants: list[str] = []
    for row in summary_by_dataset:
        if row["variant"] not in variants:
            variants.append(row["variant"])
    variants.sort(key=lambda key: sum(item["avg_delta"] for item in summary_by_dataset if item["variant"] == key), reverse=True)

    dataset_rows = {}
    for row in summary_by_dataset:
        dataset_rows.setdefault(row["dataset_id"], row)
    dataset_ids = sorted(dataset_rows)
    dataset_labels = [dataset_label_for_row(dataset_rows[dataset_id]) for dataset_id in dataset_ids]
    x = np.arange(len(dataset_ids))
    width = 0.72 / max(len(variants), 1)

    fig, ax = plt.subplots(figsize=(9.4, 4.6))
    for index, variant in enumerate(variants):
        rows = [row for row in summary_by_dataset if row["variant"] == variant]
        rows.sort(key=lambda row: row["dataset_id"])
        values = [row["avg_delta"] for row in rows]
        offsets = x + (index - (len(variants) - 1) / 2) * width
        bars = ax.bar(
            offsets,
            values,
            width,
            color=variant_color(variant),
            edgecolor="white",
            linewidth=0.5,
            label=variant_label(variant),
        )
        for bar, value in zip(bars, values):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                value + 0.7,
                f"{value:+.1f}",
                ha="center",
                va="bottom",
                fontsize=5,
                color=variant_color(variant),
                fontweight="bold",
            )
    ax.axhline(y=0, color="#475569", linewidth=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(dataset_labels, fontsize=7)
    ax.set_ylabel("Average Delta")
    ax.set_title(f"{title_prefix(prefix)} Per-Dataset Delta", fontweight="bold")
    ax.grid(axis="y", alpha=0.3, color=GRID)
    ax.legend(fontsize=7, ncol=2)
    fig.tight_layout()
    filename = f"{prefix}_per_dataset_delta.png"
    fig.savefig(output_dir / filename)
    plt.close(fig)
    return filename


def chart_variance_split(variance_rows: list[dict[str, Any]], output_dir: Path, prefix: str) -> str:
    rows = sorted(variance_rows, key=lambda row: row["mean_total_variance"])
    labels = [variant_label(row["variant"]) for row in rows]
    colors = [variant_color(row["variant"]) for row in rows]
    x = np.arange(len(rows))
    generation = [row["mean_generation_variance"] for row in rows]
    simulation = [row["mean_simulation_variance"] for row in rows]

    fig, ax = plt.subplots(figsize=(9.2, 4.6))
    ax.bar(x, generation, color=colors, edgecolor="white", linewidth=0.6, label="Generation Var")
    ax.bar(x, simulation, bottom=generation, color="#cbd5e1", edgecolor="white", linewidth=0.6, label="Simulation Var")
    for index, row in enumerate(rows):
        total = row["mean_total_variance"]
        ax.text(x[index], total + 4, f"{total:.1f}", ha="center", va="bottom", fontsize=6, color=TEXT, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=7)
    ax.set_ylabel("Mean Variance")
    ax.set_title(f"{title_prefix(prefix)} Variance Split", fontweight="bold")
    ax.grid(axis="y", alpha=0.3, color=GRID)
    ax.legend(fontsize=8, ncol=2)
    fig.tight_layout()
    filename = f"{prefix}_variance_split.png"
    fig.savefig(output_dir / filename)
    plt.close(fig)
    return filename


def add_metric_panel(
    ax: plt.Axes,
    rows: list[dict[str, Any]],
    *,
    value_key: str,
    low_key: str,
    high_key: str,
    title: str,
    xlim: tuple[float, float] | None = None,
) -> None:
    ordered = sorted(rows, key=lambda row: row[value_key], reverse=True)
    labels = [variant_label(row["variant"]) for row in ordered]
    colors = [variant_color(row["variant"]) for row in ordered]
    y = np.arange(len(ordered))
    values = [row[value_key] for row in ordered]
    lower = [row[value_key] - row[low_key] for row in ordered]
    upper = [row[high_key] - row[value_key] for row in ordered]

    ax.barh(y, values, color=colors, edgecolor="white", linewidth=0.6)
    ax.errorbar(values, y, xerr=[lower, upper], fmt="none", ecolor=TEXT, elinewidth=1.0, capsize=3)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=6)
    ax.invert_yaxis()
    ax.set_title(title, fontsize=9, fontweight="bold")
    ax.grid(axis="x", alpha=0.3, color=GRID)
    if xlim is not None:
        ax.set_xlim(*xlim)


def chart_metric_overview(summary_by_variant: list[dict[str, Any]], output_dir: Path, prefix: str) -> str:
    fig, axes = plt.subplots(2, 2, figsize=(10.5, 6.8))
    add_metric_panel(
        axes[0, 0],
        summary_by_variant,
        value_key="avg_delta",
        low_key="ci95_low",
        high_key="ci95_high",
        title="Average Delta",
    )
    add_metric_panel(
        axes[0, 1],
        summary_by_variant,
        value_key="avg_objective_delta",
        low_key="objective_ci95_low",
        high_key="objective_ci95_high",
        title="Objective Delta",
    )
    add_metric_panel(
        axes[1, 0],
        summary_by_variant,
        value_key="avg_ai_delta",
        low_key="ai_ci95_low",
        high_key="ai_ci95_high",
        title="AI Delta",
    )
    add_metric_panel(
        axes[1, 1],
        summary_by_variant,
        value_key="win_rate",
        low_key="win_rate_ci95_low",
        high_key="win_rate_ci95_high",
        title="Win Rate (%)",
        xlim=(0, 100),
    )
    fig.suptitle(f"{title_prefix(prefix)} Metric Overview", fontsize=12, fontweight="bold")
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    filename = f"{prefix}_metric_overview.png"
    fig.savefig(output_dir / filename)
    plt.close(fig)
    return filename


def main() -> None:
    args = parse_args()
    experiment_dir = Path(args.experiment_dir)
    summary_by_variant = load_json(experiment_dir / "summary_by_variant.json")
    summary_by_dataset = load_json(experiment_dir / "summary_by_dataset.json")
    variance_rows = load_json(experiment_dir / "variance_decomposition.json")
    output_dir = charts_dir()

    outputs = [
        chart_delta_ci(summary_by_variant, output_dir, args.prefix),
        chart_dataset_delta(summary_by_dataset, output_dir, args.prefix),
        chart_variance_split(variance_rows, output_dir, args.prefix),
        chart_metric_overview(summary_by_variant, output_dir, args.prefix),
    ]
    print("repeated experiment charts saved to outputs/charts/")
    for name in outputs:
        print(f"  {name}")


if __name__ == "__main__":
    main()
