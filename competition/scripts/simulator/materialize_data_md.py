#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import replace
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from simulator.answer import generate_answer
from simulator.client import GPTMessagesClient
from simulator.config import load_config
from simulator.data import parse_json_item_text
from simulator.judge import judge_answer
from simulator.objective import score_objective

CODE_BLOCK_RE = re.compile(r"```json\n(.*?)\n```", re.DOTALL)
HEADING_RE = re.compile(r"^##\s+(.*)$", re.MULTILINE)


def extract_items(markdown_text: str) -> list[tuple[str, str]]:
    headings = HEADING_RE.findall(markdown_text)
    blocks = CODE_BLOCK_RE.findall(markdown_text)
    if len(headings) != len(blocks):
        raise ValueError(f"heading count {len(headings)} does not match json block count {len(blocks)}")
    return list(zip(headings, blocks, strict=True))


def write_baseline_dataset(dataset_id: int, item) -> None:
    base_dir = REPO_ROOT / "data" / "baseline" / str(dataset_id)
    base_dir.mkdir(parents=True, exist_ok=True)
    (base_dir / "question.md").write_text(item.query.strip() + "\n", encoding="utf-8")
    (base_dir / "before.md").write_text(item.target.content.strip() + "\n", encoding="utf-8")
    competitors = [doc for doc in item.texts if doc.source_id != item.target.source_id]
    for index, doc in enumerate(competitors, start=1):
        (base_dir / f"{index}.md").write_text(doc.content.strip() + "\n", encoding="utf-8")


def build_simulator_payload(item, before_answer: str, objective, judge) -> dict:
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
        "生成的原始答案": before_answer,
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


def write_simulator_item(dataset_id: int, payload: dict) -> Path:
    output_dir = REPO_ROOT / "outputs" / "datasets" / str(dataset_id)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"simulator_item_ds{dataset_id}.json"
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Materialize curated markdown JSON items into runnable datasets")
    parser.add_argument("--source", default=str(REPO_ROOT / "data.md"), help="Markdown file containing official-style JSON blocks")
    parser.add_argument("--start-id", type=int, default=101, help="First dataset id to assign")
    args = parser.parse_args()

    source_path = Path(args.source)
    markdown_text = source_path.read_text(encoding="utf-8")
    extracted = extract_items(markdown_text)

    config = load_config()
    client = GPTMessagesClient(config)
    manifest: list[dict] = []

    for offset, (heading, block) in enumerate(extracted):
        dataset_id = args.start_id + offset
        parsed_item = parse_json_item_text(block, item_id=f"data_md_{dataset_id}", input_mode="strict")
        trusted_item = replace(parsed_item, generated_original_answer=None, visibility_before=None)

        before_answer = generate_answer(client, config, trusted_item).answer_text
        objective = score_objective(before_answer, target_source_id=trusted_item.target.source_id)
        judge = judge_answer(client, config, trusted_item, before_answer)

        write_baseline_dataset(dataset_id, trusted_item)
        payload = build_simulator_payload(trusted_item, before_answer, objective, judge)
        output_path = write_simulator_item(dataset_id, payload)

        manifest.append(
            {
                "dataset_id": dataset_id,
                "heading": heading,
                "query": trusted_item.query,
                "target_source_id": trusted_item.target.source_id,
                "baseline_dir": f"data/baseline/{dataset_id}",
                "simulator_item": f"outputs/datasets/{dataset_id}/simulator_item_ds{dataset_id}.json",
                "before_total": payload["待优化文本的可见性分数"]["final_score"],
            }
        )
        print(json.dumps(manifest[-1], ensure_ascii=False))

    manifest_path = REPO_ROOT / "outputs" / "curated_data_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"manifest_path={manifest_path}")


if __name__ == "__main__":
    main()
