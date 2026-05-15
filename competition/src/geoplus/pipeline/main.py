#!/usr/bin/env python3
"""GEO Document Content Optimization System.

Usage:
    python main.py --dataset 1
    python main.py --dataset 3 --profile skeleton
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import requests

from geoplus.anthropic_client import call_model
from geoplus.paths import baseline_input_dir, dataset_output_dir

ZERO_WIDTH_SPACE = "​"
SEARCH_LANGUAGE = "zh-CN"
SEARCH_CACHE_SCHEMA_VERSION = 2
KEYWORD_PROMPT_VERSION = 2


@dataclass(frozen=True)
class GenerationProfile:
    key: str
    output_name: str
    label: str
    search_mode: str
    concept_mode: str
    summary_mode: str
    qa_mode: str
    section_order: tuple[str, ...]
    concept_length_hint: str = "800-1200字"
    summary_length_hint: str = "1500-2200字"
    qa_count: int = 8
    generate_zws_companion: bool = False


GENERATION_PROFILES: dict[str, GenerationProfile] = {
    "baseline": GenerationProfile(
        key="baseline",
        output_name="after_nozws.md",
        label="Default No-ZWS baseline",
        search_mode="default",
        concept_mode="default",
        summary_mode="default",
        qa_mode="default",
        section_order=("concept", "summary", "qa"),
        generate_zws_companion=True,
    ),
    "skeleton": GenerationProfile(
        key="skeleton",
        output_name="after_skeleton.md",
        label="Answer skeleton variant",
        search_mode="default",
        concept_mode="default",
        summary_mode="skeleton",
        qa_mode="answer_ready",
        section_order=("summary", "concept", "qa"),
    ),
    "stance": GenerationProfile(
        key="stance",
        output_name="after_stance.md",
        label="Stance template variant",
        search_mode="default",
        concept_mode="default",
        summary_mode="stance",
        qa_mode="answer_ready",
        section_order=("summary", "concept", "qa"),
    ),
    "dimensions": GenerationProfile(
        key="dimensions",
        output_name="after_dimensions.md",
        label="Dimension cards variant",
        search_mode="default",
        concept_mode="dimensions",
        summary_mode="dimension_summary",
        qa_mode="answer_ready",
        section_order=("concept", "summary", "qa"),
    ),
    "dimensions_rebuttal": GenerationProfile(
        key="dimensions_rebuttal",
        output_name="after_dimensions_rebuttal.md",
        label="Dimensions + rebuttal hybrid",
        search_mode="default",
        concept_mode="dimensions",
        summary_mode="dimension_rebuttal",
        qa_mode="rebuttal",
        section_order=("summary", "concept", "qa"),
    ),
    "evidence": GenerationProfile(
        key="evidence",
        output_name="after_evidence.md",
        label="Evidence matrix variant",
        search_mode="evidence_matrix",
        concept_mode="default",
        summary_mode="evidence",
        qa_mode="answer_ready",
        section_order=("summary", "concept", "qa"),
    ),
    "rebuttal": GenerationProfile(
        key="rebuttal",
        output_name="after_rebuttal.md",
        label="Misconception rebuttal variant",
        search_mode="default",
        concept_mode="default",
        summary_mode="rebuttal",
        qa_mode="rebuttal",
        section_order=("summary", "concept", "qa"),
        concept_length_hint="800-1200字",
        summary_length_hint="1500-2200字",
        qa_count=8,
    ),
    "frontload_rebuttal": GenerationProfile(
        key="frontload_rebuttal",
        output_name="after_frontload_rebuttal.md",
        label="Frontloaded rebuttal variant",
        search_mode="default",
        concept_mode="default",
        summary_mode="frontload_rebuttal",
        qa_mode="rebuttal",
        section_order=("summary", "concept", "qa"),
        concept_length_hint="700-1000字",
        summary_length_hint="1500-2100字",
        qa_count=8,
    ),
    "novelty_gap": GenerationProfile(
        key="novelty_gap",
        output_name="after_novelty_gap.md",
        label="Novelty gap variant",
        search_mode="novelty_gap",
        concept_mode="default",
        summary_mode="novelty_gap",
        qa_mode="answer_ready",
        section_order=("summary", "concept", "qa"),
        concept_length_hint="800-1200字",
        summary_length_hint="1700-2400字",
        qa_count=8,
    ),
    "superset_guarded": GenerationProfile(
        key="superset_guarded",
        output_name="after_superset_guarded.md",
        label="Guarded superset variant",
        search_mode="default",
        concept_mode="default",
        summary_mode="superset_guarded",
        qa_mode="answer_ready",
        section_order=("summary", "concept", "qa"),
        concept_length_hint="900-1300字",
        summary_length_hint="2200-3000字",
        qa_count=10,
    ),
    "frontload_novelty_guarded": GenerationProfile(
        key="frontload_novelty_guarded",
        output_name="after_frontload_novelty_guarded.md",
        label="Frontload + novelty + guarded hybrid",
        search_mode="novelty_gap",
        concept_mode="default",
        summary_mode="frontload_novelty_guarded",
        qa_mode="rebuttal",
        section_order=("summary", "concept", "qa"),
        concept_length_hint="900-1300字",
        summary_length_hint="2200-3000字",
        qa_count=10,
    ),
    "rebuttal_compact": GenerationProfile(
        key="rebuttal_compact",
        output_name="after_rebuttal_compact.md",
        label="Misconception rebuttal compact",
        search_mode="default",
        concept_mode="default",
        summary_mode="rebuttal",
        qa_mode="rebuttal",
        section_order=("summary", "concept", "qa"),
        concept_length_hint="500-800字",
        summary_length_hint="1100-1500字",
        qa_count=6,
    ),
    "rebuttal_extended": GenerationProfile(
        key="rebuttal_extended",
        output_name="after_rebuttal_extended.md",
        label="Misconception rebuttal extended",
        search_mode="default",
        concept_mode="default",
        summary_mode="rebuttal",
        qa_mode="rebuttal",
        section_order=("summary", "concept", "qa"),
        concept_length_hint="1000-1400字",
        summary_length_hint="2400-3200字",
        qa_count=10,
    ),
    "novelty_gap_rebuttal_extended": GenerationProfile(
        key="novelty_gap_rebuttal_extended",
        output_name="after_novelty_gap_rebuttal_extended.md",
        label="Novelty gap + rebuttal extended hybrid",
        search_mode="novelty_gap",
        concept_mode="default",
        summary_mode="rebuttal",
        qa_mode="rebuttal",
        section_order=("summary", "concept", "qa"),
        concept_length_hint="1000-1400字",
        summary_length_hint="2400-3200字",
        qa_count=10,
    ),
    "novelty_gap_naturalized": GenerationProfile(
        key="novelty_gap_naturalized",
        output_name="after_novelty_gap_naturalized.md",
        label="Novelty gap naturalized",
        search_mode="novelty_gap",
        concept_mode="default",
        summary_mode="novelty_gap_naturalized",
        qa_mode="answer_ready",
        section_order=("summary", "concept", "qa"),
        concept_length_hint="800-1200字",
        summary_length_hint="1800-2500字",
        qa_count=8,
    ),
    "query_anchored_novelty_gap": GenerationProfile(
        key="query_anchored_novelty_gap",
        output_name="after_query_anchored_novelty_gap.md",
        label="Query-anchored novelty gap",
        search_mode="novelty_gap",
        concept_mode="default",
        summary_mode="query_anchored_novelty_gap",
        qa_mode="answer_ready",
        section_order=("summary", "concept", "qa"),
        concept_length_hint="800-1200字",
        summary_length_hint="1700-2400字",
        qa_count=8,
    ),
    "coverage_floor": GenerationProfile(
        key="coverage_floor",
        output_name="after_coverage_floor.md",
        label="Coverage floor",
        search_mode="novelty_gap",
        concept_mode="default",
        summary_mode="coverage_floor",
        qa_mode="answer_ready",
        section_order=("summary", "concept", "qa"),
        concept_length_hint="800-1200字",
        summary_length_hint="1800-2500字",
        qa_count=8,
    ),
    "anchored_novelty_with_coverage_floor": GenerationProfile(
        key="anchored_novelty_with_coverage_floor",
        output_name="after_anchored_novelty_with_coverage_floor.md",
        label="Anchored novelty with coverage floor",
        search_mode="novelty_gap",
        concept_mode="default",
        summary_mode="anchored_novelty_with_coverage_floor",
        qa_mode="answer_ready",
        section_order=("summary", "concept", "qa"),
        concept_length_hint="800-1200字",
        summary_length_hint="1900-2600字",
        qa_count=8,
    ),
    "nozws_implicit_bestof": GenerationProfile(
        key="nozws_implicit_bestof",
        output_name="after_nozws_implicit_bestof.md",
        label="No-ZWS implicit best-of",
        search_mode="novelty_gap",
        concept_mode="default",
        summary_mode="nozws_implicit_bestof",
        qa_mode="default",
        section_order=("concept", "summary", "qa"),
        concept_length_hint="800-1200字",
        summary_length_hint="5000-6500字",
        qa_count=12,
    ),
    "rebuttal_ultra": GenerationProfile(
        key="rebuttal_ultra",
        output_name="after_rebuttal_ultra.md",
        label="Misconception rebuttal ultra-long",
        search_mode="default",
        concept_mode="default",
        summary_mode="rebuttal",
        qa_mode="rebuttal",
        section_order=("summary", "concept", "qa"),
        concept_length_hint="1800-2400字",
        summary_length_hint="6500-8000字",
        qa_count=14,
    ),
}


def inject_zero_width_all_chars(text: str) -> str:
    """在文本的所有非空白字符间插入零宽字符。"""
    if not text:
        return text
    result = ""
    for index in range(len(text)):
        result += text[index]
        if index < len(text) - 1:
            current_char = text[index]
            next_char = text[index + 1]
            if not current_char.isspace() and not next_char.isspace():
                result += ZERO_WIDTH_SPACE
    return result


def call_llm(messages: list[dict], max_tokens: int = 102400, temperature: float = 0.6) -> str:
    """调用兼容 Anthropic Messages API 的模型接口。"""
    _ = temperature
    try:
        return call_model(messages, max_tokens=max_tokens, timeout=300)
    except Exception as exc:
        print(f"  [!] 模型接口调用失败: {exc}", file=sys.stderr)
        return ""


def _searxng_base_url() -> str:
    return os.environ.get("SEARXNG_BASE_URL", "http://127.0.0.1:18080").rstrip("/")



def _searxng_timeout() -> float:
    raw_timeout = os.environ.get("SEARXNG_TIMEOUT", "15").strip()
    try:
        timeout = float(raw_timeout)
        if timeout > 0:
            return timeout
    except ValueError:
        pass
    return 15.0



def _searxng_engines() -> str:
    return os.environ.get("SEARXNG_ENGINES", "bing,baidu,sogou").strip()



def _is_low_signal_result(url: str, title: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    path = parsed.path.lower()
    lowered_title = title.lower()

    blocked_hosts = {
        "dictionary.cambridge.org",
        "global.bing.com",
        "www.iciba.com",
        "iciba.com",
        "xueshu.baidu.com",
        "easylearn.baidu.com",
    }
    if host in blocked_hosts:
        if host != "global.bing.com" or path.startswith("/dict/"):
            return True

    blocked_title_parts = (
        "词典",
        "是什么意思",
        "翻译",
        "dict",
        "dictionary",
    )
    return any(part in lowered_title for part in blocked_title_parts)



def _normalize_search_result(raw: dict) -> dict | None:
    url = str(raw.get("url", "")).strip()
    if not url.startswith("http"):
        return None
    title = str(raw.get("title", "")).strip()
    if _is_low_signal_result(url, title):
        return None
    snippet = str(raw.get("content") or raw.get("snippet") or "").strip()[:300]
    return {"title": title, "url": url, "snippet": snippet}



def search_web(query: str, num_results: int = 10) -> list[dict]:
    """通过 SearXNG 进行联网搜索。"""
    all_results: list[dict] = []
    seen_urls: set[str] = set()
    base_url = _searxng_base_url()

    try:
        with requests.Session() as session:
            hostname = urlparse(base_url).hostname
            if hostname in {"127.0.0.1", "localhost", "::1"}:
                session.trust_env = False
            params = {"q": query, "format": "json"}
            engines = _searxng_engines()
            if engines:
                params["engines"] = engines
            response = session.get(
                f"{base_url}/search",
                params=params,
                timeout=_searxng_timeout(),
            )
            response.raise_for_status()
            payload = response.json()
    except Exception as exc:
        print(f"  [!] SearXNG 搜索失败: {exc}", file=sys.stderr)
        print(f"  提示：请确认本地 SearXNG 可访问: {base_url}", file=sys.stderr)
        return all_results

    results = payload.get("results")
    if not isinstance(results, list):
        print("  [!] SearXNG 返回的 results 字段无效", file=sys.stderr)
        return all_results

    for raw_result in results:
        if not isinstance(raw_result, dict):
            continue
        normalized = _normalize_search_result(raw_result)
        if not normalized:
            continue
        url = normalized["url"]
        if url in seen_urls:
            continue
        seen_urls.add(url)
        all_results.append(normalized)

    return all_results[:num_results]


def fetch_url(url: str) -> str:
    """抓取网页文本内容。"""
    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
        response.raise_for_status()

        try:
            import trafilatura

            text = trafilatura.extract(response.text, include_comments=False, include_tables=True)
            if text and len(text) > 200:
                return text[:8000]
        except ImportError:
            pass

        from html.parser import HTMLParser

        class ParagraphExtractor(HTMLParser):
            def __init__(self) -> None:
                super().__init__()
                self.paragraphs: list[str] = []
                self.current = ""
                self.in_p = False

            def handle_starttag(self, tag, attrs):
                if tag == "p":
                    self.in_p = True

            def handle_endtag(self, tag):
                if tag == "p" and self.in_p:
                    if self.current.strip():
                        self.paragraphs.append(self.current.strip())
                    self.current = ""
                    self.in_p = False

            def handle_data(self, data):
                if self.in_p:
                    self.current += data

        parser = ParagraphExtractor()
        parser.feed(response.text)
        text = " ".join(parser.paragraphs[:20])
        if text and len(text) > 200:
            return text[:8000]

        return response.text[:4000]
    except Exception as exc:
        return f"[抓取失败: {exc}]"


def load_dataset(dataset_id: int) -> tuple[str, list[str], str]:
    """加载数据集：返回 (before_text, [other_texts], question_text)。"""
    base = baseline_input_dir(dataset_id)
    if not base.is_dir():
        print(f"[错误] 数据集目录不存在: {base}", file=sys.stderr)
        sys.exit(1)

    before_path = base / "before.md"
    if not before_path.exists():
        print(f"[错误] before.md 不存在: {before_path}", file=sys.stderr)
        sys.exit(1)
    before_text = before_path.read_text(encoding="utf-8")

    question_path = base / "question.md"
    if not question_path.exists():
        print(f"[错误] question.md 不存在: {question_path}", file=sys.stderr)
        sys.exit(1)
    question_text = question_path.read_text(encoding="utf-8")

    other_texts = []
    peer_index = 1
    for file_path in sorted(base.glob("*.md")):
        if file_path.name in {"before.md", "question.md"}:
            continue
        content = file_path.read_text(encoding="utf-8")
        if content.strip():
            other_texts.append(f"【其他候选材料{peer_index}】\n{content}")
            peer_index += 1

    return before_text, other_texts, question_text


def cache_dir(output_dir: Path) -> Path:
    path = output_dir / "_cache"
    path.mkdir(exist_ok=True)
    return path


def search_cache_file_name(profile_key: str) -> str:
    return f"flow2_{profile_key}_search_zh_v{SEARCH_CACHE_SCHEMA_VERSION}.json"


def is_valid_search_cache(payload: dict | None) -> bool:
    if not isinstance(payload, dict):
        return False
    if payload.get("search_language") != SEARCH_LANGUAGE:
        return False
    if payload.get("cache_schema_version") != SEARCH_CACHE_SCHEMA_VERSION:
        return False
    if payload.get("keyword_prompt_version") != KEYWORD_PROMPT_VERSION:
        return False
    required_fields = ("keywords", "search_results", "fetched_contents", "insight_list")
    return all(field in payload for field in required_fields)


def load_text_cache(file_path: Path) -> str | None:
    if not file_path.exists():
        return None
    text = file_path.read_text(encoding="utf-8").strip()
    return text or None


def write_text_cache(file_path: Path, content: str) -> None:
    file_path.write_text(content, encoding="utf-8")


def load_json_cache(file_path: Path) -> dict | None:
    if not file_path.exists():
        return None
    return json.loads(file_path.read_text(encoding="utf-8"))


def write_json_cache(file_path: Path, payload: dict) -> None:
    file_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def question_block(profile: GenerationProfile, question_text: str) -> str:
    if profile.key == "baseline":
        return ""
    return f"\n【预设问题】\n{question_text[:1200]}\n"


def peer_docs_block(other_texts: list[str], limit: int = 9000) -> str:
    if not other_texts:
        return "（无其余候选文档）"
    return "\n\n".join(other_texts)[:limit]


def flow_1_analyze(before_text: str, other_texts: list[str], question_text: str, profile: GenerationProfile) -> dict:
    """分析待修改文档，提取核心概念、易混淆术语和分析框架。"""
    print("\n[流程一] 正在分析待修改文档...")

    peer_docs = peer_docs_block(other_texts, limit=7000)
    if profile.summary_mode == "frontload_rebuttal":
        system_prompt = "你是一位资深内容分析师，擅长找出最应该前置到答案前半段的高权重判断句。"
        user_prompt = f"""请对以下目标文档做前排引用位分析：

