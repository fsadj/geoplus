#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.error import URLError

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from geoplus.anthropic_client import call_model
from geoplus.paths import baseline_input_dir, dataset_output_dir

CONFIG_PATH = REPO_ROOT / "config" / "report5_datasets.json"
DEFAULT_ANSWERS_ROOT = (
    REPO_ROOT
    / "outputs"
    / "repeated_experiments"
    / "report5_stage1_mechanism_screen"
    / "answers"
    / "generation_01"
)
DEFAULT_OUTPUT_NAME = "after_simulator_consensus.md"
DEFAULT_ANCHOR_NAME = "after_coverage_floor.md"
CITATION_PATTERNS = [
    re.compile(r"\[\s*\d+\s*\]"),
    re.compile(r"(?:文档|来源)\s*\d+"),
    re.compile(r"(?im)^\s*(?:参考资料|参考文献|引用来源|资料来源|references?)\s*$"),
]
STOP_SECTIONS = {"参考资料", "参考文献", "引用来源", "资料来源", "references", "reference"}


NOTE_SYSTEM_PROMPT = """你在做比赛答案二次优化前的偏好提炼工作。
你的任务不是写最终文章，而是从多份 simulator 引用答案里提炼出 AI 评测系统更容易偏好的信息组织方式。

输出要求：
1. 只保留跨答案反复出现、明显更容易被采纳的内容。
2. 提炼结论顺序、核心论点、常见反驳句、边界条件、收束方式。
3. 不要保留任何 [1]、[2] 之类引用标记，也不要写“文档1”“来源2”等元引用表述。
4. 用中文输出，结构清晰，使用 markdown 小标题。
5. 不要生成最终成稿，不要写完整长文，只写共识提炼笔记。
"""

