#!/usr/bin/env python3
"""Analyze round-1 vs round-2 citation volatility."""
import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from geoplus.analysis.experiment_stats import summarize_volatility


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze test-retest volatility")
    parser.add_argument("--round-a", type=int, default=1, help="First round number")
    parser.add_argument("--round-b", type=int, default=2, help="Second round number")
    args = parser.parse_args()

    summary = summarize_volatility(args.round_a, args.round_b)
    labels = summary["labels"]
    round_a = summary["round_a"]
    round_b = summary["round_b"]

    print("=" * 100)
    print(f"  VOLATILITY ANALYSIS: Round {round_a} vs Round {round_b}")
    print("=" * 100)

    print("\n── After.md (With ZWS) ──")
    print(f"{'DS':<6} {'R1 Cit%':>8} {'R2 Cit%':>8} {'Δ Cit':>8} {'R1 Word%':>8} {'R2 Word%':>8} {'Δ Word':>8}")
    print("-" * 80)
    for label, c1, c2, dc, w1, w2, dw in zip(
        labels,
        summary["after_r1_cit"],
        summary["after_r2_cit"],
        summary["after_cit_delta"],
        summary["after_r1_word"],
        summary["after_r2_word"],
        summary["after_word_delta"],
    ):
        print(f"{label:<6} {c1:>7.1f}% {c2:>7.1f}% {dc:>+7.1f}  {w1:>7.1f}% {w2:>7.1f}% {dw:>+7.1f}")
    print("-" * 80)
    print(
        f"  {'Mean Abs Δ':<20} {'':>8} {'':>8} "
        f"{summary['summary_rows']['After.md']['mean_abs_citation']:>7.1f}"
        f"  {'':>8} {'':>8} {summary['summary_rows']['After.md']['mean_abs_word']:>7.1f}"
    )

    print("\n── After_nozws.md (No ZWS) ──")
    print(f"{'DS':<6} {'R1 Cit%':>8} {'R2 Cit%':>8} {'Δ Cit':>8} {'R1 Word%':>8} {'R2 Word%':>8} {'Δ Word':>8}")
    print("-" * 80)
    for label, c1, c2, dc, w1, w2, dw in zip(
        labels,
        summary["nozws_r1_cit"],
        summary["nozws_r2_cit"],
        summary["nozws_cit_delta"],
        summary["nozws_r1_word"],
        summary["nozws_r2_word"],
        summary["nozws_word_delta"],
    ):
        print(f"{label:<6} {c1:>7.1f}% {c2:>7.1f}% {dc:>+7.1f}  {w1:>7.1f}% {w2:>7.1f}% {dw:>+7.1f}")
    print("-" * 80)

    print("\n── ZWS Effect Volatility (With ZWS − No ZWS per round) ──")
    print(f"{'DS':<6} {'R1 ZWS Eff':>10} {'R2 ZWS Eff':>10} {'Δ Eff':>10}")
    print("-" * 56)
    for label, effect_a, effect_b, delta_effect in zip(
        labels,
        summary["zws_eff_r1"],
        summary["zws_eff_r2"],
        summary["zws_eff_delta"],
    ):
        print(f"{label:<6} {effect_a:>+9.1f}pp {effect_b:>+9.1f}pp {delta_effect:>+9.1f}pp")
    print("-" * 56)

    print("\n" + "=" * 80)
    print("  SUMMARY: Test-Retest Volatility Metrics")
    print("=" * 80)
    print(f"\n  {'Metric':<35} {'After.md':>14} {'After_nozws':>14} {'ZWS Effect':>14}")
    print("  " + "-" * 77)
    print(
        f"  {'Mean Absolute Δ Citation (pp)':<35}"
        f" {summary['summary_rows']['After.md']['mean_abs_citation']:>13.1f}pp"
        f" {summary['summary_rows']['After_nozws']['mean_abs_citation']:>13.1f}pp"
        f" {summary['summary_rows']['ZWS Effect']['mean_abs_citation']:>13.1f}pp"
    )
    print(
        f"  {'Mean Absolute Δ Word (pp)':<35}"
        f" {summary['summary_rows']['After.md']['mean_abs_word']:>13.1f}pp"
        f" {summary['summary_rows']['After_nozws']['mean_abs_word']:>13.1f}pp"
        f" {summary['summary_rows']['ZWS Effect']['mean_abs_word']:>13.1f}pp"
    )
    print(
        f"\n  {'Std Dev of Δ Citation':<35}"
        f" {summary['summary_rows']['After.md']['std_citation']:>13.1f}pp"
        f" {summary['summary_rows']['After_nozws']['std_citation']:>13.1f}pp"
        f" {summary['summary_rows']['ZWS Effect']['std_citation']:>13.1f}pp"
    )
    print(
        f"  {'Max |Δ Citation|':<35}"
        f" {summary['summary_rows']['After.md']['max_abs_citation']:>13.1f}pp"
        f" {summary['summary_rows']['After_nozws']['max_abs_citation']:>13.1f}pp"
        f" {summary['summary_rows']['ZWS Effect']['max_abs_citation']:>13.1f}pp"
    )
    print(f"  ZWS effect sign flips between rounds: {summary['zws_sign_flips']}/{len(labels)}")
    print()


if __name__ == "__main__":
    main()