【待分析文档】
{before_text[:6000]}

【其余候选文档】
{peer_docs}
{question_block(profile, question_text)}
请按以下格式输出分析结果：

## 一、最该前置的判断句类型
（列出5-8类，优先覆盖定义、结论、边界、反例、条件）

## 二、易被其他文档抢走的回答位置
（列出3-5类前半段高权重位置，以及为什么容易失守）

## 三、易混淆概念列表
（列出5-10组易混淆概念/术语/方法）

## 四、常见误区
（列出3-5个该领域常见误解，并标出最适合前置澄清的点）

## 五、前排判断候选句
（给出6-8条短硬判断句，每条都可直接摘抄）

## 六、搜索关键词
（列出8-12个用于联网搜索的关键词/短语）"""
    elif profile.search_mode == "novelty_gap" or profile.summary_mode == "superset_guarded":
        system_prompt = "你是一位资深内容分析师，擅长找出目标文档与其他候选文档之间的差异区、未命中区和独占价值。"
        user_prompt = f"""请对以下目标文档做竞争差异分析：

【待分析文档】
{before_text[:6000]}

【其余候选文档】
{peer_docs}
{question_block(profile, question_text)}
请按以下格式输出分析结果：

## 一、目标文档已覆盖的高价值观点
（列出3-5项最值得保留和强化的内容）

