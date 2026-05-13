#!/usr/bin/env python3
"""Compare citation stats for after.md vs after_nozws.md."""
import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from geoplus.analysis.experiment_stats import get_target_metrics, load_eval_stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare ZWS vs no-ZWS citation effect")
    parser.add_argument("--dataset", type=int, required=True, help="Dataset number")
    args = parser.parse_args()

    stats_zws = load_eval_stats(args.dataset, "after", 1)
    stats_nozws = load_eval_stats(args.dataset, "after_nozws", 1)
    if not stats_zws or not stats_nozws:
        print("Missing test files")
        return

    ratio_zws, word_ratio_zws = get_target_metrics(args.dataset, "after", 1)
    ratio_nozws, word_ratio_nozws = get_target_metrics(args.dataset, "after_nozws", 1)
    target_zws = stats_zws["ref_count"].get("after.md", 0)
    target_nozws = stats_nozws["ref_count"].get("after_nozws.md", 0)

    sep = "=" * 70
    print(f"\n{sep}")
    print(f"  Dataset {args.dataset} — ZWS vs No-ZWS Citation Comparison")
    print(sep)
    print(f"\n  {'Metric':<30} {'With ZWS (after.md)':>20} {'No ZWS (after_nozws.md)':>22}")
    print("  " + "-" * 72)
    print(f"  {'Citation count':<30} {target_zws:>19d}  {target_nozws:>22d}")
    print(f"  {'Citation ratio':<30} {ratio_zws:>19.1f}% {ratio_nozws:>21.1f}%")
    print(f"  {'Word ratio':<30} {word_ratio_zws:>19.1f}% {word_ratio_nozws:>21.1f}%")
    print(
        f"\n  ZWS effect: citation ratio {ratio_zws - ratio_nozws:+.1f}pp, "
        f"word ratio {word_ratio_zws - word_ratio_nozws:+.1f}pp"
    )
    print(sep + "\n")


if __name__ == "__main__":
    main()
