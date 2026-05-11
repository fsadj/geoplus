#!/usr/bin/env python3
"""Generate ZWS vs No-ZWS comparison charts for the report."""
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
    "DS1\nCognition", "DS2\nHormones", "DS3\nLanguage", "DS4\nMemory",
    "DS5\nAI & Jobs", "DS6\nGene Edit", "DS7\nGMO Safety", "DS8\nNuclear",
    "DS9\nAnimal Test", "DS10\nSurveillance", "DS11\nVaccination",
    "DS12\n5G Radiation", "DS13\nCrypto", "DS14\nMetaverse",
]

# ZWS citation ratio
zws_ref_pct  = [36.0, 63.6, 53.6, 57.9, 55.0, 72.2, 70.6, 59.1, 30.8, 38.5, 70.0, 73.9, 57.1, 51.7]
nozws_ref_pct = [31.8, 68.8, 68.2, 41.7, 50.0, 66.7, 62.5, 70.8, 31.2, 14.3, 77.3, 77.8, 40.0, 57.1]
# ZWS word ratio
zws_word_pct  = [99.8, 64.8, 68.4, 69.8, 63.2, 75.2, 67.8, 62.6, 39.2, 39.3, 74.0, 93.0, 69.1, 69.1]
nozws_word_pct = [65.0, 62.7, 74.3, 54.4, 57.3, 77.9, 68.5, 92.4, 31.7, 20.7, 76.6, 79.4, 42.8, 52.0]

ref_delta = [a - b for a, b in zip(zws_ref_pct, nozws_ref_pct)]
word_delta = [a - b for a, b in zip(zws_word_pct, nozws_word_pct)]

C_ZWS = "#3b82f6"
C_NOZWS = "#f59e0b"
C_REF = "#2563eb"
C_WORD = "#7c3aed"
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

# ── Chart 6: ZWS vs No-ZWS — Citation Ratio ──
fig, ax = plt.subplots(figsize=(7.5, 3.5))
x = np.arange(len(datasets))
w = 0.32
ax.bar(x - w/2, zws_ref_pct, w, color=C_ZWS, edgecolor="white", linewidth=0.5, label="With ZWS (after.md)")
ax.bar(x + w/2, nozws_ref_pct, w, color=C_NOZWS, edgecolor="white", linewidth=0.5, label="No ZWS (after_nozws.md)")
for bar, val in zip(ax.patches[:14], zws_ref_pct):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.6, f"{val:.0f}", ha="center", va="bottom", fontsize=5, color=C_ZWS, fontweight="bold")
for bar, val in zip(ax.patches[14:], nozws_ref_pct):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.6, f"{val:.0f}", ha="center", va="bottom", fontsize=5, color=C_NOZWS, fontweight="bold")
ax.set_xticks(x)
ax.set_xticklabels(topics, fontsize=5.5)
ax.set_ylabel("Citation Ratio (%)", fontsize=9)
ax.set_title("ZWS Injection Effect: Citation Ratio With vs Without ZWS", fontsize=11, fontweight="bold")
ax.legend(fontsize=8, loc="upper left")
ax.set_ylim(0, 95)
ax.grid(axis="y", alpha=0.3)
fig.tight_layout()
fig.savefig(IMAGE_DIR / "chart6_zws_citation_comparison.png")
plt.close(fig)

# ── Chart 7: ZWS effect delta (waterfall) ──
fig, ax = plt.subplots(figsize=(7.5, 3.2))
colors = [POS if v > 0 else NEG for v in ref_delta]
bars = ax.bar(x, ref_delta, color=colors, edgecolor="white", linewidth=0.5)
for bar, val in zip(bars, ref_delta):
    y_pos = bar.get_height() + 1.5 if val >= 0 else bar.get_height() - 3
    ax.text(bar.get_x() + bar.get_width()/2, y_pos, f"{val:+.1f}", ha="center", va="bottom" if val >= 0 else "top", fontsize=5.5, fontweight="bold", color=colors[list(ref_delta).index(val)])
ax.axhline(y=0, color="gray", linewidth=0.5, linestyle="-")
ax.axhline(y=np.mean(ref_delta), color=C_REF, linewidth=1, linestyle="--", label=f"Mean: {np.mean(ref_delta):+.1f}pp")
ax.set_xticks(x)
ax.set_xticklabels(topics, fontsize=5.5)
ax.set_ylabel("Citation Ratio Delta (pp)", fontsize=9)
ax.set_title("Net ZWS Effect on Citation Ratio (ZWS − NoZWS)", fontsize=11, fontweight="bold")
ax.legend(fontsize=8)
ax.grid(axis="y", alpha=0.3)
fig.tight_layout()
fig.savefig(IMAGE_DIR / "chart7_zws_delta_citation.png")
plt.close(fig)