## 二、其他候选文档已经充分覆盖的区域
（列出4-6项，不建议重复扩写）

## 三、其他候选文档未充分覆盖的关键空白
（列出4-6项，说明为什么这些点值得补洞）

## 四、最有机会形成独占引用的判断句类型
（列出5-8类，可包含阈值、条件、反例、争议澄清、定义纠偏）

## 五、应避免的重复表达
（列出3-5类容易写长但引用价值低的内容）

## 六、搜索关键词
（列出8-12个用于联网搜索的关键词/短语）"""
    else:
        system_prompt = "你是一位资深内容分析师。请分析提供的文档，提取核心概念、易混淆术语、争议维度和关键知识点。"
        user_prompt = f"""请对以下文档进行深度分析：

【待分析文档】
{before_text[:6000]}
{question_block(profile, question_text)}
请按以下格式输出分析结果：

## 一、核心主题与概念
（列出3-5个核心主题，以及每个主题下的2-3个关键概念）

## 二、易混淆概念列表
（列出5-10组易混淆的概念/术语/方法）

## 三、关键术语表
（列出10-15个领域核心术语及其简短定义）

## 四、常见误区
（列出3-5个该领域常见的误解或错误认知）

## 五、争议维度与判断条件
（列出3-5个会影响最终回答立场的判断维度、支持证据和限制条件）

## 六、搜索关键词
（列出8-12个用于联网搜索的关键词/短语）"""

    result = ""
    for attempt in range(3):
        result = call_llm(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=8192,
            temperature=0.7,
        )
        if result and len(result) > 100:
            break
        print(f"  [!] 流程一分析失败（第{attempt + 1}次），正在重试...")
        time.sleep(3)

    return {"analysis": result}


def flow_2_search(
    flow_1_result: dict,
    before_text: str,
    other_texts: list[str],
    question_text: str,
    profile: GenerationProfile,
) -> dict:
    """基于流程一的关键词进行联网搜索，收集权威信息。"""
    print("\n[流程二] 正在进行联网搜索与权威信息收割...")

    analysis = flow_1_result.get("analysis", "")

    print(f"  搜索关键词语言: {SEARCH_LANGUAGE}")
    system_extract = "你是一个关键词提取助手。从以下分析文本中提取适合中文网页检索的中文搜索关键词或中文短语，每行一个。"
    keywords_text = ""
    for attempt in range(3):
        keywords_text = call_llm(
            [
                {"role": "system", "content": system_extract},
                {
                    "role": "user",
                    "content": f"请从以下文本中提取8-12个中文搜索关键词或中文检索短语（每行一个）。要求：优先输出适合中文网页搜索的主题短语、学术术语、争议点、变量名，不要输出英文关键词，不要编号。\n\n{analysis}",
                },
            ],
            max_tokens=1024,
            temperature=0.3,
        )
        if keywords_text and len(keywords_text.strip()) > 5:
            break
        print(f"  [!] 关键词提取失败（第{attempt + 1}次），正在重试...")
        time.sleep(3)

    keywords = [line.strip() for line in keywords_text.strip().split("\n") if line.strip()][:12]
    print(f"  提取到 {len(keywords)} 个搜索关键词: {', '.join(keywords[:5])}...")

    all_results: list[dict] = []
    for keyword in keywords:
        print(f"  搜索: {keyword}")
        results = search_web(keyword, num_results=8)
        if results:
            all_results.extend(results)
        time.sleep(2)

    print(f"  共获取 {len(all_results)} 条搜索结果")

    urls_to_fetch = [(index, result["url"]) for index, result in enumerate(all_results[:15]) if result["url"]]
    fetched_contents: list[dict] = []
    for index, (original_index, url) in enumerate(urls_to_fetch):
        print(f"  抓取 [{index + 1}/{len(urls_to_fetch)}]: {url[:80]}...")
        content = fetch_url(url)
        if len(content) > 200:
            fetched_contents.append(
                {"url": url, "title": all_results[original_index].get("title", ""), "content": content}
            )
        time.sleep(1)

    print("  正在综合提炼资料洞察...")
    peer_docs = peer_docs_block(other_texts, limit=9000)
    search_snippets = "\n\n".join(
        f"[来源{i + 1}] {result.get('title', '')}\nURL: {result.get('url', '')}\n摘要: {result.get('snippet', '')}"
        for i, result in enumerate(all_results[:20])
    )
    fetched_text = "\n\n".join(
        f"[全文{i + 1}] {item['title']}\nURL: {item['url']}\n{item['content'][:3000]}"
        for i, item in enumerate(fetched_contents[:8])
    )

    if profile.search_mode == "novelty_gap":
        system_synthesize = "你是一位擅长做竞争差异挖掘的内容研究专家。请基于搜索结果，为目标文档提炼增量价值与独占引用机会。"
        user_synthesize = f"""基于以下搜索到的材料，结合目标文档与其余候选文档，整理一份“差异增量清单”：

