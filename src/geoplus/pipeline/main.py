#!/usr/bin/env python3
"""GEO Document Content Optimization System.

Usage:
    python main.py --dataset 1
    python main.py --dataset 3 --profile skeleton
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import requests

from geoplus.anthropic_client import call_model
from geoplus.paths import baseline_input_dir, dataset_output_dir

ZERO_WIDTH_SPACE = "​"


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


def search_web(query: str, num_results: int = 10) -> list[dict]:
    """通过 ddgs 进行联网搜索，支持代理。"""
    all_results: list[dict] = []
    seen_urls: set[str] = set()

    try:
        from ddgs import DDGS
    except ImportError:
        print("错误: 缺少必要的库 'ddgs'", file=sys.stderr)
        print("请运行: pip install ddgs", file=sys.stderr)
        return all_results

    try:
        import os

        proxy = os.environ.get("http_proxy") or os.environ.get("https_proxy")
        if proxy:
            print(f"  使用代理: {proxy}")

        with DDGS(proxy=proxy) if proxy else DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=num_results))
            for result in results:
                url = result.get("href", "")
                title = result.get("title", "")
                snippet = result.get("body", "")[:300]
                if url and url not in seen_urls and str(url).startswith("http"):
                    seen_urls.add(url)
                    all_results.append({"title": str(title), "url": str(url), "snippet": str(snippet)})
    except Exception as exc:
        print(f"  [!] ddgs 搜索失败: {exc}", file=sys.stderr)
        print("  提示：请确保可以访问外网，或设置代理环境变量 http_proxy/https_proxy", file=sys.stderr)

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
    for file_path in sorted(base.glob("*.md")):
        if file_path.name in {"before.md", "question.md"}:
            continue
        content = file_path.read_text(encoding="utf-8")
        if content.strip():
            other_texts.append(f"【{file_path.name}】\n{content}")

    return before_text, other_texts, question_text


def cache_dir(output_dir: Path) -> Path:
    path = output_dir / "_cache"
    path.mkdir(exist_ok=True)
    return path


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


def flow_1_analyze(before_text: str, question_text: str, profile: GenerationProfile) -> dict:
    """分析待修改文档，提取核心概念、易混淆术语和分析框架。"""
    print("\n[流程一] 正在分析待修改文档...")

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


def flow_2_search(flow_1_result: dict, question_text: str, profile: GenerationProfile) -> dict:
    """基于流程一的关键词进行联网搜索，收集权威信息。"""
    print("\n[流程二] 正在进行联网搜索与权威信息收割...")

    analysis = flow_1_result.get("analysis", "")

    system_extract = "你是一个关键词提取助手。从以下分析文本中提取英文搜索关键词，每行一个。"
    keywords_text = ""
    for attempt in range(3):
        keywords_text = call_llm(
            [
                {"role": "system", "content": system_extract},
                {
                    "role": "user",
                    "content": f"请从以下文本中提取8-12个英文搜索关键词（每行一个）：\n\n{analysis}",
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
    search_snippets = "\n\n".join(
        f"[来源{i + 1}] {result.get('title', '')}\nURL: {result.get('url', '')}\n摘要: {result.get('snippet', '')}"
        for i, result in enumerate(all_results[:20])
    )
    fetched_text = "\n\n".join(
        f"[全文{i + 1}] {item['title']}\nURL: {item['url']}\n{item['content'][:3000]}"
        for i, item in enumerate(fetched_contents[:8])
    )

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
        user = f"""围绕预设问题，把以下材料整理成一组“判题维度卡片”（1000-1500字）。

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
    user = f"""基于以下材料，生成一份精简的概念辨析文档（800-1200字）。

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
    question_text: str,
) -> tuple[str, str, int, float]:
    all_sources = insight_list + "\n\n".join(
        f"[来源{i + 1}] {item['title']}\nURL: {item['url']}\n{item['content'][:5000]}"
        for i, item in enumerate(fetched_contents[:10])
    )

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

    if profile.summary_mode == "rebuttal":
        system = "你是一位擅长通过反驳常见误解来提升答案可引用性的分析师。只能基于提供材料输出，不要编造未出现的结论。直接输出正文。"
        user = f"""围绕预设问题，生成一份“误解反驳 + 正解总结”文档（1500-2200字）。

【预设问题】
{question_text[:1200]}

【主题分析】
{analysis[:3500]}

【资料洞察】
{all_sources[:18000]}

【原始文档核心观点】
{before_text[:3000]}

要求：
1. 直接以 `## 常见误解与反驳` 开头。
2. 先列出 5-8 组“不是 A，而是 B”或“常见说法忽略了 C 条件”的反驳句。
3. 再给 `## 正确判断框架`，总结回答问题时最稳妥的结论与边界。
4. 每条反驳都要尽量包含依据、条件或典型误用场景。
5. 句子要短，结论要硬，方便直接被答案引用。"""
        return system, user, 12288, 0.6

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
        user = f"""基于以下文档，生成 8 个围绕预设问题常见误解的问答对。

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
        profile, analysis, insight_list, fetched_contents, before_text, question_text
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
        help="生成配置：baseline / skeleton / stance / dimensions / evidence / rebuttal",
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
    analysis_cache_path = cache_root / "flow1_analysis.md"
    search_cache_path = cache_root / "flow2_search.json"

    if args.refresh_cache:
        flow_1_result = flow_1_analyze(before_text, question_text, profile)
        write_text_cache(analysis_cache_path, flow_1_result.get("analysis", ""))
    else:
        cached_analysis = load_text_cache(analysis_cache_path)
        if cached_analysis:
            print("\n[流程一] 复用缓存分析结果...")
            flow_1_result = {"analysis": cached_analysis}
        else:
            flow_1_result = flow_1_analyze(before_text, question_text, profile)
            write_text_cache(analysis_cache_path, flow_1_result.get("analysis", ""))
    print("\n✅ 流程一完成")
    print(flow_1_result["analysis"][:500] + "...")

    if args.refresh_cache:
        flow_2_result = flow_2_search(flow_1_result, question_text, profile)
        write_json_cache(search_cache_path, flow_2_result)
    else:
        cached_search = load_json_cache(search_cache_path)
        if cached_search:
            print("\n[流程二] 复用缓存搜索结果...")
            flow_2_result = cached_search
        else:
            flow_2_result = flow_2_search(flow_1_result, question_text, profile)
            write_json_cache(search_cache_path, flow_2_result)
    print("\n✅ 流程二完成")
    print(f"  搜索关键词: {', '.join(flow_2_result.get('keywords', [])[:5])}...")
    print(f"  搜索结果: {len(flow_2_result.get('search_results', []))} 条")

    concept_section, summary_section, qa_section = flow_3_build_document(
        flow_1_result,
        flow_2_result,
        before_text,
        question_text,
        profile,
    )
    print("\n✅ 流程三完成")
    print(f"  概念辨析: {len(concept_section)} 字符")
    print(f"  主体内容: {len(summary_section)} 字符")
    print(f"  Q&A: {len(qa_section)} 字符")

    final_document = flow_4_combine_document(concept_section, summary_section, qa_section, profile)
    print("\n✅ 流程四完成")
    print(f"  最终文档长度: {len(final_document)} 字符")

    save_profile_document(output_dir, final_document, profile)


if __name__ == "__main__":
    main()
