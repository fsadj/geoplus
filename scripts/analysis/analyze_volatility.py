#!/usr/bin/env python3
"""Analyze round-1 vs round-2 citation volatility."""
import statistics
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from geoplus.analysis.reference_stats import (
    build_valid_ref_pattern,
    count_references,
    get_target_ratios,
)
from geoplus.paths import dataset_file

VALID_REF_PATTERN = build_valid_ref_pattern(
    "before.md",
    "after.md",
    "after_nozws.md",
    "test_before.md",
    "test_after.md",
    "test_after_r2.md",
    "test_after_nozws.md",
    "test_after_nozws_r2.md",
)


def main():
    datasets = list(range(1, 15))
    topics = [
        "Cognition",
        "Hormones",
        "Language",
        "Memory",
        "AI & Jobs",
        "Gene Edit",
        "GMO Safety",
        "Nuclear",
        "Animal Test",
        "Surveillance",
        "Vaccination",
        "5G Radiation",
        "Crypto",
        "Metaverse",
    ]

    print("=" * 100)
    print("  VOLATILITY ANALYSIS: Round 1 vs Round 2")
    print("=" * 100)

    print("\n── After.md (With ZWS) ──")
    print(f"{'DS':<4} {'Topic':<16} {'R1 Cit%':>8} {'R2 Cit%':>8} {'Δ Cit':>8} {'R1 Word%':>8} {'R2 Word%':>8} {'Δ Word':>8}")
    print("-" * 80)
    after_cit_deltas = []
    after_word_deltas = []
    for dataset_id in datasets:
        r1 = count_references(dataset_file(dataset_id, "test_after.md"), VALID_REF_PATTERN)
        r2 = count_references(dataset_file(dataset_id, "test_after_r2.md"), VALID_REF_PATTERN)
        c1, w1 = get_target_ratios(r1, "after.md")
        c2, w2 = get_target_ratios(r2, "after.md")
        dc = c2 - c1
        dw = w2 - w1
        after_cit_deltas.append(dc)
        after_word_deltas.append(dw)
        print(f"DS{dataset_id:<2} {topics[dataset_id - 1]:<16} {c1:>7.1f}% {c2:>7.1f}% {dc:>+7.1f}  {w1:>7.1f}% {w2:>7.1f}% {dw:>+7.1f}")
    print("-" * 80)
    print(f"  {'Mean Abs Δ':<20} {'':>8} {'':>8} {statistics.mean(abs(v) for v in after_cit_deltas):>7.1f}  {'':>8} {'':>8} {statistics.mean(abs(v) for v in after_word_deltas):>7.1f}")

    print("\n── After_nozws.md (No ZWS) ──")
    print(f"{'DS':<4} {'Topic':<16} {'R1 Cit%':>8} {'R2 Cit%':>8} {'Δ Cit':>8} {'R1 Word%':>8} {'R2 Word%':>8} {'Δ Word':>8}")
    print("-" * 80)
    nozws_cit_deltas = []
    nozws_word_deltas = []
    for dataset_id in datasets:
        r1 = count_references(dataset_file(dataset_id, "test_after_nozws.md"), VALID_REF_PATTERN)
        r2 = count_references(dataset_file(dataset_id, "test_after_nozws_r2.md"), VALID_REF_PATTERN)
        c1, w1 = get_target_ratios(r1, "after_nozws.md")
        c2, w2 = get_target_ratios(r2, "after_nozws.md")
        dc = c2 - c1
        dw = w2 - w1
        nozws_cit_deltas.append(dc)
        nozws_word_deltas.append(dw)
        print(f"DS{dataset_id:<2} {topics[dataset_id - 1]:<16} {c1:>7.1f}% {c2:>7.1f}% {dc:>+7.1f}  {w1:>7.1f}% {w2:>7.1f}% {dw:>+7.1f}")
    print("-" * 80)

    print("\n── ZWS Effect Volatility (With ZWS − No ZWS per round) ──")
    print(f"{'DS':<4} {'Topic':<16} {'R1 ZWS Eff':>10} {'R2 ZWS Eff':>10} {'Δ Eff':>10}")
    print("-" * 56)
    zws_effect_deltas = []
    for dataset_id in datasets:
        r1_after = count_references(dataset_file(dataset_id, "test_after.md"), VALID_REF_PATTERN)
        r1_nozws = count_references(dataset_file(dataset_id, "test_after_nozws.md"), VALID_REF_PATTERN)
        r2_after = count_references(dataset_file(dataset_id, "test_after_r2.md"), VALID_REF_PATTERN)
        r2_nozws = count_references(dataset_file(dataset_id, "test_after_nozws_r2.md"), VALID_REF_PATTERN)
        c1_after, _ = get_target_ratios(r1_after, "after.md")
        c1_nozws, _ = get_target_ratios(r1_nozws, "after_nozws.md")
        c2_after, _ = get_target_ratios(r2_after, "after.md")
        c2_nozws, _ = get_target_ratios(r2_nozws, "after_nozws.md")
        effect_r1 = c1_after - c1_nozws
        effect_r2 = c2_after - c2_nozws
        delta_effect = effect_r2 - effect_r1
        zws_effect_deltas.append(delta_effect)
        print(f"DS{dataset_id:<2} {topics[dataset_id - 1]:<16} {effect_r1:>+9.1f}pp {effect_r2:>+9.1f}pp {delta_effect:>+9.1f}pp")
    print("-" * 56)

    print("\n" + "=" * 80)
    print("  SUMMARY: Test-Retest Volatility Metrics")
    print("=" * 80)
    print(f"\n  {'Metric':<35} {'After.md':>14} {'After_nozws':>14} {'ZWS Effect':>14}")
    print("  " + "-" * 77)
    print(
        f"  {'Mean Absolute Δ Citation (pp)':<35}"
        f" {statistics.mean(abs(v) for v in after_cit_deltas):>13.1f}pp"
        f" {statistics.mean(abs(v) for v in nozws_cit_deltas):>13.1f}pp"
        f" {statistics.mean(abs(v) for v in zws_effect_deltas):>13.1f}pp"
    )
    print(
        f"  {'Mean Absolute Δ Word (pp)':<35}"
        f" {statistics.mean(abs(v) for v in after_word_deltas):>13.1f}pp"
        f" {statistics.mean(abs(v) for v in nozws_word_deltas):>13.1f}pp"
        f" {0:>13.1f}pp"
    )
    print(
        f"\n  {'Std Dev of Δ Citation':<35}"
        f" {statistics.stdev(after_cit_deltas):>13.1f}pp"
        f" {statistics.stdev(nozws_cit_deltas):>13.1f}pp"
        f" {statistics.stdev(zws_effect_deltas):>13.1f}pp"
    )
    print(
        f"  {'Max |Δ Citation|':<35}"
        f" {max(abs(v) for v in after_cit_deltas):>13.1f}pp"
        f" {max(abs(v) for v in nozws_cit_deltas):>13.1f}pp"
        f" {max(abs(v) for v in zws_effect_deltas):>13.1f}pp"
    )

    zws_flips = 0
    for dataset_id in datasets:
        r1_after = count_references(dataset_file(dataset_id, "test_after.md"), VALID_REF_PATTERN)
        r1_nozws = count_references(dataset_file(dataset_id, "test_after_nozws.md"), VALID_REF_PATTERN)
        r2_after = count_references(dataset_file(dataset_id, "test_after_r2.md"), VALID_REF_PATTERN)
        r2_nozws = count_references(dataset_file(dataset_id, "test_after_nozws_r2.md"), VALID_REF_PATTERN)
        c1_after, _ = get_target_ratios(r1_after, "after.md")
        c1_nozws, _ = get_target_ratios(r1_nozws, "after_nozws.md")
        c2_after, _ = get_target_ratios(r2_after, "after.md")
        c2_nozws, _ = get_target_ratios(r2_nozws, "after_nozws.md")
        if (c1_after > c1_nozws) != (c2_after > c2_nozws):
            zws_flips += 1
    print(f"  ZWS effect sign flips between rounds: {zws_flips}/14")
    print()


if __name__ == "__main__":
    main()
