#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from dataclasses import asdict
from pathlib import Path

from common import dataset_dir, ensure_question, load_docs, load_baseline_answer, read_text, timestamp, write_json, write_text

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPETITION_ROOT = REPO_ROOT / "competition"
SRC_ROOT = COMPETITION_ROOT / "src"
for path in (str(COMPETITION_ROOT), str(SRC_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from simulator.config import load_config
from simulator.pipeline import evaluate_item_before_after
from simulator.reporting import aggregate_results
from simulator.schemas import ContestItem, SourceDocument


def build_item(dataset_id: int, target_index: int, question: str, docs: list[dict[str, object]], baseline_answer: str) -> ContestItem:
    texts = [
        SourceDocument(
            source_id=int(doc["index"]),
            label=str(doc["name"]),
            title=str(doc["name"]),
            content=str(doc["content"]),
            url=f"file://{doc['path']}",
            search_rank=int(doc["index"]),
        )
        for doc in docs
    ]
    return ContestItem(
        item_id=f"match-{dataset_id}-{target_index}",
        query=question,
        texts=texts,
        target_index=target_index - 1,
        generated_original_answer=baseline_answer,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Judge one competition article")
    parser.add_argument("-n", type=int, choices=range(1, 6), required=True, help="Target article number")
    parser.add_argument("--dataset", type=int, required=True, help="Dataset id")
    parser.add_argument("--output-dir", default=None, help="Optional explicit output directory")
    args = parser.parse_args()

    base_dir = dataset_dir(args.dataset)
    output_dir = Path(args.output_dir) if args.output_dir else base_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    question, _, _ = ensure_question(args.dataset)
    docs = load_docs(args.dataset)
    baseline_answer, baseline_path = load_baseline_answer(args.dataset)
    after_path = output_dir / "after.md"
    after_text = read_text(after_path)

    item = build_item(args.dataset, args.n, question, docs, baseline_answer)
    config = load_config()
    result = evaluate_item_before_after(item, after_text=after_text, after_label=after_path.name, config=config)
    report = aggregate_results([result])

    test_after_path = output_dir / "test_after.md"
    score_path = output_dir / "score.json"
    write_text(test_after_path, result.after.answer)
    write_json(
        score_path,
        {
            "version": 1,
            "dataset_id": args.dataset,
            "target_index": args.n,
            "question": question,
            "baseline_path": str(baseline_path),
            "after_path": str(after_path),
            "test_after_path": str(test_after_path),
            "generated_at": timestamp(),
            "summary": {
                "before_total": report.avg_before_total,
                "after_total": report.avg_after_total,
                "delta": report.avg_delta,
                "objective_delta": report.avg_objective_delta,
                "ai_delta": report.avg_ai_delta,
                "win_rate": report.win_rate,
            },
            "result": report.item_results[0],
            "raw": asdict(report),
        },
    )
    print(str(test_after_path))
    print(str(score_path))


if __name__ == "__main__":
    main()