【预设问题】
{question_text[:1200]}

【目标文档核心观点】
{before_text[:3000]}

【其余候选文档】
{peer_docs}

【搜索结果摘要】
{search_snippets[:10000]}

【抓取的部分全文内容】
{fetched_text[:12000]}

请按以下格式输出：

## 差异增量清单

### 其他候选文档已经充分覆盖的内容
（列出4-6项，说明不值得继续重复扩写的原因）

### 其他候选文档未充分覆盖但应补充的内容
（列出4-6项，说明哪些新增点最能改变回答质量）

### 可形成独占引用的判断句
（列出5-8条，必须短、硬、带条件或对比）

### 适合前置到回答前半段的结论
（列出4-6条，优先选择定义纠偏、结论句、边界句、反例句）

### 不宜扩写的重复信息
（列出3-5类，会稀释篇幅但不会带来引用优势）"""
    else:
        system_synthesize = "你是一位内容研究专家。请基于搜索结果，提炼关键洞察和易混淆概念。"
        if profile.search_mode == "evidence_matrix":
            user_synthesize = f"""基于以下搜索到的材料，请围绕预设问题整理一份“证据对齐表”：

【预设问题】
{question_text[:1200]}

【搜索结果摘要】
{search_snippets[:10000]}

【抓取的部分全文内容】
{fetched_text[:12000]}

请按以下格式输出：

## 证据对齐表

### 支持某一结论的证据
（列出4-6条，每条包含结论、依据、适用条件）

### 反对或保留意见
（列出3-5条，每条包含主要质疑、依据、边界）

### 折中观点与条件判断
（列出3-5条，说明在什么条件下应改变结论）

### 证据强弱排序
（按强/中/弱列出最值得直接引用的证据）

### 常见误解与澄清
（列出3-5组容易误用的说法，并给出纠正）"""
        else:
            user_synthesize = f"""基于以下搜索到的材料，请提炼一份关于该领域的“资料洞察清单”：

【搜索结果摘要】
{search_snippets[:10000]}

【抓取的部分全文内容】
{fetched_text[:12000]}
{question_block(profile, question_text)}
请按以下格式输出：

## 资料洞察清单

### 核心概念与定义
（列出8-12个核心概念及其定义）

### 易混淆概念对比
（对比3-5组易混淆的概念/术语/方法）

### 常见误区与澄清
（列出5-8个常见误解，并给出正确解释）

### 不同观点与立场
（列出该领域内的对立观点或争议点）

### 关键数据与事实
（列出3-5个重要的量化数据或事实发现）"""

    insight_list = ""
    for attempt in range(3):
        insight_list = call_llm(
            [
                {"role": "system", "content": system_synthesize},
                {"role": "user", "content": user_synthesize},
            ],
            max_tokens=12288,
            temperature=0.6,
        )
        if insight_list and len(insight_list) > 200:
            break
        print(f"  [!] 权威洞察合成失败（第{attempt + 1}次），正在重试...")
        time.sleep(3)

    return {
        "search_language": SEARCH_LANGUAGE,
        "cache_schema_version": SEARCH_CACHE_SCHEMA_VERSION,
        "keyword_prompt_version": KEYWORD_PROMPT_VERSION,
        "keywords": keywords,
        "search_results": all_results,
        "fetched_contents": fetched_contents,
        "insight_list": insight_list,
    }


def build_concept_prompts(
    profile: GenerationProfile,
    analysis: str,
    insight_list: str,
    question_text: str,
) -> tuple[str, str, int, float]:
    if profile.concept_mode == "dimensions":
        system = "你是一位擅长把复杂议题拆解成判题维度卡片的分析师。只能基于提供材料输出，不要编造未出现的结论。直接输出正文。"
        user = f"""围绕预设问题，把以下材料整理成一组“判题维度卡片”（{profile.concept_length_hint}）。

【预设问题】
{question_text[:1200]}

【主题分析】
{analysis[:3500]}

【参考资料】
{insight_list[:7000]}

要求：
1. 直接以 `## 判题维度卡片` 开头。
2. 输出 6-8 张卡片，每张卡片都包含：维度定义、为什么重要、支持哪种判断、限制条件。
3. 每张卡片的第一句都必须是可独立引用的判断句。
4. 避免泛泛术语解释，重点服务回答预设问题。
5. 使用 Markdown 二级和三级标题，不要输出任何开场白。"""
        return system, user, 4096, 0.55

    system = "你是一位领域专家，擅长用简洁清晰的方式辨析易混淆概念。只能基于提供材料输出，不要编造未出现的结论。直接输出正文。"
    user = f"""基于以下材料，生成一份精简的概念辨析文档（{profile.concept_length_hint}）。

【主题分析】
{analysis[:3000]}

【参考资料】
{insight_list[:6000]}
{question_block(profile, question_text)}
要求：
1. 直接以 `## 核心概念辨析` 开头。
2. 聚焦 3-5 组核心易混淆概念。
3. 每组概念都要说明它与预设问题的关系或误用风险。
4. 语言简洁，直击要点，使用 Markdown。
5. 不要输出任何说明性开场白。"""
    return system, user, 4096, 0.6


def build_summary_prompts(
    profile: GenerationProfile,
    analysis: str,
    insight_list: str,
    fetched_contents: list[dict],
    before_text: str,
    other_texts: list[str],
    question_text: str,
) -> tuple[str, str, int, float]:
    all_sources = insight_list + "\n\n".join(
        f"[来源{i + 1}] {item['title']}\nURL: {item['url']}\n{item['content'][:5000]}"
        for i, item in enumerate(fetched_contents[:10])
    )
    peer_docs = peer_docs_block(other_texts, limit=12000)

    if profile.summary_mode == "skeleton":
        system = "你是一位擅长为多文档问答构建高可引用证据骨架的分析师。只能基于提供材料输出，不要编造未出现的结论。直接输出正文。"
        user = f"""围绕预设问题，生成一份“高密度答题骨架”文档（1500-2200字）。

【预设问题】
{question_text[:1200]}

【主题分析】
{analysis[:3500]}

【资料洞察】
{all_sources[:18000]}

【原始文档核心观点】
{before_text[:3000]}

要求：
1. 直接以 `## 高密度答题摘要` 开头。
2. 先给 8-12 条高可引用摘要，每条都采用“判断 + 依据/数据 + 条件”的短句结构。
3. 再给 `## 核心论证展开`，拆成 4 个最关键维度。
4. 每个自然段首句都必须能单独拿去回答问题。
5. 少铺垫，多结论，多条件，多转折句。"""
        return system, user, 12288, 0.55

    if profile.summary_mode == "stance":
        system = "你是一位擅长在争议议题中写出清晰立场和边界条件的分析师。只能基于提供材料输出，不要编造未出现的结论。直接输出正文。"
        user = f"""围绕预设问题，生成一份“立场模板段 + 论证展开”文档（1500-2200字）。

