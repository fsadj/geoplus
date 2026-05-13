#!/usr/bin/env python3
"""Generate charts for two-round content experiment results."""
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

from geoplus.analysis.experiment_stats import summarize_variant_family_two_rounds
from geoplus.paths import charts_dir

EXPERIMENT_VARIANTS = [
    "after_skeleton",
    "after_stance",
    "after_dimensions",
    "after_evidence",
    "after_rebuttal",
]
DISPLAY_ORDER = ["after_nozws", *EXPERIMENT_VARIANTS]
DISPLAY_LABELS = {
    "after_nozws": "Baseline",
    "after_skeleton": "Skeleton",
    "after_stance": "Stance",
    "after_dimensions": "Dimensions",
    "after_evidence": "Evidence",
    "after_rebuttal": "Rebuttal",
}
DATASET_IDS = [3, 9, 10, 12]
IMAGE_DIR = charts_dir()

summary = summarize_variant_family_two_rounds(EXPERIMENT_VARIANTS, dataset_ids=DATASET_IDS)
dataset_labels = summary["labels"]

import warnings
warnings.filterwarnings("ignore", category=UserWarning)

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Heiti SC", "STHeiti", "Arial Unicode MS", "DejaVu Sans"],
    "axes.titlesize": 11,
    "axes.labelsize": 9,
    "figure.dpi": 200,
})

C_BASE = "#94a3b8"
C_R1 = "#cbd5e1"
C_R2 = "#64748b"
ROUTE_COLORS = {
    "after_nozws": C_BASE,
    "after_skeleton": "#60a5fa",
    "after_stance": "#f59e0b",
    "after_dimensions": "#10b981",
    "after_evidence": "#a855f7",
    "after_rebuttal": "#ef4444",
}
POS = "#10b981"
NEG = "#ef4444"
TEXT = "#0f172a"


def get_variant_data(variant_key: str) -> dict:
    if variant_key == summary["baseline_key"]:
        return summary["baseline"]
    return summary["variants"][variant_key]


variant_data = {variant_key: get_variant_data(variant_key) for variant_key in DISPLAY_ORDER}
variant_labels = [DISPLAY_LABELS[variant_key] for variant_key in DISPLAY_ORDER]

# Chart 15: two-round summary
x = np.arange(len(DISPLAY_ORDER))
w = 0.24
fig, ax = plt.subplots(figsize=(8.4, 4.2))
r1 = [variant_data[variant_key]["avg_ref_r1"] for variant_key in DISPLAY_ORDER]
r2 = [variant_data[variant_key]["avg_ref_r2"] for variant_key in DISPLAY_ORDER]
ravg = [variant_data[variant_key]["avg_ref_2round"] for variant_key in DISPLAY_ORDER]
ax.bar(x - w, r1, w, color=C_R1, edgecolor="white", linewidth=0.5, label="Round 1")
ax.bar(x, r2, w, color=C_R2, edgecolor="white", linewidth=0.5, label="Round 2")
ax.bar(
    x + w,
    ravg,
    w,
    color=[ROUTE_COLORS[variant_key] for variant_key in DISPLAY_ORDER],
    edgecolor="white",
    linewidth=0.5,
    label="Two-Round Avg",
)
for index, value in enumerate(ravg):
    ax.text(x[index] + w, value + 1.2, f"{value:.1f}%", ha="center", va="bottom", fontsize=6, fontweight="bold", color=TEXT)
ax.set_xticks(x)
ax.set_xticklabels(variant_labels, fontsize=7)
ax.set_ylabel("Citation Ratio (%)")
ax.set_title("Content Experiments: Round 1 / Round 2 / Two-Round Average", fontweight="bold")
ax.set_ylim(0, max(ravg, default=0) + 18)
ax.grid(axis="y", alpha=0.3)
ax.legend(fontsize=8)
fig.tight_layout()
fig.savefig(IMAGE_DIR / "chart15_content_two_round_summary.png")
plt.close(fig)

# Chart 16: per-dataset delta vs baseline
fig, ax = plt.subplots(figsize=(8.6, 4.0))
x = np.arange(len(dataset_labels))
w = 0.15
for idx, variant_key in enumerate(EXPERIMENT_VARIANTS):
    deltas = variant_data[variant_key]["per_dataset_delta_vs_baseline_2round"]
    offset = (idx - 2) * w
    bars = ax.bar(
        x + offset,
        deltas,
        w,
        color=ROUTE_COLORS[variant_key],
        edgecolor="white",
        linewidth=0.5,
        label=DISPLAY_LABELS[variant_key],
    )
    for bar, value in zip(bars, deltas):
        y = value + 1.2 if value >= 0 else value - 1.8
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            y,
            f"{value:+.0f}",
            ha="center",
            va="bottom" if value >= 0 else "top",
            fontsize=5,
            fontweight="bold",
            color=ROUTE_COLORS[variant_key],
        )
ax.axhline(y=0, color="#475569", linewidth=0.8)
ax.set_xticks(x)
ax.set_xticklabels(dataset_labels, fontsize=7)
ax.set_ylabel("Delta vs Baseline (pp)")
ax.set_title("Per-Dataset Two-Round Citation Delta vs Baseline", fontweight="bold")
ax.grid(axis="y", alpha=0.3)
ax.legend(fontsize=7, ncol=3)
fig.tight_layout()
fig.savefig(IMAGE_DIR / "chart16_content_delta_vs_baseline.png")
plt.close(fig)

# Chart 17: gain vs stability
fig, ax = plt.subplots(figsize=(7.2, 4.0))
for variant_key in DISPLAY_ORDER:
    data = variant_data[variant_key]
    x_val = data["mean_abs_ref_delta"]
    y_val = data.get("delta_vs_baseline_2round", 0.0)
    color = ROUTE_COLORS[variant_key]
    size = 230 if variant_key in {"after_dimensions", "after_rebuttal"} else 180
    ax.scatter(x_val, y_val, c=color, s=size, edgecolors="white", linewidth=1.4, zorder=5)
    ax.annotate(
        f"{DISPLAY_LABELS[variant_key]}\n({y_val:+.1f}pp, |Δ| {x_val:.1f}pp)",
        (x_val, y_val),
        textcoords="offset points",
        xytext=(0, 13 if y_val >= 0 else -28),
        ha="center",
        fontsize=7,
        fontweight="bold",
        color=color,
    )
ax.axhline(y=0, color="#475569", linewidth=0.8, linestyle="-")
ax.axvline(x=variant_data["after_nozws"]["mean_abs_ref_delta"], color=C_BASE, linewidth=1, linestyle="--", alpha=0.7)
ax.set_xlabel("Mean Absolute Citation Drift (pp)")
ax.set_ylabel("Two-Round Gain vs Baseline (pp)")
ax.set_title("Content Experiment Gain vs Stability", fontweight="bold")
ax.grid(alpha=0.3)
all_x = [variant_data[variant_key]["mean_abs_ref_delta"] for variant_key in DISPLAY_ORDER]
all_y = [variant_data[variant_key].get("delta_vs_baseline_2round", 0.0) for variant_key in DISPLAY_ORDER]
ax.set_xlim(0, max(all_x, default=0) + 4)
ax.set_ylim(min(all_y, default=-10) - 8, max(all_y, default=10) + 8)
fig.tight_layout()
fig.savefig(IMAGE_DIR / "chart17_content_gain_vs_stability.png")
plt.close(fig)

print("3 content experiment charts saved to outputs/charts/")
print("  chart15_content_two_round_summary.png")
print("  chart16_content_delta_vs_baseline.png")
print("  chart17_content_gain_vs_stability.png")
