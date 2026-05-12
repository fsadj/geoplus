#!/usr/bin/env python3
"""Generate volatility analysis charts."""
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

from geoplus.analysis.experiment_stats import summarize_volatility
from geoplus.paths import charts_dir

IMAGE_DIR = charts_dir()
summary = summarize_volatility(1, 2)
dataset_labels = summary["labels"]
datasets = summary["dataset_ids"]

C_AFTER = "#3b82f6"
C_NOZWS = "#f59e0b"
C_ZWS = "#7c3aed"
POS = "#10b981"
NEG = "#ef4444"

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
w = 0.32

fig, ax = plt.subplots(figsize=(7.5, 4.0))
ax.bar(x - w / 2, summary["after_r1_cit"], w, color=C_AFTER, alpha=0.7, edgecolor="white", linewidth=0.5, label="Round 1")
ax.bar(x + w / 2, summary["after_r2_cit"], w, color="#1d4ed8", edgecolor="white", linewidth=0.5, label="Round 2")
for index, delta in enumerate(summary["after_cit_delta"]):
    color = POS if delta >= 0 else NEG
    ax.annotate(f"{delta:+.0f}", (x[index] + w / 2, max(summary['after_r1_cit'][index], summary['after_r2_cit'][index]) + 2), ha="center", fontsize=5.5, fontweight="bold", color=color)
ax.set_xticks(x)
ax.set_xticklabels(dataset_labels, fontsize=5.5)
ax.set_ylabel("Citation Ratio (%)", fontsize=9)
ax.set_title("After.md Citation Ratio: Round 1 vs Round 2", fontsize=11, fontweight="bold")
ax.legend(fontsize=8)
ax.set_ylim(0, 100)
ax.grid(axis="y", alpha=0.3)
fig.tight_layout()
fig.savefig(IMAGE_DIR / "chart10_volatility_after.png")
plt.close(fig)

fig, ax = plt.subplots(figsize=(7.5, 4.0))
ax.bar(x - w / 2, summary["nozws_r1_cit"], w, color=C_NOZWS, alpha=0.7, edgecolor="white", linewidth=0.5, label="Round 1")
ax.bar(x + w / 2, summary["nozws_r2_cit"], w, color="#b45309", edgecolor="white", linewidth=0.5, label="Round 2")
for index, delta in enumerate(summary["nozws_cit_delta"]):
    color = POS if delta >= 0 else NEG
    ax.annotate(f"{delta:+.0f}", (x[index] + w / 2, max(summary['nozws_r1_cit'][index], summary['nozws_r2_cit'][index]) + 2), ha="center", fontsize=5.5, fontweight="bold", color=color)
ax.set_xticks(x)
ax.set_xticklabels(dataset_labels, fontsize=5.5)
ax.set_ylabel("Citation Ratio (%)", fontsize=9)
ax.set_title("After_nozws.md Citation Ratio: Round 1 vs Round 2", fontsize=11, fontweight="bold")
ax.legend(fontsize=8)
ax.set_ylim(0, 100)
ax.grid(axis="y", alpha=0.3)
fig.tight_layout()
fig.savefig(IMAGE_DIR / "chart11_volatility_nozws.png")
plt.close(fig)

fig, ax = plt.subplots(figsize=(7.5, 3.2))
colors_delta = [POS if value >= 0 else NEG for value in summary["after_cit_delta"]]
bars = ax.bar(x, summary["after_cit_delta"], color=colors_delta, edgecolor="white", linewidth=0.5)
for bar, val in zip(bars, summary["after_cit_delta"]):
    y_pos = bar.get_height() + 1.5 if val >= 0 else bar.get_height() - 3
    ax.text(bar.get_x() + bar.get_width() / 2, y_pos, f"{val:+.1f}", ha="center", va="bottom" if val >= 0 else "top", fontsize=5.5, fontweight="bold")
ax.axhline(y=0, color="gray", linewidth=0.5, linestyle="-")
mean_delta = np.mean(summary["after_cit_delta"])
ax.axhline(y=mean_delta, color=C_AFTER, linewidth=1, linestyle="--", label=f"Mean: {mean_delta:+.1f}pp")
ax.set_xticks(x)
ax.set_xticklabels(dataset_labels, fontsize=5.5)
ax.set_ylabel("Citation Ratio Δ (pp)", fontsize=9)
ax.set_title("Test-Retest Volatility: After.md R2 − R1 Citation Delta", fontsize=11, fontweight="bold")
ax.legend(fontsize=8)
ax.grid(axis="y", alpha=0.3)
fig.tight_layout()
fig.savefig(IMAGE_DIR / "chart12_volatility_delta.png")
plt.close(fig)