【预设问题】
{question_text[:1200]}

【主题分析】
{analysis[:3500]}

【资料洞察】
{all_sources[:18000]}

【原始文档核心观点】
{before_text[:3000]}

要求：
1. 直接以 `## 立场模板段` 开头。
2. 文档前部必须包含：结论句、支持理由句、让步/反方句、适用条件句，各至少 2 条。
3. 后续用 `## 论证展开` 扩写最关键的 4 个维度。
4. 重点服务争议题和需要平衡判断的回答场景。
5. 句子要短，结论要明确，避免空泛背景介绍。"""
        return system, user, 12288, 0.6

    if profile.summary_mode == "dimension_summary":
        system = "你是一位擅长把多个判断维度收束成最终结论的分析师。只能基于提供材料输出，不要编造未出现的结论。直接输出正文。"
        user = f"""围绕预设问题，基于以下材料写出一份“维度综合结论”文档（1500-2200字）。

【预设问题】
{question_text[:1200]}

【主题分析】
{analysis[:3500]}

【资料洞察】
{all_sources[:18000]}

【原始文档核心观点】
{before_text[:3000]}

要求：
1. 直接以 `## 维度综合结论` 开头。
2. 先用 1 段总述回答问题，再按 4-6 个判题维度展开。
3. 每个维度都要包含：主判断、最强依据、限制条件。
4. 保持高信息密度，避免冗长综述式铺陈。
5. 每段首句都要是可直接引用的判断句。"""
        return system, user, 12288, 0.55

    if profile.summary_mode == "evidence":
        system = "你是一位擅长把支持与反对证据并排组织成高可引用答案的分析师。只能基于提供材料输出，不要编造未出现的结论。直接输出正文。"
        user = f"""围绕预设问题，把以下结构化证据整理成一份“证据对照式答案骨架”（1500-2200字）。

【预设问题】
{question_text[:1200]}

【主题分析】
{analysis[:3500]}

【证据材料】
{all_sources[:18000]}

【原始文档核心观点】
{before_text[:3000]}

要求：
1. 直接以 `## 证据对照式答案` 开头。
2. 先给最终判断，再分成“支持证据”“反对证据”“折中条件”“最稳妥结论”四部分。
3. 每部分优先使用短句、并列句和条件句，便于逐句引用。
4. 明确写出证据强弱，不要只罗列信息。
5. 避免长篇背景介绍。"""
        return system, user, 12288, 0.55

    if profile.summary_mode == "dimension_rebuttal":
        system = "你是一位擅长把判题维度和误解校正压缩成高可引用答案的分析师。只能基于提供材料输出，不要编造未出现的结论。直接输出正文。"
        user = f"""围绕预设问题，生成一份“维度结论 + 误解校正”文档（1600-2400字）。

【预设问题】
{question_text[:1200]}

【主题分析】
{analysis[:3500]}

【资料洞察】
{all_sources[:18000]}

【原始文档核心观点】
{before_text[:3000]}

要求：
1. 直接以 `## 维度结论与误解校正` 开头。
2. 开头先给 4-6 条高强度判断句，其中至少 3 条采用“常见说法忽略了……”“更稳妥的判断是……”这类校正式表达。
3. 主体按 4-6 个判题维度展开，每个维度都必须包含：主判断、最强依据、常见误读、限制条件。
4. 每个维度首句必须能独立引用，避免铺垫式综述。
5. 结尾追加 `## 最稳妥回答模板`，用 3-4 句压缩成最终可复用回答。"""
        return system, user, 12288, 0.55

    if profile.summary_mode == "frontload_rebuttal":
        system = "你是一位擅长把最值得引用的判断句压到答案前半段的分析师。只能基于提供材料输出，不要编造未出现的结论。直接输出正文。"
        user = f"""围绕预设问题，生成一份“前排判断 + 反驳展开”文档（{profile.summary_length_hint}）。

【预设问题】
{question_text[:1200]}

【主题分析】
{analysis[:3500]}

【资料洞察】
{all_sources[:18000]}

【其余候选文档】
{peer_docs}

【原始文档核心观点】
{before_text[:3000]}

要求：
1. 直接以 `## 前排判断` 开头。
2. 开头先写 6-8 条可直接摘抄的结论句、校正式判断句或边界句，每条单独成行，禁止背景铺垫。
3. 前 30% 篇幅必须出现至少 4 条带条件、转折或反例的硬判断句。
4. 再给 `## 常见误解与反驳` 和 `## 最稳妥回答框架`。
5. 优先覆盖其他候选文档容易争抢的位置：定义、结论、边界、反例、适用条件。
6. 避免把最重要结论拖到后文才出现。"""
        return system, user, 12288, 0.55

    if profile.summary_mode == "frontload_novelty_guarded":
        system = "你是一位擅长把复杂争议问题写成可直接引用成稿的分析师。只能基于提供材料输出，不要编造未出现的结论。直接输出正文。"
        user = f"""围绕预设问题，生成一份可直接被回答引用的结构化成稿（{profile.summary_length_hint}）。

【预设问题】
{question_text[:1200]}

【主题分析】
{analysis[:3500]}

【资料洞察】
{all_sources[:18000]}

【其余候选文档】
{peer_docs}

【原始文档核心观点】
{before_text[:3000]}

要求：
1. 直接以 `## 直接结论` 开头，前 25% 篇幅先给出 6-8 条最关键的判断句，不要先铺背景。
2. 这些判断句应优先覆盖最容易决定答案走向的位置，尽量包含定义纠偏、边界条件、阈值、反例、争议澄清中的至少两项。
3. 主体只使用与问题直接相关的小节标题，可在 `## 关键分歧`、`## 条件与边界`、`## 最终判断` 这类标题中择用，不要使用与写作策略相关的标题。
4. 只保留真正能改变判断的内容：目标文档最有价值的主张、外部资料新增且强相关的依据、能明显纠正常见误解的边界句。
5. 不要出现“补洞”“独占”“前置”“超集”“框架”“其他候选文档”“最值得”“按此框架”等元话语，不要提及 `1.md`、`2.md`、`3.md`、`4.md` 或“某份文档”。
6. 不要解释自己的写作策略，也不要评价自己与其他材料谁更有辨识度；直接围绕问题作答。
7. 每个自然段首句都要可单独引用，并尽量带条件、对比或校正式表达。"""
        return system, user, 12288, 0.55

    if profile.summary_mode == "novelty_gap":
        system = "你是一位擅长把增量信息收束成直接答案的分析师。只能基于提供材料输出，不要编造未出现的结论。直接输出正文。"
        user = f"""围绕预设问题，生成一份可直接被回答引用的结构化成稿（{profile.summary_length_hint}）。

【预设问题】
{question_text[:1200]}

【主题分析】
{analysis[:3500]}

【资料洞察】
{all_sources[:18000]}

【其余候选文档】
{peer_docs}

【原始文档核心观点】
{before_text[:3000]}

