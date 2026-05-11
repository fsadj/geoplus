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

from geoplus.paths import charts_dir

IMAGE_DIR = charts_dir()

datasets = list(range(1, 15))
topics = [
    "DS1\nCog", "DS2\nHorm", "DS3\nLang", "DS4\nMem",
    "DS5\nAIJob", "DS6\nGene", "DS7\nGMO", "DS8\nNuke",
    "DS9\nAnim", "DS10\nSurv", "DS11\nVacc",
    "DS12\n5G", "DS13\nCrypt", "DS14\nMeta",
]

# Data from analyze_volatility.py output
after_r1_cit = [26.1, 61.3, 50.0, 50.0, 50.0, 60.0, 35.7, 58.6, 42.9, 35.0, 62.5, 68.2, 66.7, 66.7]
after_r2_cit = [67.5, 65.0, 42.4, 51.9, 47.8, 64.7, 71.4, 52.0, 41.7, 47.4, 71.4, 83.3, 25.0, 50.0]
after_cit_delta = [r2 - r1 for r1, r2 in zip(after_r1_cit, after_r2_cit)]

nozws_r1_cit = [44.8, 66.7, 37.0, 68.0, 55.6, 60.0, 66.7, 38.5, 27.3, 25.0, 60.0, 76.5, 56.2, 58.8]
nozws_r2_cit = [39.1, 56.2, 58.3, 46.2, 68.8, 57.1, 46.2, 63.3, 18.2, 0.0, 54.5, 63.6, 50.0, 48.1]
nozws_cit_delta = [r2 - r1 for r1, r2 in zip(nozws_r1_cit, nozws_r2_cit)]

zws_eff_r1 = [a - n for a, n in zip(after_r1_cit, nozws_r1_cit)]
zws_eff_r2 = [a - n for a, n in zip(after_r2_cit, nozws_r2_cit)]
zws_eff_delta = [r2 - r1 for r1, r2 in zip(zws_eff_r1, zws_eff_r2)]

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

# ── Chart 10: After.md R1 vs R2 scatter ──
fig, ax = plt.subplots(figsize=(7.5, 4.0))
x = np.arange(len(datasets))
w = 0.32
ax.bar(x - w/2, after_r1_cit, w, color=C_AFTER, alpha=0.7, edgecolor="white", linewidth=0.5, label="Round 1")
ax.bar(x + w/2, after_r2_cit, w, color="#1d4ed8", edgecolor="white", linewidth=0.5, label="Round 2")
for i in range(14):
    delta = after_cit_delta[i]
    color = POS if delta >= 0 else NEG
    mid = (x[i] - w/2 + x[i] + w/2) / 2 + w/2
    ax.annotate(f"{delta:+.0f}", (x[i] + w/2, max(after_r1_cit[i], after_r2_cit[i]) + 2),
                ha="center", fontsize=5.5, fontweight="bold", color=color)
ax.set_xticks(x)
ax.set_xticklabels(topics, fontsize=5.5)
ax.set_ylabel("Citation Ratio (%)", fontsize=9)
ax.set_title("After.md Citation Ratio: Round 1 vs Round 2", fontsize=11, fontweight="bold")
ax.legend(fontsize=8)
ax.set_ylim(0, 100)
ax.grid(axis="y", alpha=0.3)
fig.tight_layout()
fig.savefig(IMAGE_DIR / "chart10_volatility_after.png")
plt.close(fig)

# ── Chart 11: After_nozws.md R1 vs R2 scatter ──
fig, ax = plt.subplots(figsize=(7.5, 4.0))
ax.bar(x - w/2, nozws_r1_cit, w, color=C_NOZWS, alpha=0.7, edgecolor="white", linewidth=0.5, label="Round 1")
ax.bar(x + w/2, nozws_r2_cit, w, color="#b45309", edgecolor="white", linewidth=0.5, label="Round 2")
for i in range(14):
    delta = nozws_cit_delta[i]
    color = POS if delta >= 0 else NEG
    ax.annotate(f"{delta:+.0f}", (x[i] + w/2, max(nozws_r1_cit[i], nozws_r2_cit[i]) + 2),
                ha="center", fontsize=5.5, fontweight="bold", color=color)
ax.set_xticks(x)
ax.set_xticklabels(topics, fontsize=5.5)
ax.set_ylabel("Citation Ratio (%)", fontsize=9)
ax.set_title("After_nozws.md Citation Ratio: Round 1 vs Round 2", fontsize=11, fontweight="bold")
ax.legend(fontsize=8)
ax.set_ylim(0, 100)
ax.grid(axis="y", alpha=0.3)
fig.tight_layout()
fig.savefig(IMAGE_DIR / "chart11_volatility_nozws.png")
plt.close(fig)

# ── Chart 12: Citation delta waterfall ──
fig, ax = plt.subplots(figsize=(7.5, 3.2))
colors_delta = [POS if v >= 0 else NEG for v in after_cit_delta]
bars = ax.bar(x, after_cit_delta, color=colors_delta, edgecolor="white", linewidth=0.5)
for bar, val in zip(bars, after_cit_delta):
    y_pos = bar.get_height() + 1.5 if val >= 0 else bar.get_height() - 3
    ax.text(bar.get_x() + bar.get_width()/2, y_pos, f"{val:+.1f}", ha="center",
            va="bottom" if val >= 0 else "top", fontsize=5.5, fontweight="bold")
