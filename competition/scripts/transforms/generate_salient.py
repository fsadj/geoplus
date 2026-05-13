#!/usr/bin/env python3
"""Generate after_salient.md for specified datasets."""
import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from geoplus.paths import dataset_file
from geoplus.transforms.zws_strategies import build_salient_document


def main():
    parser = argparse.ArgumentParser(description="Generate after_salient.md")
    parser.add_argument("--dataset", type=int, help="Single dataset number (1-14)")
    parser.add_argument("--all", action="store_true", help="Process all 14 datasets")
    args = parser.parse_args()

    if args.dataset:
        datasets = [args.dataset]
    elif args.all:
        datasets = list(range(1, 15))
    else:
        datasets = list(range(1, 6))

    total = 0
    for dataset_id in datasets:
        nozws_path = dataset_file(dataset_id, "after_nozws.md")
        if not nozws_path.exists():
            print(f"DS{dataset_id}: after_nozws.md not found, skip")
            continue

        text = nozws_path.read_text(encoding="utf-8")
        print(f"\n{'=' * 60}")
        print(f"DS{dataset_id}: Processing ({len(text)} chars)")
        print(f"{'=' * 60}")

        result, num_citable, density = build_salient_document(text)
        out_path = dataset_file(dataset_id, "after_salient.md")
        out_path.write_text(result, encoding="utf-8")
        print(f"  Saved: {out_path}")
        print(f"  Summary: {num_citable} citable sentences, ZWS density: {density:.1f}%")
        total += num_citable

    print(f"\nDone. Total citable sentences across {len(datasets)} datasets: {total}")


if __name__ == "__main__":
    main()