要求：
1. 直接以 `## 直接结论` 开头，开头先给 5-7 条对回答问题最关键的判断句，不要先写综述式背景。
2. 每条判断都应尽量体现新增信息、限制条件、反例、阈值或争议澄清中的至少一种。
3. 主体只使用与问题直接相关的小节标题，可在 `## 关键分歧`、`## 容易被忽略的条件`、`## 最终判断` 这类标题中择用，不要使用与写作策略相关的标题。
4. 避免重复复述已经被广泛覆盖的共识表述，优先写真正能改变最终判断的内容。
5. 不要出现“补洞”“独占”“前置”“超集”“框架”“其他候选文档”“更优句子”“最值得”等元话语，不要提及 `1.md`、`2.md`、`3.md`、`4.md` 或“某份文档”。
6. 不要解释自己的写作策略，也不要比较自己与其他材料谁更好；直接围绕问题作答。
7. 每个自然段首句都要尽量可单独引用。"""
        return system, user, 12288, 0.55

    if profile.summary_mode == "novelty_gap_naturalized":
        system = "你是一位擅长把增量信息自然融入论述正文的分析师。只能基于提供材料输出，不要编造未出现的结论。直接输出正文。"
        user = f"""围绕预设问题，生成一份自然论述风格的高密度成稿（{profile.summary_length_hint}）。

【预设问题】
{question_text[:1200]}

【主题分析】
{analysis[:3500]}

【资料洞察】
{all_sources[:18000]}

【其余候选文档】
{peer_docs}

【原始文档核心观点】
{before_text[:3000]}

要求：
1. 不要用判断清单开头，不要先列 5-7 条短句；直接进入连贯论述。
2. 全文只保留 2-4 个与问题直接相关的小节标题，可在 `## 关键分歧`、`## 条件与边界`、`## 最终判断` 这类标题中择用。
3. 将新增信息、限制条件、反例、阈值、争议澄清自然嵌入段落，不要把这些信息写成显眼的模板化声明列表。
4. 仍然优先写真正能改变最终判断的内容，避免重复复述已经被广泛覆盖的共识表述。
5. 每个自然段首句都尽量是明确判断，但要融入正常论述，不要写成口号式短硬句堆叠。
6. 不要出现“补洞”“独占”“前置”“超集”“框架”“其他候选文档”“更优句子”“最值得”等元话语，不要提及 `1.md`、`2.md`、`3.md`、`4.md` 或“某份文档”。
7. 不要解释自己的写作策略，也不要比较自己与其他材料谁更好；直接围绕问题作答。"""
        return system, user, 12288, 0.55

    if profile.summary_mode == "query_anchored_novelty_gap":
        system = "你是一位擅长把差异化信息严密对齐到问题槽位的分析师。只能基于提供材料输出，不要编造未出现的结论。直接输出正文。"
        user = f"""围绕预设问题，生成一份“贴题增量优先”的结构化成稿（{profile.summary_length_hint}）。

【预设问题】
{question_text[:1200]}

【主题分析】
{analysis[:3500]}

【资料洞察】
{all_sources[:18000]}

【其余候选文档】
{peer_docs}

【原始文档核心观点】
{before_text[:3000]}

要求：
1. 直接以 `## 直接结论` 开头，开头先给 5-7 条最关键的判断句，不要先写综述式背景。
2. 每条新增信息都必须明确服务问题中的某个槽位：定义、核心判断、成立条件、边界、反例、适用范围；不能证明与题眼直接相关的内容，不得放进前两段。
3. 优先保留真正能改变最终回答走向的增量信息，而不是仅仅因为稀有就保留。
4. 允许使用定义纠偏、阈值句、条件句和反例句，但不要把它们写成口号式模板。
5. 主体只使用与问题直接相关的小节标题，可在 `## 关键判断`、`## 条件与边界`、`## 最终判断` 这类标题中择用。
6. 不要出现“补洞”“独占”“前置”“超集”“框架”“其他候选文档”“最值得”等元话语，不要提及 `1.md`、`2.md`、`3.md`、`4.md` 或“某份文档”。
7. 每个自然段首句都要尽量可单独引用，并明确对应到某个问题槽位。"""
        return system, user, 12288, 0.55

    if profile.summary_mode == "coverage_floor":
        system = "你是一位擅长在保持答案主导性的同时补齐必要共识信息的分析师。只能基于提供材料输出，不要编造未出现的结论。直接输出正文。"
        user = f"""围绕预设问题，生成一份“共享覆盖下限受控”的结构化成稿（{profile.summary_length_hint}）。

【预设问题】
{question_text[:1200]}

【主题分析】
{analysis[:3500]}

【资料洞察】
{all_sources[:18000]}

【其余候选文档】
{peer_docs}

【原始文档核心观点】
{before_text[:3000]}

要求：
1. 直接以 `## 直接结论` 开头，先回答问题，再展开关键依据和边界。
2. 在保留目标文档核心判断的前提下，补入一组最小共享覆盖：优先选择那些多份材料都支持、且最容易影响回答命中的共识信息。
3. 共享覆盖必须是“最小必要子集”，只补关键公共点，不要回退成大段背景综述或机械罗列共识。
4. 任何共享信息都必须服务最终判断、条件限制或常见误解澄清，不能挤掉真正有价值的差异化判断。
5. 主体只使用与问题直接相关的小节标题，可在 `## 关键依据`、`## 条件与边界`、`## 最终判断` 这类标题中择用。
6. 不要出现“补洞”“独占”“前置”“超集”“框架”“其他候选文档”“最值得”等元话语，不要提及 `1.md`、`2.md`、`3.md`、`4.md` 或“某份文档”。
7. 每段首句必须尽量可单独引用，同时避免过度铺陈共享背景。"""
        return system, user, 12288, 0.55

    if profile.summary_mode == "anchored_novelty_with_coverage_floor":
        system = "你是一位擅长兼顾差异化判断与共同引用命中的分析师。只能基于提供材料输出，不要编造未出现的结论。直接输出正文。"
        user = f"""围绕预设问题，生成一份“贴题增量 + 受控共享覆盖”的结构化成稿（{profile.summary_length_hint}）。

【预设问题】
{question_text[:1200]}

【主题分析】
{analysis[:3500]}

【资料洞察】
{all_sources[:18000]}

【其余候选文档】
{peer_docs}

【原始文档核心观点】
{before_text[:3000]}

要求：
1. 直接以 `## 直接结论` 开头，前两段优先放置与问题最贴合、最能改变判断的差异化信息。
2. 前两段中的新增信息都必须明确对应问题槽位：定义、核心判断、条件、边界、反例、适用范围。
3. 中后段补入最小共享覆盖，用来承接那些多份材料共有、且对回答命中率有帮助的关键共识点，但不能让共享信息反客为主。
4. 目标文档负责主判断、阈值、边界和纠偏；其他材料只负责补充证据、例子、数字或争议。
5. 主体只使用与问题直接相关的小节标题，可在 `## 关键判断`、`## 关键依据`、`## 条件与边界`、`## 最终判断` 这类标题中择用。
6. 不要出现“补洞”“独占”“前置”“超集”“框架”“其他候选文档”“最值得”等元话语，不要提及 `1.md`、`2.md`、`3.md`、`4.md` 或“某份文档”。
7. 每个自然段首句都尽量可单独引用，且全文要让读者能看出主干判断始终由目标文档主导。"""
        return system, user, 12288, 0.55

    if profile.summary_mode == "superset_guarded":
        system = "你是一位擅长把高信息密度材料收束成直接答案的分析师。只能基于提供材料输出，不要编造未出现的结论。直接输出正文。"
        user = f"""围绕预设问题，生成一份中长篇结构化成稿（{profile.summary_length_hint}）。

【预设问题】
{question_text[:1200]}

【主题分析】
{analysis[:3500]}

【资料洞察】
{all_sources[:18000]}

【其余候选文档】
{peer_docs}

【原始文档核心观点】
{before_text[:3000]}

