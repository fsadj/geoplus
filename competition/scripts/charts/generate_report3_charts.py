#!/usr/bin/env python3
"""Generate charts for experiment summaries."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

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
BEFORE = "#94a3b8"
ROUTE_COLORS = {
    "after_frontload_rebuttal": "#ef4444",
    "after_novelty_gap": "#0ea5e9",
    "after_novelty_gap_rebuttal_extended": "#7c3aed",
    "after_novelty_gap_naturalized": "#06b6d4",
    "after_superset_guarded": "#22c55e",
    "after_frontload_novelty_guarded": "#111827",
    "after_rebuttal": "#f97316",
    "after_rebuttal_extended": "#c2410c",
    "after_dimensions": "#8b5cf6",
    "after_dimensions_rebuttal": "#f59e0b",
    "after_nozws": "#64748b",
    "after_nozws_implicit_bestof": "#1d4ed8",
}
DISPLAY_LABELS = {
    "after_frontload_rebuttal": "Frontload",
    "after_novelty_gap": "Novelty Gap",
    "after_novelty_gap_rebuttal_extended": "Novelty+Rebuttal",
    "after_novelty_gap_naturalized": "Naturalized",
    "after_superset_guarded": "Superset Guarded",
    "after_frontload_novelty_guarded": "Hybrid",
    "after_rebuttal": "Rebuttal",
    "after_rebuttal_extended": "Rebuttal Ext",
    "after_dimensions": "Dimensions",
    "after_dimensions_rebuttal": "Dim+Rebuttal",
    "after_nozws": "Baseline",
    "after_nozws_implicit_bestof": "NoZWS BestOf",
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
    parser = argparse.ArgumentParser(description="Generate charts for experiment summaries")
    parser.add_argument(
        "--summary",
        required=True,
        help="Path to compare_variants JSON summary",
    )
    parser.add_argument(
        "--prefix",
        default="report3",
        help="Output file prefix under outputs/charts",
    )
    return parser.parse_args()


def variant_label(variant_key: str) -> str:
    return DISPLAY_LABELS.get(variant_key, variant_key.removeprefix("after_").replace("_", " ").title())


def variant_color(variant_key: str) -> str:
    return ROUTE_COLORS.get(variant_key, "#334155")


def load_summary(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def item_dataset_label(item: dict) -> str:
    item_id = str(item.get("item_id", ""))
    digits = "".join(ch for ch in item_id if ch.isdigit())
    if digits:
        return f"DS{digits}"
    return item_id or "Unknown"


def title_prefix(prefix: str) -> str:
    return prefix.replace("_", " ").title()


def chart_delta_breakdown(summary: dict, output_dir: Path, prefix: str) -> str:
    rows = sorted(summary["variants"], key=lambda row: row["avg_delta"], reverse=True)
    labels = [variant_label(row["variant"]) for row in rows]
    colors = [variant_color(row["variant"]) for row in rows]
    x = np.arange(len(rows))
    width = 0.24

    fig, ax = plt.subplots(figsize=(8.6, 4.2))
    total = [row["avg_delta"] for row in rows]
    objective = [row["avg_objective_delta"] for row in rows]
    ai = [row["avg_ai_delta"] for row in rows]
    ax.bar(x - width, total, width, color=colors, edgecolor="white", linewidth=0.6, label="Total Δ")
    ax.bar(x, objective, width, color="#93c5fd", edgecolor="white", linewidth=0.6, label="Objective Δ")
    ax.bar(x + width, ai, width, color="#fde68a", edgecolor="white", linewidth=0.6, label="AI Δ")
    for index, value in enumerate(total):
        ax.text(x[index] - width, value + 0.9, f"{value:+.1f}", ha="center", va="bottom", fontsize=6, color=TEXT, fontweight="bold")
    ax.axhline(y=0, color="#475569", linewidth=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=7)
    ax.set_ylabel("Score Delta")
    ax.set_title(f"{title_prefix(prefix)} Delta Breakdown", fontweight="bold")
    ax.grid(axis="y", alpha=0.3, color=GRID)
    ax.legend(fontsize=8, ncol=3)
    fig.tight_layout()
    filename = f"{prefix}_delta_breakdown.png"
    fig.savefig(output_dir / filename)
    plt.close(fig)
    return filename


def chart_after_totals(summary: dict, output_dir: Path, prefix: str) -> str:
    rows = sorted(summary["variants"], key=lambda row: row["avg_after_total"], reverse=True)
    labels = [variant_label(row["variant"]) for row in rows]
    colors = [variant_color(row["variant"]) for row in rows]
    x = np.arange(len(rows))
    before_avg = rows[0]["avg_before_total"] if rows else 0.0

    fig, ax = plt.subplots(figsize=(8.2, 4.0))
    bars = ax.bar(x, [row["avg_after_total"] for row in rows], color=colors, edgecolor="white", linewidth=0.6)
    ax.axhline(y=before_avg, color=BEFORE, linewidth=1.4, linestyle="--", label=f"Before Avg {before_avg:.1f}")
    for bar, row in zip(bars, rows):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.8,
            f"{row['avg_after_total']:.1f}",
            ha="center",
            va="bottom",
            fontsize=6,
            color=TEXT,
            fontweight="bold",
        )
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=7)
    ax.set_ylabel("Average After Total")
    ax.set_title(f"{title_prefix(prefix)} Average After Score", fontweight="bold")
    ax.grid(axis="y", alpha=0.3, color=GRID)
    ax.legend(fontsize=8)
    fig.tight_layout()
    filename = f"{prefix}_after_totals.png"
    fig.savefig(output_dir / filename)
    plt.close(fig)
    return filename


def chart_per_dataset_delta(summary: dict, output_dir: Path, prefix: str) -> str:
    rows = sorted(summary["variants"], key=lambda row: row["avg_delta"], reverse=True)
    if not rows:
        raise ValueError("summary contains no variants")
    dataset_labels = [item_dataset_label(item) for item in rows[0]["item_results"]]
    x = np.arange(len(dataset_labels))
    width = 0.72 / max(len(rows), 1)

    fig, ax = plt.subplots(figsize=(8.8, 4.2))
    for index, row in enumerate(rows):
        offsets = x + (index - (len(rows) - 1) / 2) * width
        deltas = [item["delta"] for item in row["item_results"]]
        bars = ax.bar(
            offsets,
            deltas,
            width,
            color=variant_color(row["variant"]),
            edgecolor="white",
            linewidth=0.5,
            label=variant_label(row["variant"]),
        )
        for bar, value in zip(bars, deltas):
            y = value + 0.9 if value >= 0 else value - 1.2
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                y,
                f"{value:+.1f}",
                ha="center",
                va="bottom" if value >= 0 else "top",
                fontsize=5,
                color=variant_color(row["variant"]),
                fontweight="bold",
            )
    ax.axhline(y=0, color="#475569", linewidth=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(dataset_labels, fontsize=7)
    ax.set_ylabel("Delta")
    ax.set_title(f"{title_prefix(prefix)} Per-Dataset Delta", fontweight="bold")
    ax.grid(axis="y", alpha=0.3, color=GRID)
    ax.legend(fontsize=7, ncol=min(3, len(rows)))
    fig.tight_layout()
    filename = f"{prefix}_per_dataset_delta.png"
    fig.savefig(output_dir / filename)
    plt.close(fig)
    return filename


def main() -> None:
    args = parse_args()
    summary = load_summary(Path(args.summary))
    output_dir = charts_dir()

    outputs = [
        chart_delta_breakdown(summary, output_dir, args.prefix),
        chart_after_totals(summary, output_dir, args.prefix),
        chart_per_dataset_delta(summary, output_dir, args.prefix),
    ]
    print("experiment charts saved to outputs/charts/")
    for name in outputs:
        print(f"  {name}")


if __name__ == "__main__":
    main()