# ── Chart 8: ZWS effect on word ratio ──
fig, ax = plt.subplots(figsize=(7.5, 3.5))
ax.bar(x - w/2, zws_word_pct, w, color=C_ZWS, edgecolor="white", linewidth=0.5, label="With ZWS")
ax.bar(x + w/2, nozws_word_pct, w, color=C_NOZWS, edgecolor="white", linewidth=0.5, label="No ZWS")
for bar, val in zip(ax.patches[:14], zws_word_pct):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.6, f"{val:.0f}", ha="center", va="bottom", fontsize=5, color=C_ZWS, fontweight="bold")
for bar, val in zip(ax.patches[14:], nozws_word_pct):
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.6, f"{val:.0f}", ha="center", va="bottom", fontsize=5, color=C_NOZWS, fontweight="bold")
ax.set_xticks(x)
ax.set_xticklabels(topics, fontsize=5.5)
ax.set_ylabel("Word Ratio (%)", fontsize=9)
ax.set_title("ZWS Injection Effect: Word Content Ratio With vs Without ZWS", fontsize=11, fontweight="bold")
ax.legend(fontsize=8, loc="upper left")
ax.set_ylim(0, 115)
ax.grid(axis="y", alpha=0.3)
fig.tight_layout()
fig.savefig(IMAGE_DIR / "chart8_zws_word_comparison.png")
plt.close(fig)

# ── Chart 9: Summary — avg with vs without ZWS ──
fig, axes = plt.subplots(1, 2, figsize=(6.5, 3.2))
avg_zws_ref = np.mean(zws_ref_pct)
avg_nozws_ref = np.mean(nozws_ref_pct)
axes[0].bar(["With ZWS"], [avg_zws_ref], color=C_ZWS, width=0.35)
axes[0].bar(["No ZWS"], [avg_nozws_ref], color=C_NOZWS, width=0.35)
axes[0].text(0, avg_zws_ref + 1.5, f"{avg_zws_ref:.1f}%", ha="center", fontsize=10, fontweight="bold", color=C_ZWS)
axes[0].text(1, avg_nozws_ref + 1.5, f"{avg_nozws_ref:.1f}%", ha="center", fontsize=10, fontweight="bold", color=C_NOZWS)
axes[0].set_ylabel("%", fontsize=9)
axes[0].set_title("Avg Citation Ratio", fontsize=10, fontweight="bold")
axes[0].set_ylim(0, 70)
axes[0].grid(axis="y", alpha=0.3)

avg_zws_word = np.mean(zws_word_pct)
avg_nozws_word = np.mean(nozws_word_pct)
axes[1].bar(["With ZWS"], [avg_zws_word], color=C_ZWS, width=0.35)
axes[1].bar(["No ZWS"], [avg_nozws_word], color=C_NOZWS, width=0.35)
axes[1].text(0, avg_zws_word + 1.5, f"{avg_zws_word:.1f}%", ha="center", fontsize=10, fontweight="bold", color=C_ZWS)
axes[1].text(1, avg_nozws_word + 1.5, f"{avg_nozws_word:.1f}%", ha="center", fontsize=10, fontweight="bold", color=C_NOZWS)
axes[1].set_ylabel("%", fontsize=9)
axes[1].set_title("Avg Word Ratio", fontsize=10, fontweight="bold")
axes[1].set_ylim(0, 75)
axes[1].grid(axis="y", alpha=0.3)

fig.suptitle("ZWS Injection: Average Effect Across 14 Datasets", fontsize=11, fontweight="bold")
fig.tight_layout()
fig.savefig(IMAGE_DIR / "chart9_zws_avg_summary.png")
plt.close(fig)

print("4 ZWS charts saved to outputs/charts/")
print(f"  chart6_zws_citation_comparison.png")
print(f"  chart7_zws_delta_citation.png")
print(f"  chart8_zws_word_comparison.png")
print(f"  chart9_zws_avg_summary.png")
print(f"\nAvg citation delta: {np.mean(ref_delta):+.1f}pp")
print(f"Avg word delta:     {np.mean(word_delta):+.1f}pp")
print(f"Citation: positive in {sum(1 for v in ref_delta if v > 0)}/14, negative in {sum(1 for v in ref_delta if v < 0)}/14")