fig, ax = plt.subplots(figsize=(7.5, 4.0))
ax.bar(x - w / 2, summary["zws_eff_r1"], w, color="#a78bfa", alpha=0.8, edgecolor="white", linewidth=0.5, label="Round 1 ZWS Effect")
ax.bar(x + w / 2, summary["zws_eff_r2"], w, color=C_ZWS, edgecolor="white", linewidth=0.5, label="Round 2 ZWS Effect")
for index in range(len(datasets)):
    ax.annotate(f"{summary['zws_eff_r1'][index]:+.0f}", (x[index] - w / 2, summary['zws_eff_r1'][index] + (2 if summary['zws_eff_r1'][index] >= 0 else -5)), ha="center", fontsize=5, fontweight="bold", color="#7c3aed")
    ax.annotate(f"{summary['zws_eff_r2'][index]:+.0f}", (x[index] + w / 2, summary['zws_eff_r2'][index] + (2 if summary['zws_eff_r2'][index] >= 0 else -5)), ha="center", fontsize=5, fontweight="bold", color=C_ZWS)
ax.axhline(y=0, color="gray", linewidth=0.5, linestyle="-")
ax.set_xticks(x)
ax.set_xticklabels(dataset_labels, fontsize=5.5)
ax.set_ylabel("ZWS Effect (pp)", fontsize=9)
ax.set_title("ZWS Effect Stability: Round 1 vs Round 2", fontsize=11, fontweight="bold")
ax.legend(fontsize=8)
ax.grid(axis="y", alpha=0.3)
fig.tight_layout()
fig.savefig(IMAGE_DIR / "chart13_zws_effect_stability.png")
plt.close(fig)

fig, axes = plt.subplots(1, 3, figsize=(8, 3.0))
metrics_labels = ["After.md", "After_nozws", "ZWS Effect"]
mean_abs = [summary["summary_rows"][label]["mean_abs_citation"] for label in metrics_labels]
std_devs = [summary["summary_rows"][label]["std_citation"] for label in metrics_labels]
max_abs = [summary["summary_rows"][label]["max_abs_citation"] for label in metrics_labels]
colors_bar = [C_AFTER, C_NOZWS, C_ZWS]

axes[0].bar(metrics_labels, mean_abs, color=colors_bar, width=0.45)
axes[0].set_title("Mean |Δ Citation| (pp)", fontsize=9, fontweight="bold")
for index, value in enumerate(mean_abs):
    axes[0].text(index, value + 0.5, f"{value:.1f}", ha="center", fontsize=9, fontweight="bold")
axes[0].set_ylim(0, max(35, max(mean_abs, default=0) + 10))
axes[0].grid(axis="y", alpha=0.3)

axes[1].bar(metrics_labels, std_devs, color=colors_bar, width=0.45)
axes[1].set_title("Std Dev of Δ Citation (pp)", fontsize=9, fontweight="bold")
for index, value in enumerate(std_devs):
    axes[1].text(index, value + 0.5, f"{value:.1f}", ha="center", fontsize=9, fontweight="bold")
axes[1].set_ylim(0, max(40, max(std_devs, default=0) + 10))
axes[1].grid(axis="y", alpha=0.3)

axes[2].bar(metrics_labels, max_abs, color=colors_bar, width=0.45)
axes[2].set_title("Max |Δ Citation| (pp)", fontsize=9, fontweight="bold")
for index, value in enumerate(max_abs):
    axes[2].text(index, value + 0.5, f"{value:.1f}", ha="center", fontsize=9, fontweight="bold")
axes[2].set_ylim(0, max(65, max(max_abs, default=0) + 10))
axes[2].grid(axis="y", alpha=0.3)

fig.suptitle(f"Test-Retest Volatility Summary ({len(datasets)} Datasets × 2 Rounds)", fontsize=11, fontweight="bold")
fig.tight_layout()
fig.savefig(IMAGE_DIR / "chart14_volatility_summary.png")
plt.close(fig)

print("5 volatility charts saved to outputs/charts/")
print("  chart10_volatility_after.png")
print("  chart11_volatility_nozws.png")
print("  chart12_volatility_delta.png")
print("  chart13_zws_effect_stability.png")
print("  chart14_volatility_summary.png")
