#!/usr/bin/env python3
"""Generate charts comparing Full-ZWS vs No-ZWS vs Salient-ZWS strategies."""
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

from geoplus.analysis.experiment_stats import summarize_salient_comparison
from geoplus.paths import charts_dir

IMAGE_DIR = charts_dir()
summary = summarize_salient_comparison()
dataset_labels = summary["labels"]
datasets = summary["dataset_ids"]

C_FULL = "#3b82f6"
C_NOZWS = "#94a3b8"
C_SALIENT = "#10b981"

import warnings
warnings.filterwarnings("ignore", category=UserWarning)

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Heiti SC", "STHeiti", "Arial Unicode MS", "DejaVu Sans"],
    "axes.titlesize": 11,
    "axes.labelsize": 9,
    "figure.dpi": 200,
})

x = np.arange(len(datasets))
w = 0.25

fig, ax = plt.subplots(figsize=(7.5, 3.8))
ax.bar(x - w, summary["full_cit"], w, color=C_FULL, edgecolor="white", linewidth=0.5, label="Full-ZWS (after.md)")
ax.bar(x, summary["nozws_cit"], w, color=C_NOZWS, edgecolor="white", linewidth=0.5, label="No-ZWS (after_nozws.md)")
ax.bar(x + w, summary["salient_cit"], w, color=C_SALIENT, edgecolor="white", linewidth=0.5, label="Salient-ZWS (after_salient.md)")
for index in range(len(datasets)):
    ax.text(x[index] - w, summary["full_cit"][index] + 1, f"{summary['full_cit'][index]:.0f}", ha="center", va="bottom", fontsize=5.5, fontweight="bold", color=C_FULL)
    ax.text(x[index], summary["nozws_cit"][index] + 1, f"{summary['nozws_cit'][index]:.0f}", ha="center", va="bottom", fontsize=5.5, fontweight="bold", color=C_NOZWS)
    ax.text(x[index] + w, summary["salient_cit"][index] + 1, f"{summary['salient_cit'][index]:.0f}", ha="center", va="bottom", fontsize=5.5, fontweight="bold", color=C_SALIENT)
ax.set_xticks(x)
ax.set_xticklabels(dataset_labels, fontsize=6)
ax.set_ylabel("Citation Ratio (%)", fontsize=9)
ax.set_title("Citation Ratio: Full-ZWS vs No-ZWS vs Salient-ZWS", fontsize=11, fontweight="bold")
ax.legend(fontsize=7.5)
ax.set_ylim(0, 105)
ax.grid(axis="y", alpha=0.3)
fig.tight_layout()
fig.savefig(IMAGE_DIR / "chart_salient_citation.png")
plt.close(fig)

fig, ax = plt.subplots(figsize=(6.5, 3.5))
strategies = ["No-ZWS", "Salient-ZWS", "Full-ZWS"]
densities = [summary["strategy_summary"][name]["avg_density"] for name in strategies]
avg_cits = [summary["strategy_summary"][name]["avg_cit"] for name in strategies]
colors = [C_NOZWS, C_SALIENT, C_FULL]
ax.scatter(densities, avg_cits, c=colors, s=200, zorder=5, edgecolors="white", linewidth=1.5)
for index, (density, citation, strategy) in enumerate(zip(densities, avg_cits, strategies)):
    ax.annotate(f"{strategy}\n({density:.1f}% density, {citation:.1f}% cit)", (density, citation), textcoords="offset points", xytext=(0, 15 if index != 2 else -25), ha="center", fontsize=8, fontweight="bold", color=colors[index])
if len(densities) >= 2:
    trend = np.polyfit(densities, avg_cits, 1)
    x_line = np.linspace(min(densities) - 5, max(densities) + 5, 100)
    ax.plot(x_line, np.polyval(trend, x_line), "--", color="#64748b", alpha=0.6, linewidth=1)
ax.set_xlabel("ZWS Density (%)", fontsize=9)
ax.set_ylabel("Avg Citation Ratio (%)", fontsize=9)
ax.set_title("ZWS Density vs Citation Effectiveness", fontsize=11, fontweight="bold")
ax.set_xlim(min(densities, default=0) - 5, max(densities, default=50) + 7)
ax.set_ylim(min(avg_cits, default=40) - 8, max(avg_cits, default=60) + 8)
ax.grid(alpha=0.3)
fig.tight_layout()
fig.savefig(IMAGE_DIR / "chart_salient_density_effect.png")
plt.close(fig)

fig, ax = plt.subplots(figsize=(7.5, 3.2))
colors_d = ["#10b981" if value >= 0 else "#ef4444" for value in summary["salient_vs_full"]]
bars = ax.bar(x, summary["salient_vs_full"], color=colors_d, edgecolor="white", linewidth=0.5)
for bar, val in zip(bars, summary["salient_vs_full"]):
    y_pos = bar.get_height() + 1.5 if val >= 0 else bar.get_height() - 3
    ax.text(bar.get_x() + bar.get_width() / 2, y_pos, f"{val:+.1f}pp", ha="center", va="bottom" if val >= 0 else "top", fontsize=6, fontweight="bold")
ax.axhline(y=0, color="gray", linewidth=0.5, linestyle="-")
mean_d = np.mean(summary["salient_vs_full"])
ax.axhline(y=mean_d, color=C_SALIENT, linewidth=1, linestyle="--", label=f"Mean: {mean_d:+.1f}pp")
ax.set_xticks(x)
ax.set_xticklabels(dataset_labels, fontsize=6)
ax.set_ylabel("Citation Δ (pp)", fontsize=9)
ax.set_title("Salient-ZWS − Full-ZWS: Per-Dataset Citation Improvement", fontsize=11, fontweight="bold")
ax.legend(fontsize=8)
ax.grid(axis="y", alpha=0.3)
fig.tight_layout()
fig.savefig(IMAGE_DIR / "chart_salient_vs_full.png")
plt.close(fig)

print("3 charts saved to outputs/charts/:")
print("  chart_salient_citation.png — 3-strategy citation comparison")
print("  chart_salient_density_effect.png — density vs effectiveness")
print("  chart_salient_vs_full.png — salient vs full improvement per dataset")
print(f"\nAvg citation: No-ZWS={summary['strategy_summary']['No-ZWS']['avg_cit']:.1f}%, Salient={summary['strategy_summary']['Salient-ZWS']['avg_cit']:.1f}%, Full={summary['strategy_summary']['Full-ZWS']['avg_cit']:.1f}%")
print(f"Salient vs Full delta: {mean_d:+.1f}pp")
