#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from simulator.answer import generate_answer
from simulator.client import GPTMessagesClient
from simulator.config import load_config
from simulator.data import load_markdown_item, parse_dataset_ids
from simulator.judge import judge_answer
from simulator.objective import score_objective


def output_path_for_dataset(dataset_id: int) -> Path:
    return REPO_ROOT / "outputs" / "datasets" / str(dataset_id) / f"simulator_item_ds{dataset_id}.json"


def build_payload(dataset_id: int, client: GPTMessagesClient) -> dict:
    config = client.config
    item = load_markdown_item(dataset_id)
    answer = generate_answer(client, config, item).answer_text
    objective = score_objective(answer, target_source_id=item.target.source_id)
    judge = judge_answer(client, config, item, answer)
    return {
        "用户查询": item.query,
        "文本列表": [
            {
                "文本序号": doc.source_id,
                "位于传统搜索引擎搜索答案列表的位次": doc.search_rank,
                "url链接": doc.url,
                "标题": doc.title,
                "内容": doc.content,
            }
            for doc in item.texts
        ],
        "待优化文本的序号": item.target.source_id,
        "生成的原始答案": answer,
        "待优化文本的可见性分数": {
            "word_volu": objective.word_volu,
            "posi_prom": objective.posi_prom,
            "word_posi": objective.word_posi,
            "rele": judge.relevance,
            "infl": judge.fluency,
            "div": judge.diversity,
            "uniq": judge.uniqueness,
            "clic": judge.click_follow,
            "subj_posi": judge.prominence,
            "subj_volu": judge.content_volume,
            "aver_subj": judge.total,
            "final_score": 0.5 * objective.word_posi + 0.5 * judge.total,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Export official-style simulator JSON items from markdown datasets")
    parser.add_argument("--datasets", default="3,9,10,12", help="Comma-separated dataset ids")
    parser.add_argument("--force", action="store_true", help="Overwrite existing simulator item files")
    args = parser.parse_args()

    config = load_config()
    client = GPTMessagesClient(config)
    for dataset_id in parse_dataset_ids(args.datasets):
        output_path = output_path_for_dataset(dataset_id)
        if output_path.exists() and not args.force:
            print(f"skip dataset={dataset_id} path={output_path}")
            continue
        payload = build_payload(dataset_id, client)
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(
            json.dumps(
                {
                    "dataset": dataset_id,
                    "path": str(output_path),
                    "before_total": payload["待优化文本的可见性分数"]["final_score"],
                },
                ensure_ascii=False,
            )
        )


if __name__ == "__main__":
    main()