要求：
1. 直接以 `## 直接结论` 开头，先给出最终判断，再展开最关键的依据和边界。
2. 主体只保留真正与问题强相关、能改变最终结论的内容，不要用篇幅重复背景、定义复述和泛化例子。
3. 主体只使用与问题直接相关的小节标题，可在 `## 关键依据`、`## 条件与边界`、`## 最终判断` 这类标题中择用，不要使用与写作策略相关的标题。
4. 总长度控制在 {profile.summary_length_hint}，追求信息密度而不是机械拉长篇幅。
5. 不要出现“补洞”“独占”“前置”“超集”“框架”“替代他源”“其他候选文档”“最值得”等元话语，不要提及 `1.md`、`2.md`、`3.md`、`4.md` 或“某份文档”。
6. 不要解释自己的写作策略，也不要说明自己删掉了什么；直接围绕问题作答。
7. 每段首句必须尽量可单独引用，并优先带条件、限制或对比。"""
        return system, user, 12288, 0.55

    if profile.summary_mode == "rebuttal":
        system = "你是一位擅长把常见误判收束成直接答案的分析师。只能基于提供材料输出，不要编造未出现的结论。直接输出正文。"
        user = f"""围绕预设问题，生成一份可直接被回答引用的结构化成稿（{profile.summary_length_hint}）。

【预设问题】
{question_text[:1200]}

【主题分析】
{analysis[:3500]}

【资料洞察】
{all_sources[:18000]}

【原始文档核心观点】
{before_text[:3000]}

要求：
1. 直接以 `## 直接结论` 开头，先给出最终判断，再展开最容易被误判的关键点。
2. 主体可使用 `## 常见误判`、`## 为什么不能简单地下结论`、`## 条件与边界`、`## 最终判断` 这类与问题直接相关的小节标题，不要使用与写作策略相关的标题。
3. 先列出 5-8 条短硬判断句，优先采用“常见说法忽略了……”“更稳妥的判断是……”这类校正式表达，但不要解释自己在做反驳写作。
4. 每条判断都尽量包含依据、条件、限制或典型误用场景。
5. 不要出现“补洞”“独占”“前置”“超集”“框架”“其他候选文档”“按此框架”等元话语，不要提及 `1.md`、`2.md`、`3.md`、`4.md` 或“某份文档”。
6. 句子要短，结论要硬，方便直接被答案引用。"""
        return system, user, 12288, 0.6

    if profile.summary_mode == "nozws_implicit_bestof":
        system = "你是一位顶尖的权威研究机构首席分析师。只能基于提供材料输出，不要编造未出现的结论。严禁输出任何前缀、开场白、说明文字，直接以正文标题开始输出。"
        user = f"""基于以下所有材料，撰写一份高信息密度的权威综述（不少于5000字），整体章法尽量贴近“概念辨析 + 权威综述 + 问题解答”的成熟长文结构。

【预设问题】
{question_text[:1200]}

【主题分析】
{analysis[:4000]}

【所有搜索结果汇总】
{all_sources[:20000]}

【其余候选文档】
{peer_docs}

【原始文档核心观点】
{before_text[:3000]}

要求：
1. 直接以正文标题（如 `## 核心概念辨析` 或 `## 一、核心概念与定义`）开始输出，保留多级标题、分层论述和尾部问题解答的整体骨架。
2. 保持自然完整的权威综述写法，不要把优化信号写成显眼的策略模板、前置清单或口号式声明。
3. 将现有已证明有效的优化信号隐形融入正文：优先保留能改变结论的增量信息，主动补入易漏但高价值的条件句、边界句、定义纠偏、反例与争议澄清，同时避免低价值重复扩写。
4. 需要兼顾 `after_nozws` 风格的可抽取性与论述完整度：可使用多级标题、列表和对比结构，但不要出现“补洞”“独占”“前置”“超集”“框架”“其他候选文档”“最值得”等元话语。
5. 每个自然段首句必须是明确判断或结论，但要融入正常论述，不要只堆短硬句。
6. 内容必须足够长且全面，但不要添加与材料无关的虚构信息，也不要提及 `1.md`、`2.md`、`3.md`、`4.md` 或“某份文档”。"""
        return system, user, 65536, 0.68

    system = "你是一位顶尖的权威研究机构首席分析师。只能基于提供材料输出，不要编造未出现的结论。严禁输出任何前缀、开场白、说明文字，直接以正文标题开始输出。"
    user = f"""基于以下所有材料，撰写一份高信息密度的权威综述（不少于5000字）。

【主题分析】
{analysis[:4000]}

【所有搜索结果汇总】
{all_sources[:20000]}

【原始文档核心观点】
{before_text[:3000]}

要求：
1. 直接以正文标题（如 `## 一、核心概念与定义`）开始输出。
2. 覆盖该主题的关键维度：定义、原理、前沿进展、争议、案例、未来展望。
3. 使用多级标题、列表和对比结构提升可抽取性。
4. 每个自然段首句必须是明确判断或结论。
5. 内容必须足够长且全面，但不要添加与材料无关的虚构信息。"""
    return system, user, 65536, 0.7


def build_qa_prompts(profile: GenerationProfile, summary_section: str, question_text: str) -> tuple[str, str, int, float]:
    if profile.qa_mode == "rebuttal":
        system = "你是一个专业的问答生成专家，擅长把误解反驳改写成高可复用问答。"
        user = f"""基于以下文档，生成 {profile.qa_count} 个围绕预设问题常见误解的问答对。

【预设问题】
{question_text[:1200]}

【文档内容】
{summary_section[:18000]}

格式要求：
1. 直接以 `## 误解型问答` 开头。
2. 每个回答先指出误解，再给正解和条件。
3. 每个回答控制在 2-3 句，尽量可直接挪用到最终回答里。"""
        return system, user, 6144, 0.55

    if profile.qa_mode == "answer_ready":
        system = "你是一个专业的问答生成专家，擅长把长文改写成可直接复用的短问答。"
        user = f"""基于以下文档，围绕预设问题拆成 10 个高可复用问答对。

【预设问题】
{question_text[:1200]}

【文档内容】
{summary_section[:18000]}

格式要求：
1. 直接以 `## 可复用问答` 开头。
2. 每个问题都对应预设问题的一个关键子问题。
3. 每个回答必须包含明确判断、依据或条件，长度控制在 2-3 句。
4. 避免空泛解释。"""
        return system, user, 6144, 0.55

    system = "你是一个专业的问答生成专家。"
    user = f"""基于以下权威综述，生成 12 个精确的问答对。

【权威综述】
{summary_section[:20000]}

格式要求：
Q1: [问题]
A1: [简短答案，含1-2个量化事实]

