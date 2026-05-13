#!/usr/bin/env python3
"""Strip zero-width spaces from after.md files."""
import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from geoplus.paths import dataset_file

ZERO_WIDTH_SPACE = "​"


def main():
    parser = argparse.ArgumentParser(description="Strip ZWS from after.md")
    parser.add_argument("--dataset", type=int, help="Dataset number (1-14), or omit for all")
    args = parser.parse_args()

    datasets = [args.dataset] if args.dataset else list(range(1, 15))
    for dataset_id in datasets:
        after_path = dataset_file(dataset_id, "after.md")
        if not after_path.exists():
            print(f"  DS{dataset_id}: after.md not found, skip")
            continue

        text = after_path.read_text(encoding="utf-8")
        zwsp_count = text.count(ZERO_WIDTH_SPACE)
        cleaned = text.replace(ZERO_WIDTH_SPACE, "")

        out_path = dataset_file(dataset_id, "after_nozws.md")
        out_path.write_text(cleaned, encoding="utf-8")
        ratio = (zwsp_count / len(text) * 100) if text else 0
        print(f"  DS{dataset_id}: removed {zwsp_count} ZWS (was {ratio:.1f}% of {len(text)} chars) -> saved {len(cleaned)} chars")

    print("\nDone.")


if __name__ == "__main__":
    main()
