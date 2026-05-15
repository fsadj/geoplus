#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from common import (
    build_heuristic_article,
    dataset_dir,
    doc_blocks,
    ensure_question,
    load_baseline_answer,
    load_docs,
    read_optional_text,
    source_summary,
    timestamp,
    write_json,
    write_text,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPETITION_ROOT = REPO_ROOT / "competition"
SRC_ROOT = COMPETITION_ROOT / "src"
for path in (str(COMPETITION_ROOT), str(SRC_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from simulator.client import GPTMessagesClient
from simulator.config import load_config


SYSTEM_PROMPT = """你是比赛文章优化器。
你的任务是根据题目、五篇文章和基线引用结果，重写目标文章，使后续模拟评测更容易引用到关键内容。
要求：
1. 只基于给定材料改写，不要引入新事实。
2. 优先强化与题目直接相关的内容，并保留可以被其他文章共同支持的信息。
3. 目标文章要更清晰、更结构化、更便于后续答案生成时引用。
4. 只输出优化后的 markdown 正文，不要解释。"""


def build_user_prompt(question: str, target_index: int, target_doc: dict[str, object], other_docs: list[dict[str, object]], baseline_answer: str) -> str:
    other_block = doc_blocks(other_docs)
    target_content = str(target_doc["content"])
    summary = source_summary([target_doc, *other_docs])
    return (
        f"【题目】\n{question}\n\n"
        f"【目标文章编号】\n{target_index}\n\n"
        f"【目标文章原文】\n{target_content}\n\n"
        f"【其他文章】\n{other_block}\n\n"
        f"【基线引用结果】\n{baseline_answer}\n\n"
        f"【跨文档主题词】\n{summary}\n\n"
        "请输出一篇更适合比赛评测的目标文章。建议保持原意，但把核心信息前置，增加小标题或分段，使其更容易被后续生成答案时引用。"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Optimize one competition article")
    parser.add_argument("-n", type=int, choices=range(1, 6), required=True, help="Target article number")
    parser.add_argument("--dataset", type=int, required=True, help="Dataset id")
    parser.add_argument("--output-dir", default=None, help="Optional explicit output directory")
    args = parser.parse_args()

    base_dir = dataset_dir(args.dataset)
    output_dir = Path(args.output_dir) if args.output_dir else base_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    question, question_path, question_created = ensure_question(args.dataset)
    docs = load_docs(args.dataset)
    target_doc = docs[args.n - 1]
    other_docs = [doc for doc in docs if doc["index"] != args.n]
    baseline_answer, baseline_path = load_baseline_answer(args.dataset)

    config = load_config()
    client = GPTMessagesClient(config)
    user_prompt = build_user_prompt(question, args.n, target_doc, other_docs, baseline_answer)

    strategy = "llm"
    try:
        optimized_text = client.call(
            model=config.answer_model,
            system=SYSTEM_PROMPT,
            user=user_prompt,
            max_tokens=config.answer_max_tokens,
        )
    except Exception:
        strategy = "heuristic"
        optimized_text = build_heuristic_article(question, target_doc, other_docs, baseline_answer)

    if not optimized_text.strip():
        strategy = "heuristic"
        optimized_text = build_heuristic_article(question, target_doc, other_docs, baseline_answer)

    after_path = output_dir / "after.md"
    meta_path = output_dir / "after_meta.json"
    write_text(after_path, optimized_text)
    write_json(
        meta_path,
        {
            "version": 1,
            "dataset_id": args.dataset,
            "target_index": args.n,
            "question_path": str(question_path),
            "question_created": question_created,
            "question": question,
            "baseline_path": str(baseline_path),
            "input_files": [str(doc["path"]) for doc in docs],
            "strategy": strategy,
            "model": config.answer_model,
            "created_at": timestamp(),
            "output_files": {
                "after_md": str(after_path),
                "after_meta_json": str(meta_path),
            },
        },
    )
    print(str(after_path))
    print(str(meta_path))


if __name__ == "__main__":
    main()