请直接输出 Q&A 内容。"""
    return system, user, 8192, 0.6


def flow_3_build_document(
    flow_1_result: dict,
    flow_2_result: dict,
    before_text: str,
    other_texts: list[str],
    question_text: str,
    profile: GenerationProfile,
) -> tuple[str, str, str]:
    """构建文档三部分：概念辨析、主体内容、Q&A。"""
    print("\n[流程三] 正在构建文档内容...")

    analysis = flow_1_result.get("analysis", "")
    insight_list = flow_2_result.get("insight_list", "")
    fetched_contents = flow_2_result.get("fetched_contents", [])

    print("  [3.1] 生成概念辨析...")
    concept_system, concept_user, concept_tokens, concept_temp = build_concept_prompts(
        profile, analysis, insight_list, question_text
    )
    concept_section = ""
    for attempt in range(3):
        concept_section = call_llm(
            [
                {"role": "system", "content": concept_system},
                {"role": "user", "content": concept_user},
            ],
            max_tokens=concept_tokens,
            temperature=concept_temp,
        )
        if concept_section and len(concept_section) > 300:
            break
        print(f"  [!] 概念辨析生成失败（第{attempt + 1}次），正在重试...")
        time.sleep(3)

    print("  [3.2] 生成主体内容...")
    summary_system, summary_user, summary_tokens, summary_temp = build_summary_prompts(
        profile, analysis, insight_list, fetched_contents, before_text, other_texts, question_text
    )
    summary_section = ""
    for attempt in range(3):
        summary_section = call_llm(
            [
                {"role": "system", "content": summary_system},
                {"role": "user", "content": summary_user},
            ],
            max_tokens=summary_tokens,
            temperature=summary_temp,
        )
        if summary_section and len(summary_section) > 600:
            break
        print(f"  [!] 主体内容生成失败（第{attempt + 1}次），正在重试...")
        time.sleep(3)

    print("  [3.3] 生成 Q&A...")
    qa_system, qa_user, qa_tokens, qa_temp = build_qa_prompts(profile, summary_section, question_text)
    qa_section = ""
    for attempt in range(3):
        qa_section = call_llm(
            [
                {"role": "system", "content": qa_system},
                {"role": "user", "content": qa_user},
            ],
            max_tokens=qa_tokens,
            temperature=qa_temp,
        )
        if qa_section and len(qa_section) > 150:
            break
        print(f"  [!] Q&A 生成失败（第{attempt + 1}次），正在重试...")
        time.sleep(3)

    return concept_section, summary_section, qa_section


def ensure_required_sections(
    concept_section: str,
    summary_section: str,
    qa_section: str,
    profile: GenerationProfile,
) -> None:
    section_map = {
        "concept": concept_section.strip(),
        "summary": summary_section.strip(),
        "qa": qa_section.strip(),
    }
    min_lengths = {
        "concept": 300,
        "summary": 600,
        "qa": 150,
    }
    failures = []
    for name in profile.section_order:
        content = section_map.get(name, "")
        minimum = min_lengths.get(name, 1)
        if len(content) < minimum:
            failures.append(f"{name}<{minimum} ({len(content)})")
    if failures:
        raise RuntimeError(f"生成结果不完整，停止保存: {', '.join(failures)}")


def flow_4_combine_document(
    concept_section: str,
    summary_section: str,
    qa_section: str,
    profile: GenerationProfile,
) -> str:
    """按配置顺序组合文档。"""
    print("\n[流程四] 正在组合文档...")
    section_map = {
        "concept": concept_section.strip(),
        "summary": summary_section.strip(),
        "qa": qa_section.strip(),
    }
    sections = [section_map[name] for name in profile.section_order if section_map.get(name)]
    return "\n\n---\n\n".join(section for section in sections if section)


def save_profile_document(output_dir: Path, final_document: str, profile: GenerationProfile) -> None:
    output_path = output_dir / profile.output_name
    output_path.write_text(final_document, encoding="utf-8")
    print(f"\n  ✅ 已保存 {profile.label}: {output_path}")
    print(f"  文档长度: {len(final_document)} 字符")

    if profile.generate_zws_companion:
        print("\n  [注入] 正在为默认基线派生 Full-ZWS 文档（U+200B）...")
        after_document = inject_zero_width_all_chars(final_document)
        after_path = output_dir / "after.md"
        after_path.write_text(after_document, encoding="utf-8")
        print(f"  ✅ 已保存 Full-ZWS 文档: {after_path}")
        print(f"  文档长度: {len(after_document)} 字符")


def main() -> None:
    parser = argparse.ArgumentParser(description="GEO Document Content Optimization System")
    parser.add_argument("--dataset", type=int, required=True, help="数据集编号（如 1）")
    parser.add_argument(
        "--profile",
        choices=sorted(GENERATION_PROFILES),
        default="baseline",
        help="生成配置：baseline / skeleton / stance / dimensions / dimensions_rebuttal / evidence / rebuttal / frontload_rebuttal / novelty_gap / superset_guarded / frontload_novelty_guarded / rebuttal_compact / rebuttal_extended / novelty_gap_rebuttal_extended / novelty_gap_naturalized / query_anchored_novelty_gap / coverage_floor / anchored_novelty_with_coverage_floor / nozws_implicit_bestof / rebuttal_ultra",
    )
    parser.add_argument("--refresh-cache", action="store_true", help="忽略已有分析/搜索缓存并重新执行")
    args = parser.parse_args()

    profile = GENERATION_PROFILES[args.profile]

    print("=" * 60)
    print("  GEO Document Content Optimization System")
    print("=" * 60)
    print(f"\n数据集: data/baseline/{args.dataset}/")
    print(f"生成配置: {profile.key} -> {profile.output_name}")

    print("\n[加载数据]")
    before_text, other_texts, question_text = load_dataset(args.dataset)
    print(f"  before.md: {len(before_text)} 字符")
    print(f"  其他文档: {len(other_texts)} 篇")
    print(f"  question.md: {len(question_text)} 字符")

    output_dir = dataset_output_dir(args.dataset)
    cache_root = cache_dir(output_dir)
    analysis_cache_path = cache_root / f"flow1_{profile.key}_analysis.md"
    legacy_search_cache_path = cache_root / f"flow2_{profile.key}_search.json"
    search_cache_path = cache_root / search_cache_file_name(profile.key)

    if args.refresh_cache:
        flow_1_result = flow_1_analyze(before_text, other_texts, question_text, profile)
        write_text_cache(analysis_cache_path, flow_1_result.get("analysis", ""))
    else:
        cached_analysis = load_text_cache(analysis_cache_path)
        if cached_analysis:
            print("\n[流程一] 复用缓存分析结果...")
            flow_1_result = {"analysis": cached_analysis}
        else:
            flow_1_result = flow_1_analyze(before_text, other_texts, question_text, profile)
            write_text_cache(analysis_cache_path, flow_1_result.get("analysis", ""))
    print("\n✅ 流程一完成")
    print(flow_1_result["analysis"][:500] + "...")

    if args.refresh_cache:
        flow_2_result = flow_2_search(flow_1_result, before_text, other_texts, question_text, profile)
        write_json_cache(search_cache_path, flow_2_result)
    else:
        cached_search = load_json_cache(search_cache_path)
        if is_valid_search_cache(cached_search):
            print(f"\n[流程二] 复用缓存搜索结果: {search_cache_path.name}")
            flow_2_result = cached_search
        else:
            if cached_search is not None:
                print(f"\n[流程二] 检测到旧版或非中文缓存，已自动重建: {search_cache_path.name}")
            elif legacy_search_cache_path.exists():
                print(f"\n[流程二] 检测到旧英文缓存，已自动重建: {legacy_search_cache_path.name}")
            flow_2_result = flow_2_search(flow_1_result, before_text, other_texts, question_text, profile)
            write_json_cache(search_cache_path, flow_2_result)
    print("\n✅ 流程二完成")
    print(f"  搜索关键词: {', '.join(flow_2_result.get('keywords', [])[:5])}...")
    print(f"  搜索结果: {len(flow_2_result.get('search_results', []))} 条")

    concept_section, summary_section, qa_section = flow_3_build_document(
        flow_1_result,
        flow_2_result,
        before_text,
        other_texts,
        question_text,
        profile,
    )
    print("\n✅ 流程三完成")
    print(f"  概念辨析: {len(concept_section)} 字符")
    print(f"  主体内容: {len(summary_section)} 字符")
    print(f"  Q&A: {len(qa_section)} 字符")

    ensure_required_sections(concept_section, summary_section, qa_section, profile)
    final_document = flow_4_combine_document(concept_section, summary_section, qa_section, profile)
    print("\n✅ 流程四完成")
    print(f"  最终文档长度: {len(final_document)} 字符")

    save_profile_document(output_dir, final_document, profile)


if __name__ == "__main__":
    main()
