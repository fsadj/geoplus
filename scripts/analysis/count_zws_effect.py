#!/usr/bin/env python3
"""Compare citation stats for after.md vs after_nozws.md."""
import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from geoplus.analysis.reference_stats import build_valid_ref_pattern, count_references
from geoplus.paths import dataset_file

VALID_REF_PATTERN = build_valid_ref_pattern(
    "before.md",
    "after.md",
    "after_nozws.md",
    "test_before.md",
    "test_after.md",
    "test_after_nozws.md",
)


def main():
    parser = argparse.ArgumentParser(description="Compare ZWS vs no-ZWS citation effect")
    parser.add_argument("--dataset", type=int, required=True, help="Dataset number")
    args = parser.parse_args()

    stats_zws = count_references(dataset_file(args.dataset, "test_after.md"), VALID_REF_PATTERN)
    stats_nozws = count_references(dataset_file(args.dataset, "test_after_nozws.md"), VALID_REF_PATTERN)
    if not stats_zws or not stats_nozws:
        print("Missing test files")
        return

    target_zws = stats_zws["ref_count"].get("after.md", 0)
    target_nozws = stats_nozws["ref_count"].get("after_nozws.md", 0)
    total_zws = stats_zws["total_ref"]
    total_nozws = stats_nozws["total_ref"]
    ratio_zws = (target_zws / total_zws * 100) if total_zws > 0 else 0
    ratio_nozws = (target_nozws / total_nozws * 100) if total_nozws > 0 else 0

    word_zws = stats_zws["ref_words"].get("after.md", 0)
    word_nozws = stats_nozws["ref_words"].get("after_nozws.md", 0)
    total_word_zws = stats_zws["total_words"]
    total_word_nozws = stats_nozws["total_words"]
    word_ratio_zws = (word_zws / total_word_zws * 100) if total_word_zws > 0 else 0
    word_ratio_nozws = (word_nozws / total_word_nozws * 100) if total_word_nozws > 0 else 0

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