ax.axhline(y=0, color="gray", linewidth=0.5, linestyle="-")
mean_delta = np.mean(after_cit_delta)
ax.axhline(y=mean_delta, color=C_AFTER, linewidth=1, linestyle="--",
           label=f"Mean: {mean_delta:+.1f}pp")
ax.set_xticks(x)
ax.set_xticklabels(topics, fontsize=5.5)
ax.set_ylabel("Citation Ratio Δ (pp)", fontsize=9)
ax.set_title("Test-Retest Volatility: After.md R2 − R1 Citation Delta", fontsize=11, fontweight="bold")
ax.legend(fontsize=8)
ax.grid(axis="y", alpha=0.3)
fig.tight_layout()
fig.savefig(IMAGE_DIR / "chart12_volatility_delta.png")
plt.close(fig)

# ── Chart 13: ZWS Effect R1 vs R2 ──
fig, ax = plt.subplots(figsize=(7.5, 4.0))
ax.bar(x - w/2, zws_eff_r1, w, color="#a78bfa", alpha=0.8, edgecolor="white", linewidth=0.5, label="Round 1 ZWS Effect")
ax.bar(x + w/2, zws_eff_r2, w, color=C_ZWS, edgecolor="white", linewidth=0.5, label="Round 2 ZWS Effect")
for i in range(14):
    ax.annotate(f"{zws_eff_r1[i]:+.0f}", (x[i] - w/2, zws_eff_r1[i] + (2 if zws_eff_r1[i] >= 0 else -5)),
                ha="center", fontsize=5, fontweight="bold", color="#7c3aed")
    ax.annotate(f"{zws_eff_r2[i]:+.0f}", (x[i] + w/2, zws_eff_r2[i] + (2 if zws_eff_r2[i] >= 0 else -5)),
                ha="center", fontsize=5, fontweight="bold", color=C_ZWS)
ax.axhline(y=0, color="gray", linewidth=0.5, linestyle="-")
ax.set_xticks(x)
ax.set_xticklabels(topics, fontsize=5.5)
ax.set_ylabel("ZWS Effect (pp)", fontsize=9)
ax.set_title("ZWS Effect Stability: Round 1 vs Round 2", fontsize=11, fontweight="bold")
ax.legend(fontsize=8)
ax.grid(axis="y", alpha=0.3)
fig.tight_layout()
fig.savefig(IMAGE_DIR / "chart13_zws_effect_stability.png")
plt.close(fig)

# ── Chart 14: Summary volatility metrics ──
fig, axes = plt.subplots(1, 3, figsize=(8, 3.0))

metrics_labels = ["After.md", "After_nozws", "ZWS Effect"]
mean_abs = [14.3, 13.6, 25.3]
std_devs = [20.5, 15.2, 29.1]
max_abs = [41.7, 25.0, 56.2]
colors_bar = [C_AFTER, C_NOZWS, C_ZWS]

axes[0].bar(metrics_labels, mean_abs, color=colors_bar, width=0.45)
axes[0].set_title("Mean |Δ Citation| (pp)", fontsize=9, fontweight="bold")
for i, v in enumerate(mean_abs):
    axes[0].text(i, v + 0.5, f"{v:.1f}", ha="center", fontsize=9, fontweight="bold")
axes[0].set_ylim(0, 35)
axes[0].grid(axis="y", alpha=0.3)

axes[1].bar(metrics_labels, std_devs, color=colors_bar, width=0.45)
axes[1].set_title("Std Dev of Δ Citation (pp)", fontsize=9, fontweight="bold")
for i, v in enumerate(std_devs):
    axes[1].text(i, v + 0.5, f"{v:.1f}", ha="center", fontsize=9, fontweight="bold")
axes[1].set_ylim(0, 40)
axes[1].grid(axis="y", alpha=0.3)

axes[2].bar(metrics_labels, max_abs, color=colors_bar, width=0.45)
axes[2].set_title("Max |Δ Citation| (pp)", fontsize=9, fontweight="bold")
for i, v in enumerate(max_abs):
    axes[2].text(i, v + 0.5, f"{v:.1f}", ha="center", fontsize=9, fontweight="bold")
axes[2].set_ylim(0, 65)
axes[2].grid(axis="y", alpha=0.3)

fig.suptitle("Test-Retest Volatility Summary (14 Datasets × 2 Rounds)", fontsize=11, fontweight="bold")
fig.tight_layout()
fig.savefig(IMAGE_DIR / "chart14_volatility_summary.png")
plt.close(fig)

print("5 volatility charts saved to outputs/charts/")
print("  chart10_volatility_after.png")
print("  chart11_volatility_nozws.png")
print("  chart12_volatility_delta.png")
print("  chart13_zws_effect_stability.png")
print("  chart14_volatility_summary.png")
