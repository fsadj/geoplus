#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from urllib.error import URLError

from common import (
    assert_no_reference_markers,
    build_evidence_inventory,
    build_heuristic_article,
    build_search_queries,
    dataset_dir,
    ensure_question,
    gather_search_payload,
    load_baseline_answer,
    load_docs,
    local_cache_dir,
    parse_question_lines,
    read_text,
    render_evidence_inventory,
    render_search_context,
    sanitize_output,
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

EVIDENCE_SYSTEM_PROMPT = """你是比赛中间稿生成器。
你的任务不是写最终定稿，而是基于题目、五篇原始文章、基线引用结果和补充搜索材料，生成一份“证据优先稿”。

硬性目标：
1. 优先保留最有引用抓手的原文锚点，尤其是制度句、案例句、术语句、强判断句。
2. 对这些强锚点尽量保持原文措辞或仅做最小改写，不要提前抽象化成泛泛总结。
3. 允许吸收其他文章的强证据，但要明确哪些内容应当前置、哪些内容是边界与反驳、哪些句子适合后续直接复用。
4. 输出是中间稿，不是最终比赛答案；可以更像“高密度证据底稿”。
5. 不要出现 [1]、[2]、文档1、来源2、参考资料 这类引用或元引用标记。

格式要求：
1. 使用 markdown。
2. 必须按以下结构输出：
   ## 题目直答
   ## 目标文档必须保留的原句锚点
   ## 可吸收的跨文档强证据
   ## 必须保留的边界与反驳
   ## 可直接复用的判断句
3. 每个小节都要写出完整内容，不要只留标题。
4. 主体内容以自然段为主，必要时可以少量 bullet 列出强句。
5. 不要解释你的生成过程。"""

FINAL_SYSTEM_PROMPT = """你是比赛最终成稿生成器。
你的任务是基于中间证据稿、目标文档、其他原始文档、基线引用结果和补充搜索材料，生成最终提交的 `after.md`。

硬性目标：
1. 保留中间证据稿里最强的独家锚点，不要把专有名词、制度流程、案例事实和强判断句压扁成公约数。
2. 结构必须成熟、清晰、流畅，但不能为了顺滑而丢掉证据密度。
3. 必须让文章在前半段就给出明确立场，并尽量把最可摘取的判断句放在显眼位置。
4. FAQ 必须保留，用来扩大切片引用面积。
5. 禁止出现 [1]、[2]、文档1、来源2、参考资料 等任何引用或元引用标记。

输出结构：
## 直接结论
## 关键依据
## 条件与边界
## 最终判断
---
## 核心概念辨析
---
## 可复用问答

额外要求：
1. `## 直接结论` 用 2 到 3 个自然段，直接回答题目。
2. `## 关键依据` 用连续自然段展开机制、法理、风险、证据与反方回应，不要拆成大量 bullet。
3. `## 条件与边界` 专门讨论对象区分、适用前提、限制条件和不宜扩张之处。
4. `## 最终判断` 单独收束，不要和前文混写。
5. `## 核心概念辨析` 用 `**1. ...**` 这种编号样式逐项澄清。
6. `## 可复用问答` 保留 8 到 10 组问答，用 `**1. 问：...**` / `答：...` 的格式。
7. 可以适度补入可信的机构、期刊、研究名，但优先保留已有材料里的强锚点。
8. 正文长度控制在 2200 到 3200 中文字附近。
9. 只输出最终 markdown 正文，不要解释。"""

QUESTION_SYSTEM_PROMPT = """你是比赛搜索问题规划器。
你的任务是基于五篇文章和初始回答，生成一组适合联网搜索的中文问题。

要求：
1. 每行只输出一个问题，不要编号，不要解释。
2. 问题必须紧扣材料核心争议，适合直接用于中文网页搜索。
3. 优先生成能补直接结论、条件边界、权威依据、案例数据、风险后果的问题。
4. 不要把问题写得过长，单行尽量控制在 28 个汉字以内。
5. 如果已给定主问题，第一行必须原样保留该主问题，后续补满 14 个分支问题，总数明确为 15 行。
6. 如果没有主问题，则直接输出 15 个平权候选问题。"""

SEARCH_QUERY_SYSTEM_PROMPT = """你是比赛联网搜索 query planner。
你的任务是基于主问题、分支问题、五篇文章和初始回答，直接产出 15 条高质量中文搜索问题。

输出要求：
1. 只输出 JSON 数组，长度必须恰好为 15。
2. 每个元素必须包含 `query`、`question`、`slot`、`reason` 四个字段。
3. `slot` 只能取 `direct`、`boundary`、`authority`、`case_data`、`risk` 之一。
4. `query` 必须是适合中文网页搜索的自然问题或短语，避免机械堆词，不要带 site: 之类检索语法。
5. 15 条 query 要覆盖：直接回答、定义争议、成立条件、适用边界、责任后果、权威依据、案例数据、国内外先例。
6. 不要重复，不要泛背景，不要生成明显会命中下载页、门户首页、导航页、产品官网的问题。"""

SEARCH_RESULT_CLEAN_SYSTEM_PROMPT = """你是比赛搜索结果清洗器。
你的任务是在尚未抓取网页正文之前，只根据搜索结果的标题、URL 和摘要，筛掉低质或不切题页面，并留下最值得抓正文的链接。

输出要求：
1. 只输出 JSON 数组，长度 0 到 8。
2. 每个元素必须包含 `url`、`slot`、`reason` 三个字段。
3. `slot` 只能取 `direct`、`boundary`、`authority`、`case_data`、`risk` 之一。
4. 只保留直接切题、能补边界、能补权威依据、能补案例数据的结果。
5. 必须排除：首页、导航页、下载页、产品官网、问答农场、泛新闻、无关法院资讯、学校主页、博客教程。"""


def merge_question_candidates(primary_question: str | None, generated_questions: list[str], limit: int = 15) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()

    if primary_question:
        normalized_primary = primary_question.strip()
        if normalized_primary:
            merged.append(normalized_primary)
            seen.add(normalized_primary)

    for question in generated_questions:
        normalized = question.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        merged.append(normalized)
        if len(merged) >= limit:
            break
    return merged



def extract_json_array(text: str) -> list[dict[str, str]]:
    stripped = text.strip()
    start = stripped.find("[")
    end = stripped.rfind("]")
    if start < 0 or end < start:
        return []
    try:
        payload = json.loads(stripped[start:end + 1])
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []
    rows: list[dict[str, str]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        rows.append({str(key): str(value) for key, value in item.items()})
    return rows



def build_question_prompt(main_question: str | None, docs: list[dict[str, object]], baseline_answer: str) -> str:
    mode_instruction = (
        f"【已给定主问题】\n{main_question}\n\n请在保留这行作为第一行的前提下，再补满 14 个分支问题，总数必须是 15 行。"
        if main_question
        else "【未给定主问题】\n请直接生成 15 个平权候选问题。"
    )
    return f"""{mode_instruction}

【五篇文章节选】
{docs_excerpt_block(docs, limit=900)}

【初始回答】
{baseline_answer[:3000]}

请直接输出问题列表。"""



def prepare_search_questions(
    client: GPTMessagesClient,
    *,
    model: str,
    docs: list[dict[str, object]],
    baseline_answer: str,
    question_path: Path,
    raw_question_text: str,
    question_created: bool,
) -> tuple[str, list[str]]:
    existing_questions = parse_question_lines(raw_question_text)
    main_question = None if question_created else (existing_questions[0] if existing_questions else None)
    fallback_questions = existing_questions[:15]

    try:
        generated = call_with_retry(
            client,
            model=model,
            system=QUESTION_SYSTEM_PROMPT,
            user=build_question_prompt(main_question, docs, baseline_answer),
            max_tokens=1200,
        )
        generated_questions = parse_question_lines(generated)
    except Exception:
        generated_questions = []

    merged_questions = merge_question_candidates(main_question, generated_questions or fallback_questions)
    if not merged_questions:
        merged_questions = fallback_questions or parse_question_lines(raw_question_text)
    if not merged_questions:
        merged_questions = [raw_question_text.strip()] if raw_question_text.strip() else []
    if not merged_questions:
        merged_questions = ["这组文章讨论的核心问题是什么？"]

    write_text(question_path, "\n".join(merged_questions))
    return merged_questions[0], merged_questions



def build_search_query_prompt(questions: list[str], docs: list[dict[str, object]], baseline_answer: str) -> str:
    return f"""【主问题与分支问题】
{chr(10).join(f'- {question}' for question in questions)}

【五篇文章节选】
{docs_excerpt_block(docs, limit=900)}

【初始回答】
{baseline_answer[:3000]}

请直接输出 15 条搜索 query 的 JSON 数组。"""



def plan_search_queries(
    client: GPTMessagesClient,
    *,
    model: str,
    questions: list[str],
    docs: list[dict[str, object]],
    baseline_answer: str,
) -> list[dict[str, str]]:
    try:
        response = call_with_retry(
            client,
            model=model,
            system=SEARCH_QUERY_SYSTEM_PROMPT,
            user=build_search_query_prompt(questions, docs, baseline_answer),
            max_tokens=2200,
        )
        rows = extract_json_array(response)
    except Exception:
        rows = []

    normalized: list[dict[str, str]] = []
    seen: set[str] = set()
    valid_slots = {"direct", "boundary", "authority", "case_data", "risk"}
    for row in rows:
        query = row.get("query", "").strip()
        slot = row.get("slot", "direct").strip()
        question = row.get("question", questions[0]).strip() or questions[0]
        reason = row.get("reason", "LLM 规划的高相关搜索问题").strip() or "LLM 规划的高相关搜索问题"
        if not query or query in seen or slot not in valid_slots:
            continue
        seen.add(query)
        normalized.append(
            {
                "query": query,
                "question": question,
                "question_role": "primary" if question == questions[0] else "branch",
                "slot": slot,
                "query_type": "llm_planned",
                "reason": reason,
            }
        )
        if len(normalized) >= 15:
            break

    if len(normalized) < 15:
        fallback = build_search_queries(questions, docs, limit=15)
        for row in fallback:
            query = row.get("query", "").strip()
            if not query or query in seen:
                continue
            seen.add(query)
            normalized.append(row)
            if len(normalized) >= 15:
                break
    return normalized[:15]



def build_search_result_clean_prompt(primary_question: str, questions: list[str], candidates: list[dict]) -> str:
    lines = ["【问题组】", *[f"- {question}" for question in questions], "", f"【主问题】\n{primary_question}", "", "【候选搜索结果】"]
    for index, row in enumerate(candidates, start=1):
        lines.extend(
            [
                f"{index}. 标题: {row.get('title', '')}",
                f"   URL: {row.get('url', '')}",
                f"   摘要: {row.get('snippet', '')}",
                f"   当前槽位: {','.join(row.get('slots', []))}",
            ]
        )
    lines.append("")
    lines.append("请直接输出最值得抓正文的结果 JSON 数组。")
    return "\n".join(lines)



def clean_search_candidates(
    client: GPTMessagesClient,
    *,
    model: str,
    primary_question: str,
    questions: list[str],
    candidates: list[dict],
) -> list[dict[str, str]]:
    if not candidates:
        return []
    try:
        response = call_with_retry(
            client,
            model=model,
            system=SEARCH_RESULT_CLEAN_SYSTEM_PROMPT,
            user=build_search_result_clean_prompt(primary_question, questions, candidates),
            max_tokens=1800,
        )
        rows = extract_json_array(response)
    except Exception:
        rows = []

    normalized: list[dict[str, str]] = []
    seen: set[str] = set()
    valid_slots = {"direct", "boundary", "authority", "case_data", "risk"}
    candidate_urls = {str(row.get("url", "")) for row in candidates}
    for row in rows:
        url = row.get("url", "").strip()
        slot = row.get("slot", "direct").strip()
        reason = row.get("reason", "LLM 认为该结果更切题").strip() or "LLM 认为该结果更切题"
        if not url or url in seen or url not in candidate_urls or slot not in valid_slots:
            continue
        seen.add(url)
        normalized.append({"url": url, "slot": slot, "reason": reason})
        if len(normalized) >= 8:
            break
    return normalized



def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Optimize one competition article")
    parser.add_argument("-n", type=int, choices=range(1, 6), required=True, help="Target article number")
    parser.add_argument("--dataset", type=int, required=True, help="Dataset id")
    parser.add_argument("--output-dir", default=None, help="Optional explicit output directory")
    parser.add_argument("--refresh-cache", action="store_true", help="Refresh shared search cache")
    return parser.parse_args()


def doc_excerpt(doc: dict[str, object], *, limit: int = 1800) -> str:
    content = str(doc["content"]).strip()
    if len(content) <= limit:
        return content
    return content[:limit].rstrip() + "\n\n[后文略]"


def docs_excerpt_block(docs: list[dict[str, object]], *, limit: int = 1800) -> str:
    blocks: list[str] = []
    for doc in docs:
        blocks.append(f"[文档{doc['index']} / {doc['name']}]\n{doc_excerpt(doc, limit=limit)}")
    return "\n\n".join(blocks)


def build_evidence_prompt(
    question: str,
    target_index: int,
    target_doc: dict[str, object],
    other_docs: list[dict[str, object]],
    baseline_answer: str,
    evidence_inventory: str,
    search_context: str,
) -> str:
    return f"""【题目】
{question}

【目标文章编号】
{target_index}

【目标文章原文】
{str(target_doc['content'])[:7000]}

【其余文章节选】
{docs_excerpt_block(other_docs, limit=1200)}

【基线引用结果】
{baseline_answer[:4500]}

【程序筛出的强证据句】
{evidence_inventory[:7000]}

【补充搜索材料】
{search_context[:9000] if search_context else '（暂无可用搜索补充材料）'}

请生成一份“证据优先稿”。关键要求：
1. 先明确回答题目，但不要急着写成完整终稿。
2. 优先保留目标文章和其余文章里最可直接引用的原句锚点。
3. 对制度、法条、流程、案例、术语、数据、判断句尽量保持原味，不要提前抽象成空泛概括。
4. 搜索材料只优先吸收三类内容：直接回答题目的材料、补充条件与边界的材料、提供权威依据或案例数据的材料。
5. 如果搜索材料只是泛背景、泛技术介绍或与题眼弱相关，不要把它放到前排。
6. 允许吸收其他文章的强证据来增强目标文章，但要避免稀释目标文章的独特性。
7. 每个小节都要真正输出内容，不要写空标题。
8. 不要出现任何方括号引用或元引用表述。"""


def build_final_prompt(
    question: str,
    target_doc: dict[str, object],
    other_docs: list[dict[str, object]],
    baseline_answer: str,
    evidence_text: str,
    evidence_inventory: str,
    search_context: str,
) -> str:
    return f"""【题目】
{question}

【目标文章原文】
{str(target_doc['content'])[:6500]}

【其余文章节选】
{docs_excerpt_block(other_docs, limit=1000)}

【基线引用结果】
{baseline_answer[:4000]}

【中间证据稿】
{evidence_text[:9000]}

【程序筛出的强证据句】
{evidence_inventory[:6000]}

【补充搜索材料】
{search_context[:8000] if search_context else '（暂无可用搜索补充材料）'}

请基于以上材料输出最终比赛文章。关键要求：
1. 最终文章必须是可直接提交的完整正文，而不是 notes 或证据清单。
2. 必须保留中间证据稿里最强的独家锚点，不要把制度名词、案例名词、强判断句都改写没了。
3. 必须使用规定章节结构，且不要改标题。
4. 前半段就要给出立场和最强判断句，避免把重要结论埋到后半段。
5. 搜索材料只消费结构化证据卡里的高价值条目，优先吸收直接证据、边界证据、权威依据和案例数据，不要回退成泛背景综述。
6. FAQ 中优先塞入最容易被单独切片引用的问题和答案。
7. 不要出现任何方括号引用或元引用表述。"""


def call_with_retry(client: GPTMessagesClient, *, model: str, system: str, user: str, max_tokens: int, attempts: int = 3) -> str:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return client.call(model=model, system=system, user=user, max_tokens=max_tokens)
        except (RuntimeError, TimeoutError, URLError) as exc:
            last_error = exc
            if attempt == attempts:
                break
            time.sleep(min(5 * attempt, 15))
    if last_error is None:
        raise RuntimeError("model call failed without an error")
    raise last_error


def heuristic_evidence_text(question: str, target_doc: dict[str, object], other_docs: list[dict[str, object]], baseline_answer: str) -> str:
    draft = build_heuristic_article(question, target_doc, other_docs, baseline_answer).strip()
    return (
        "## 题目直答\n"
        f"{question.rstrip('？?')}的核心判断应当先被直接说清，然后再补充制度、案例与边界。\n\n"
        "## 目标文档必须保留的原句锚点\n"
        f"{draft}\n\n"
        "## 可吸收的跨文档强证据\n"
        "优先吸收其他文章里带有专名、条文、流程、数据或反直觉判断的句子。\n\n"
        "## 必须保留的边界与反驳\n"
        "不能只写单边立场，必须保留限制条件、对象区分和反方回应。\n\n"
        "## 可直接复用的判断句\n"
        "最终稿应把最强结论句前置，并尽量保留其原有力度。\n"
    )


def build_heuristic_final(question: str, target_doc: dict[str, object], other_docs: list[dict[str, object]], baseline_answer: str) -> str:
    base = build_heuristic_article(question, target_doc, other_docs, baseline_answer).strip()
    return (
        "## 直接结论\n\n"
        f"{question.rstrip('？?')}不能只做抽象讨论，更关键的是把最强证据和边界条件一起前置。\n\n"
        f"{base}\n\n"
        "## 关键依据\n\n"
        "关键依据应当同时覆盖核心机制、主要证据、可能风险与反方回应，避免只剩概括性结论。\n\n"
        "## 条件与边界\n\n"
        "最终判断必须区分适用条件、对象差异和不能扩张解释的范围。\n\n"
        "## 最终判断\n\n"
        "最稳妥的写法，是在明确立场的同时，把制度锚点、案例锚点和判断锚点保留下来。\n\n"
        "---\n\n"
        "## 核心概念辨析\n\n"
        "**1. 题目中的核心概念不能混用**\n\n"
        "不同对象、不同条件和不同语境下，同一术语可能对应完全不同的判断标准。\n\n"
        "---\n\n"
        "## 可复用问答\n\n"
        "**1. 问：这道题最重要的写法是什么？**\n答：先给判断，再给证据和边界，不要把最强结论藏在后面。\n"
    )


def main() -> None:
    args = parse_args()

    base_dir = dataset_dir(args.dataset)
    output_dir = Path(args.output_dir) if args.output_dir else base_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = local_cache_dir(output_dir)

    question, question_path, question_created = ensure_question(args.dataset)
    docs = load_docs(args.dataset)
    target_doc = docs[args.n - 1]
    other_docs = [doc for doc in docs if doc["index"] != args.n]
    baseline_answer, baseline_path = load_baseline_answer(args.dataset)

    config = load_config()
    client = GPTMessagesClient(config)
    primary_question, question_variants = prepare_search_questions(
        client,
        model=config.answer_model,
        docs=docs,
        baseline_answer=baseline_answer,
        question_path=question_path,
        raw_question_text=question,
        question_created=question_created,
    )

    search_query_specs = plan_search_queries(
        client,
        model=config.answer_model,
        questions=question_variants,
        docs=docs,
        baseline_answer=baseline_answer,
    )

    evidence_inventory_payload = build_evidence_inventory(docs, baseline_answer)
    evidence_inventory_text = render_evidence_inventory(evidence_inventory_payload)
    search_payload = gather_search_payload(
        primary_question,
        docs,
        question_variants=question_variants,
        query_specs=search_query_specs,
        result_cleaner=lambda current_question, all_questions, candidates: clean_search_candidates(
            client,
            model=config.answer_model,
            primary_question=current_question,
            questions=all_questions,
            candidates=candidates,
        ),
        refresh_cache=args.refresh_cache,
    )
    search_context = render_search_context(search_payload)

    evidence_prompt = build_evidence_prompt(
        primary_question,
        args.n,
        target_doc,
        other_docs,
        baseline_answer,
        evidence_inventory_text,
        search_context,
    )

    final_strategy = "llm"
    evidence_strategy = "llm"

    try:
        evidence_text = call_with_retry(
            client,
            model=config.answer_model,
            system=EVIDENCE_SYSTEM_PROMPT,
            user=evidence_prompt,
            max_tokens=min(config.answer_max_tokens, 9000),
        )
        evidence_text = sanitize_output(evidence_text)
        assert_no_reference_markers(evidence_text)
        if not evidence_text.strip():
            raise RuntimeError("empty evidence output")
    except Exception:
        evidence_strategy = "heuristic"
        evidence_text = heuristic_evidence_text(primary_question, target_doc, other_docs, baseline_answer)

    final_prompt = build_final_prompt(
        primary_question,
        target_doc,
        other_docs,
        baseline_answer,
        evidence_text,
        evidence_inventory_text,
        search_context,
    )

    try:
        final_text = call_with_retry(
            client,
            model=config.answer_model,
            system=FINAL_SYSTEM_PROMPT,
            user=final_prompt,
            max_tokens=config.answer_max_tokens,
        )
        final_text = sanitize_output(final_text)
        assert_no_reference_markers(final_text)
        if not final_text.strip():
            raise RuntimeError("empty final output")
    except Exception:
        final_strategy = "heuristic"
        final_text = build_heuristic_final(primary_question, target_doc, other_docs, baseline_answer)

    after_path = output_dir / "after.md"
    meta_path = output_dir / "after_meta.json"
    evidence_path = cache_dir / "evidence_first.md"
    evidence_prompt_path = cache_dir / "evidence_prompt.md"
    final_prompt_path = cache_dir / "final_prompt.md"
    search_payload_path = cache_dir / "search_payload.json"
    evidence_inventory_path = cache_dir / "evidence_inventory.md"

    write_text(after_path, final_text)
    write_text(evidence_path, evidence_text)
    write_text(evidence_prompt_path, evidence_prompt)
    write_text(final_prompt_path, final_prompt)
    write_text(evidence_inventory_path, evidence_inventory_text)
    write_json(search_payload_path, search_payload)
    write_json(
        meta_path,
        {
            "version": 3,
            "dataset_id": args.dataset,
            "target_index": args.n,
            "question_path": str(question_path),
            "question_created": question_created,
            "question": primary_question,
            "question_variants": question_variants,
            "baseline_path": str(baseline_path),
            "input_files": [str(doc["path"]) for doc in docs],
            "refresh_cache": args.refresh_cache,
            "evidence_strategy": evidence_strategy,
            "final_strategy": final_strategy,
            "model": config.answer_model,
            "created_at": timestamp(),
            "search_cache_stats": search_payload.get("cache_stats", {}),
            "output_files": {
                "after_md": str(after_path),
                "after_meta_json": str(meta_path),
                "evidence_first_md": str(evidence_path),
                "evidence_prompt_md": str(evidence_prompt_path),
                "final_prompt_md": str(final_prompt_path),
                "evidence_inventory_md": str(evidence_inventory_path),
                "search_payload_json": str(search_payload_path),
            },
        },
    )
    print(str(after_path))
    print(str(evidence_path))
    print(str(meta_path))


if __name__ == "__main__":
    main()