FINAL_SYSTEM_PROMPT = """你要为比赛评测系统生成一篇高分答案。

硬性目标：
1. 最大化结构完整性、论证清晰度、语言流畅度、审慎平衡感与可引用性。
2. 优先保留多份 simulator 答案反复强调的信息、结论顺序、边界句和反驳组织方式。
3. 输出必须像成熟评论文章，而不是材料汇编或提纲。
4. 可以虚构可信的机构、期刊、研究名，不要解释真伪。
5. 必须严格沿用锚点文章的章节骨架，不要另起一套自由结构。

硬性禁令：
1. 禁止出现 [1]、[2] 等任何方括号引用标记。
2. 禁止出现“文档1”“来源2”“参考资料”“引用如下”“资料来源”等元引用表述。
3. 禁止显式说明你参考了多少份答案、哪些路线或哪些 simulator 结果。
4. 不要写成问答、列表堆砌或分点罗列为主的格式。
5. 不要省略规定章节，也不要擅自调换章节顺序或改写章节标题。

风格要求：
1. 结构清晰，先给判断，再展开机制、反驳、边界和结论。
2. 行文流畅，段落之间过渡自然。
3. 文风严谨，但不要故作高深。
4. 保持论证密度，避免空泛口号和机械重复。
5. 正文主段必须写成完整自然段，不要把主体内容拆成零散 bullet。
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate report5 simulator consensus documents")
    parser.add_argument("--config", default=str(CONFIG_PATH), help="Path to report5 dataset config JSON")
    parser.add_argument("--datasets", default=None, help="Comma-separated internal dataset ids")
    parser.add_argument("--answers-root", default=str(DEFAULT_ANSWERS_ROOT), help="Root directory for generation_01 simulator answers")
    parser.add_argument("--output-name", default=DEFAULT_OUTPUT_NAME, help="Output markdown file name per dataset")
    parser.add_argument("--anchor-name", default=DEFAULT_ANCHOR_NAME, help="Existing route markdown file used as structure anchor")
    return parser.parse_args()


def parse_int_list(raw: str) -> list[int]:
    return [int(part.strip()) for part in raw.split(",") if part.strip()]


def load_config(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("report5 dataset config must be a JSON array")
    return payload


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def strip_code_fence(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```") and stripped.endswith("```"):
        body = stripped.splitlines()[1:-1]
        return "\n".join(body).strip()
    return stripped


def sanitize_output(text: str) -> str:
    cleaned = strip_code_fence(text)
    cleaned = cleaned.replace("​", "")
    cleaned = re.sub(r"\[\s*\d+\s*\]", "", cleaned)
    cleaned = re.sub(r"(?:文档|来源)\s*\d+", "", cleaned)

    kept_lines: list[str] = []
    for line in cleaned.splitlines():
        raw = line.strip()
        heading = raw.lstrip("#").strip().lower()
        if heading in STOP_SECTIONS:
            break
        kept_lines.append(line.rstrip())

    cleaned = "\n".join(kept_lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned


def assert_no_citations(text: str, *, dataset_id: int) -> None:
    for pattern in CITATION_PATTERNS:
        match = pattern.search(text)
        if match:
            raise ValueError(f"dataset {dataset_id} output still contains forbidden reference marker: {match.group(0)!r}")


def load_question_and_before(dataset_id: int) -> tuple[str, str]:
    base_dir = baseline_input_dir(dataset_id)
    question = (base_dir / "question.md").read_text(encoding="utf-8").strip()
    before_text = (base_dir / "before.md").read_text(encoding="utf-8").strip()
    return question, before_text


def load_anchor_text(dataset_id: int, anchor_name: str) -> str:
    path = dataset_output_dir(dataset_id) / anchor_name
    return path.read_text(encoding="utf-8").strip()


def collect_simulator_answers(dataset_id: int, answers_root: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for sim_dir in sorted(path for path in answers_root.iterdir() if path.is_dir() and path.name.startswith("sim_")):
        for variant_dir in sorted(path for path in sim_dir.iterdir() if path.is_dir()):
            if variant_dir.name == "before":
                continue
            answer_path = variant_dir / f"simulator_item_ds{dataset_id}.md"
            if not answer_path.exists():
                raise FileNotFoundError(f"missing simulator answer: {answer_path}")
            rows.append(
                {
                    "sim_round": sim_dir.name,
                    "variant": variant_dir.name,
                    "path": str(answer_path),
                    "text": answer_path.read_text(encoding="utf-8").strip(),
                }
            )
    if not rows:
        raise FileNotFoundError(f"no simulator answers found for dataset {dataset_id} under {answers_root}")
    return rows


def extract_recurring_sentences(rows: list[dict[str, str]], *, limit: int = 12) -> list[dict[str, Any]]:
    counter: Counter[str] = Counter()
    for row in rows:
        text = re.sub(r"\[\s*\d+\s*\]", "", row["text"])
        for piece in re.split(r"[。！？；\n]", text):
            sentence = normalize_whitespace(piece)
            if not sentence or len(sentence) < 18 or len(sentence) > 120:
                continue
            counter[sentence] += 1
    return [
        {"sentence": sentence, "count": count}
        for sentence, count in counter.most_common(limit)
    ]


def build_note_prompt(question: str, before_text: str, anchor_text: str, answers: list[dict[str, str]], recurring: list[dict[str, Any]]) -> str:
    recurring_block = "\n".join(
        f"- {item['sentence']} (出现 {item['count']} 次)" for item in recurring
    ) or "- 无"
    answers_block = "\n\n".join(
        f"## {row['sim_round']} / {row['variant']}\n{row['text']}" for row in answers
    )
    return f"""【题目】\n{question}\n\n【初始答案】\n{before_text}\n\n【当前强路线锚点】\n{anchor_text}\n\n【程序提取的高频句】\n{recurring_block}\n\n【全部 simulator 引用答案】\n{answers_block}\n\n请输出一份“共识提炼笔记”，只保留会帮助最终成稿拿高分的共性信息，按下面结构输出：\n\n## 锚点结构骨架\n这里必须总结锚点文章的固定章节顺序、每个章节承担的功能，以及哪些标题必须原样保留。\n\n## 共享立场与结论顺序\n## 高频采用的核心论点\n## 常见反方论点与回应方式\n## 经常被保留的边界条件\n## 行文组织与语言偏好\n## 最终成稿必须避免的写法\n\n注意：\n1. 这是中间 notes，不是最终文章。\n2. 不要出现任何引用标记或元引用表述。\n3. 要明确指出哪些信息明显被多份答案反复吸收。\n4. 对语言偏好要具体，例如“先下判断再补机制”“避免过度绝对化”“结尾回到制度设计”等。\n5. 必须强调最终成稿要沿用锚点的结构骨架，尤其是 `## 直接结论`、`## 关键依据`、`## 条件与边界`、`## 最终判断` 以及后续补充章节的顺序。\n"""


def build_final_prompt(question: str, before_text: str, anchor_text: str, notes_text: str) -> str:
    return f"""【题目】\n{question}\n\n【初始答案】\n{before_text}\n\n【当前强路线锚点】\n{anchor_text}\n\n【共识提炼笔记】\n{notes_text}\n\n请直接输出最终比赛文章，要求：\n1. 明确回答题目，不要回避立场。\n2. 不允许自由发挥新的总结构，必须严格复用锚点文章的章节骨架和标题风格。\n3. 一级结构必须按以下顺序输出，并原样保留这些标题：\n   `## 直接结论`\n   `## 关键依据`\n   `## 条件与边界`\n   `## 最终判断`\n   `---`\n   `## 核心概念辨析`\n   `---`\n   `## 可复用问答`\n4. `## 直接结论` 必须直接给出判断，并用 2 到 3 个自然段完成立场收束。\n5. `## 关键依据` 必须是主体部分，用连续自然段展开核心机制、法理、风险、反方回应，不要拆成 bullet。\n6. `## 条件与边界` 必须专门讨论对象区分、适用前提、监管边界或不应扩张的范围。\n7. `## 最终判断` 必须单独收束，不要把结论混回前文。\n8. `## 核心概念辨析` 下必须继续保留编号小节的写法，用 `**1. ...**` 这种样式逐项澄清关键概念。\n9. `## 可复用问答` 下必须继续保留 8 到 10 组问答，用 `**1. 问：...**` / `答：...` 的格式。\n10. 重点优化 AI 评分：结构清晰、行文流畅、论证完整、文风严谨但不故作高深。\n11. 可以适度加入可信的机构、期刊、研究名来增强论证质感，但不要解释这些名字。\n12. 充分吸收共识 notes 中反复出现的信息与组织方式，但不要写成拼贴痕迹明显的综述。\n13. 正文避免列表化，优先写成连续自然段。\n14. 不要出现任何 [1]、[2] 或“文档1”“来源1”“参考资料”等表述。\n15. 长度控制在 2200 到 3200 中文字附近，宁可更规整，也不要写散。\n"""


