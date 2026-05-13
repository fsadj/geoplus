#!/usr/bin/env python3
"""Generate charts for curated rebuttal length-band experiments."""
import json
import sys
import warnings
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

R1_PATH = REPO_ROOT / "outputs" / "simulator_length_summary_rebuttal_curated_with_ultra.json"
R2_PATH = REPO_ROOT / "outputs" / "simulator_length_summary_rebuttal_curated_with_ultra_r2.json"
DISPLAY_ORDER = ["after_rebuttal", "after_rebuttal_extended", "after_rebuttal_ultra"]
DISPLAY_LABELS = {
    "after_rebuttal": "Medium",
    "after_rebuttal_extended": "Extended",
    "after_rebuttal_ultra": "Ultra",
}
COLORS = {
    "after_rebuttal": "#2563eb",
    "after_rebuttal_extended": "#10b981",
    "after_rebuttal_ultra": "#ef4444",
}
IMAGE_DIR = charts_dir()

warnings.filterwarnings("ignore", category=UserWarning)
plt.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": ["Heiti SC", "STHeiti", "Arial Unicode MS", "DejaVu Sans"],
        "axes.titlesize": 11,
        "axes.labelsize": 9,
        "figure.dpi": 200,
    }
)


def load_variants(path: Path) -> dict[str, dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {item["variant"]: item for item in payload["variants"]}


r1 = load_variants(R1_PATH)
r2 = load_variants(R2_PATH)

summary_rows: list[dict[str, float | str]] = []
for variant_key in DISPLAY_ORDER:
    r1_item = r1[variant_key]
    r2_item = r2[variant_key]
    summary_rows.append(
        {
            "variant": variant_key,
            "label": DISPLAY_LABELS[variant_key],
            "r1_delta": float(r1_item["avg_delta"]),
            "r2_delta": float(r2_item["avg_delta"]),
            "avg_delta": (float(r1_item["avg_delta"]) + float(r2_item["avg_delta"])) / 2,
            "drift": abs(float(r1_item["avg_delta"]) - float(r2_item["avg_delta"])),
            "r1_ai": float(r1_item["avg_ai_delta"]),
            "r1_obj": float(r1_item["avg_objective_delta"]),
        }
    )

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10.4, 4.2))

x = np.arange(len(summary_rows))
width = 0.22
r1_vals = [row["r1_delta"] for row in summary_rows]
r2_vals = [row["r2_delta"] for row in summary_rows]
avg_vals = [row["avg_delta"] for row in summary_rows]
labels = [row["label"] for row in summary_rows]
bar_colors = [COLORS[row["variant"]] for row in summary_rows]

ax1.bar(x - width, r1_vals, width, color="#cbd5e1", edgecolor="white", linewidth=0.6, label="Round 1")
ax1.bar(x, r2_vals, width, color="#64748b", edgecolor="white", linewidth=0.6, label="Round 2")
ax1.bar(x + width, avg_vals, width, color=bar_colors, edgecolor="white", linewidth=0.6, label="Two-Round Avg")
for idx, value in enumerate(avg_vals):
    ax1.text(x[idx] + width, value + 1.2, f"{value:.1f}", ha="center", va="bottom", fontsize=7, fontweight="bold")
ax1.set_xticks(x)
ax1.set_xticklabels(labels, fontsize=8)
ax1.set_ylabel("Average Delta")
ax1.set_title("Curated Length Band: Round 1 / Round 2 / Two-Round Avg", fontweight="bold")
ax1.grid(axis="y", alpha=0.3)
ax1.legend(fontsize=8)
ax1.set_ylim(0, max(max(r1_vals), max(r2_vals), max(avg_vals)) + 16)

for row in summary_rows:
    ax2.scatter(
        row["drift"],
        row["avg_delta"],
        s=240,
        color=COLORS[row["variant"]],
        edgecolors="white",
        linewidth=1.5,
        zorder=5,
    )
    ax2.annotate(
        f"{row['label']}\nAvg {row['avg_delta']:.1f} | Drift {row['drift']:.1f}",
        (row["drift"], row["avg_delta"]),
        textcoords="offset points",
        xytext=(0, 10),
        ha="center",
        fontsize=7,
        fontweight="bold",
        color=COLORS[row["variant"]],
    )
ax2.axhline(y=0, color="#475569", linewidth=0.8)
ax2.set_xlabel("Round-to-Round Drift")
ax2.set_ylabel("Two-Round Average Delta")
ax2.set_title("Length Band Gain vs Stability", fontweight="bold")
ax2.grid(alpha=0.3)
ax2.set_xlim(0, max(row["drift"] for row in summary_rows) + 8)
ax2.set_ylim(0, max(avg_vals) + 10)

fig.tight_layout()
output_path = IMAGE_DIR / "chart18_length_band_summary.png"
fig.savefig(output_path)
plt.close(fig)

print("1 length band chart saved to outputs/charts/")
print("  chart18_length_band_summary.png")