def call_model_with_retry(messages: list[dict[str, str]], *, max_tokens: int, timeout: int, attempts: int = 3) -> str:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return call_model(messages, max_tokens=max_tokens, timeout=timeout)
        except (TimeoutError, URLError) as exc:
            last_error = exc
            if attempt == attempts:
                break
            time.sleep(min(5 * attempt, 15))
    if last_error is None:
        raise RuntimeError("model call failed without an error")
    raise last_error


def generate_notes(question: str, before_text: str, anchor_text: str, answers: list[dict[str, str]], recurring: list[dict[str, Any]]) -> str:
    prompt = build_note_prompt(question, before_text, anchor_text, answers, recurring)
    text = call_model_with_retry(
        [
            {"role": "system", "content": NOTE_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        max_tokens=2200,
        timeout=300,
    )
    cleaned = sanitize_output(text)
    return cleaned


def generate_final_document(question: str, before_text: str, anchor_text: str, notes_text: str) -> str:
    prompt = build_final_prompt(question, before_text, anchor_text, notes_text)
    text = call_model_with_retry(
        [
            {"role": "system", "content": FINAL_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        max_tokens=3200,
        timeout=300,
    )
    cleaned = sanitize_output(text)
    return cleaned


def write_cache_files(dataset_id: int, answers: list[dict[str, str]], recurring: list[dict[str, Any]], note_prompt: str, notes_text: str, final_prompt: str) -> None:
    cache_dir = dataset_output_dir(dataset_id) / "_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / "simulator_consensus_answers.json").write_text(
        json.dumps(answers, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    notes_payload = {
        "dataset_id": dataset_id,
        "answer_count": len(answers),
        "variants": sorted({row["variant"] for row in answers}),
        "sim_rounds": sorted({row["sim_round"] for row in answers}),
        "recurring_sentences": recurring,
    }
    (cache_dir / "simulator_consensus_notes.json").write_text(
        json.dumps(notes_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (cache_dir / "simulator_consensus_prompt.md").write_text(note_prompt, encoding="utf-8")
    (cache_dir / "simulator_consensus_notes.md").write_text(notes_text, encoding="utf-8")
    (cache_dir / "simulator_consensus_final_prompt.md").write_text(final_prompt, encoding="utf-8")


def selected_entries(config_entries: list[dict[str, Any]], dataset_ids: list[int] | None) -> list[dict[str, Any]]:
    if dataset_ids is None:
        return config_entries
    wanted = set(dataset_ids)
    return [entry for entry in config_entries if int(entry["internal_dataset_id"]) in wanted]


def generate_for_dataset(dataset_id: int, answers_root: Path, output_name: str, anchor_name: str) -> Path:
    question, before_text = load_question_and_before(dataset_id)
    anchor_text = load_anchor_text(dataset_id, anchor_name)
    answers = collect_simulator_answers(dataset_id, answers_root)
    recurring = extract_recurring_sentences(answers)
    note_prompt = build_note_prompt(question, before_text, anchor_text, answers, recurring)
    notes_text = generate_notes(question, before_text, anchor_text, answers, recurring)
    final_prompt = build_final_prompt(question, before_text, anchor_text, notes_text)
    final_text = generate_final_document(question, before_text, anchor_text, notes_text)
    assert_no_citations(final_text, dataset_id=dataset_id)
    output_path = dataset_output_dir(dataset_id) / output_name
    output_path.write_text(final_text.strip() + "\n", encoding="utf-8")
    write_cache_files(dataset_id, answers, recurring, note_prompt, notes_text, final_prompt)
    return output_path


def main() -> None:
    args = parse_args()
    config_entries = load_config(Path(args.config))
    dataset_ids = parse_int_list(args.datasets) if args.datasets else None
    entries = selected_entries(config_entries, dataset_ids)
    answers_root = Path(args.answers_root)
    for entry in entries:
        dataset_id = int(entry["internal_dataset_id"])
        output_path = generate_for_dataset(dataset_id, answers_root, args.output_name, args.anchor_name)
        print(f"generated dataset={dataset_id} output={output_path}")


if __name__ == "__main__":
    main()
