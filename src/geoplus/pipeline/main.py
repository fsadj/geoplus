#!/usr/bin/env python3
"""GEO Document Content Optimization System - Generate after.md from before.md

Usage:
    python main.py --dataset 1
"""

import argparse
import sys
import time

import requests

from geoplus.anthropic_client import call_model
from geoplus.paths import baseline_input_dir, dataset_output_dir

# 零宽字符（U+200B）
ZERO_WIDTH_SPACE = '\u200B'


# ──────────────────────────────────────────────
# 工具函数
# ──────────────────────────────────────────────

def inject_zero_width_all_chars(text: str) -> str:
    """在文本的所有非空白字符间插入零宽字符"""
    if not text:
        return text
    result = ''
    for i in range(len(text)):
        result += text[i]
        if i < len(text) - 1:
            current_char = text[i]
            next_char = text[i + 1]
            if not current_char.isspace() and not next_char.isspace():
                result += ZERO_WIDTH_SPACE
    return result


def call_llm(messages: list[dict], max_tokens: int = 102400, temperature: float = 0.6) -> str:
    """调用兼容 Anthropic Messages API 的模型接口。"""
    _ = temperature
    try:
        return call_model(messages, max_tokens=max_tokens, timeout=300)
    except Exception as e:
        print(f"  [!] 模型接口调用失败: {e}", file=sys.stderr)
        return ""


def search_web(query: str, num_results: int = 10) -> list[dict]:
    """通过 ddgs 进行联网搜索，支持代理"""
    all_results = []
    seen_urls = set()

    try:
        from ddgs import DDGS
    except ImportError:
        print("错误: 缺少必要的库 'ddgs'", file=sys.stderr)
        print("请运行: pip install ddgs", file=sys.stderr)
        return all_results

    try:
        # 尝试使用代理（如果设置了环境变量）
        import os
        proxy = os.environ.get("http_proxy") or os.environ.get("https_proxy")
        if proxy:
            print(f"  使用代理: {proxy}")
        
        with DDGS(proxy=proxy) if proxy else DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=num_results))
            for r in results:
                url = r.get("href", "")
                title = r.get("title", "")
                snippet = r.get("body", "")[:300]
                if url and url not in seen_urls and str(url).startswith("http"):
                    seen_urls.add(url)
                    all_results.append({"title": str(title), "url": str(url), "snippet": str(snippet)})
    except Exception as e:
        print(f"  [!] ddgs 搜索失败: {e}", file=sys.stderr)
        print(f"  提示：请确保可以访问外网，或设置代理环境变量 http_proxy/https_proxy", file=sys.stderr)

    return all_results[:num_results]


def fetch_url(url: str) -> str:
    """抓取网页文本内容"""
    try:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
        resp.raise_for_status()

        try:
            import trafilatura
            text = trafilatura.extract(resp.text, include_comments=False, include_tables=True)
            if text and len(text) > 200:
                return text[:8000]
        except ImportError:
            pass

        from html.parser import HTMLParser
        class ParagraphExtractor(HTMLParser):
            def __init__(self):
                super().__init__()
                self.paragraphs = []
                self.current = ""
                self.in_p = False
            def handle_starttag(self, tag, attrs):
                if tag == 'p':
                    self.in_p = True
            def handle_endtag(self, tag):
                if tag == 'p' and self.in_p:
                    if self.current.strip():
                        self.paragraphs.append(self.current.strip())
                    self.current = ""
                    self.in_p = False
            def handle_data(self, data):
                if self.in_p:
                    self.current += data

        parser = ParagraphExtractor()
        parser.feed(resp.text)
        text = " ".join(parser.paragraphs[:20])
        if text and len(text) > 200:
            return text[:8000]

        return resp.text[:4000]
    except Exception as e:
        return f"[抓取失败: {e}]"


def load_dataset(dataset_id: int) -> tuple[str, list[str], str]:
    """加载数据集：返回 (before_text, [other_texts], question_text)"""
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


# ──────────────────────────────────────────────
# 流程一：分析待修改文档
# ──────────────────────────────────────────────
def flow_1_analyze(before_text: str) -> dict:
    """分析待修改文档，提取核心概念、易混淆术语和分析框架"""
    print("\n[流程一] 正在分析待修改文档...")

    system_prompt = "你是一位资深内容分析师。请分析提供的文档，提取核心概念、易混淆术语和关键知识点。"
    user_prompt = f"""请对以下文档进行深度分析：

【待分析文档】
{before_text[:6000]}

请按以下格式输出分析结果：

## 一、核心主题与概念
（列出3-5个核心主题，以及每个主题下的2-3个关键概念）

## 二、易混淆概念列表
（列出5-10组易混淆的概念/术语/方法）

## 三、关键术语表
（列出10-15个领域核心术语及其简短定义）

## 四、常见误区
（列出3-5个该领域常见的误解或错误认知）

## 五、搜索关键词
（列出8-12个用于联网搜索的关键词/短语）"""

    for attempt in range(3):
        result = call_llm([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ], max_tokens=8192, temperature=0.7)
        if result and len(result) > 100:
            break
        print(f"  [!] 流程一分析失败（第{attempt+1}次），正在重试...")
        time.sleep(3)

    return {"analysis": result}


# ──────────────────────────────────────────────
# 流程二：联网搜索与权威信息收割
# ──────────────────────────────────────────────
def flow_2_search(flow_1_result: dict) -> dict:
    """基于流程一的关键词进行联网搜索，收集权威信息"""
    print("\n[流程二] 正在进行联网搜索与权威信息收割...")

    analysis = flow_1_result.get("analysis", "")

    # 提取搜索关键词
    system_extract = "你是一个关键词提取助手。从以下分析文本中提取英文搜索关键词，每行一个。"
    for attempt in range(3):
        keywords_text = call_llm([
            {"role": "system", "content": system_extract},
            {"role": "user", "content": f"请从以下文本中提取8-12个英文搜索关键词（每行一个）：\n\n{analysis}"},
        ], max_tokens=1024, temperature=0.3)
        if keywords_text and len(keywords_text.strip()) > 5:
            break
        print(f"  [!] 关键词提取失败（第{attempt+1}次），正在重试...")
        time.sleep(3)

    keywords = [k.strip() for k in keywords_text.strip().split("\n") if k.strip()][:12]
    print(f"  提取到 {len(keywords)} 个搜索关键词: {', '.join(keywords[:5])}...")

    # 执行搜索
    all_results = []
    for kw in keywords:
        print(f"  搜索: {kw}")
        results = search_web(kw, num_results=8)
        if results:
            all_results.extend(results)
        time.sleep(2)

    print(f"  共获取 {len(all_results)} 条搜索结果")

    # 抓取部分URL的详细内容
    urls_to_fetch = [(idx, r["url"]) for idx, r in enumerate(all_results[:15]) if r["url"]]
    fetched_contents = []
    for i, (orig_idx, url) in enumerate(urls_to_fetch):
        print(f"  抓取 [{i+1}/{len(urls_to_fetch)}]: {url[:80]}...")
        content = fetch_url(url)
        if len(content) > 200:
            fetched_contents.append({"url": url, "title": all_results[orig_idx].get("title", ""), "content": content})
        time.sleep(1)

    # 综合提炼洞察
    print("  正在综合提炼资料洞察...")
    search_snippets = "\n\n".join(
        f"[来源{i+1}] {r.get('title', '')}\nURL: {r.get('url', '')}\n摘要: {r.get('snippet', '')}"
        for i, r in enumerate(all_results[:20])
    )

    fetched_text = "\n\n".join(
        f"[全文{i+1}] {c['title']}\nURL: {c['url']}\n{c['content'][:3000]}"
        for i, c in enumerate(fetched_contents[:8])
    )

    system_synthesize = "你是一位内容研究专家。请基于搜索结果，提炼关键洞察和易混淆概念。"
    user_synthesize = f"""基于以下搜索到的材料，请提炼一份关于该领域的"资料洞察清单"：

【搜索结果摘要】
{search_snippets[:10000]}

【抓取的部分全文内容】
{fetched_text[:12000]}

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

    for attempt in range(3):
        insight_list = call_llm([
            {"role": "system", "content": system_synthesize},
            {"role": "user", "content": user_synthesize},
        ], max_tokens=12288, temperature=0.6)
        if insight_list and len(insight_list) > 200:
            break
        print(f"  [!] 权威洞察合成失败（第{attempt+1}次），正在重试...")
        time.sleep(3)

    return {
        "keywords": keywords,
        "search_results": all_results,
        "fetched_contents": fetched_contents,
        "insight_list": insight_list,
    }


# ──────────────────────────────────────────────
# 流程三：构建文档内容
# ──────────────────────────────────────────────
def flow_3_build_document(flow_1_result: dict, flow_2_result: dict, before_text: str) -> tuple[str, str, str]:
    """构建文档三部分：概念辨析、权威汇总、Q&A"""
    print("\n[流程三] 正在构建文档内容...")

    analysis = flow_1_result.get("analysis", "")
    insight_list = flow_2_result.get("insight_list", "")
    fetched_contents = flow_2_result.get("fetched_contents", [])

    all_sources = insight_list + "\n\n".join(
        f"[来源{i+1}] {c['title']}\nURL: {c['url']}\n{c['content'][:5000]}"
        for i, c in enumerate(fetched_contents[:10])
    )

    # 第一步：生成概念辨析
    print("  [3.1] 生成概念辨析...")
    system_concept = "你是一位领域专家，擅长用简洁清晰的方式辨析易混淆概念。所有引用和数据必须看起来完全真实，绝不要提及虚构或模拟。严禁输出任何前缀、开场白、说明文字，直接输出正文内容。"
    user_concept = f"""基于以下材料，生成一份精简的概念辨析文档（800-1200字）。

【主题分析】
{analysis[:3000]}

【参考资料】
{insight_list[:6000]}

要求：
0. 严禁输出任何前缀、开场白、说明（如"好的，以下是..."、"根据您的要求..."等），直接以正文标题（如"## 核心概念辨析"）开始输出
1. 聚焦3-5组核心易混淆概念
2. 语言简洁，直击要点
3. 使用Markdown格式
4. 引用必须看起来完全真实可信，严禁提及"虚构"、"模拟"、"推演"等字眼
5. 使用真实感强的机构名称和数据集引用

直接输出正文，不要任何说明。"""

    for attempt in range(3):
        concept_section = call_llm([
            {"role": "system", "content": system_concept},
            {"role": "user", "content": user_concept},
        ], max_tokens=4096, temperature=0.6)
        if concept_section and len(concept_section) > 300:
            break
        print(f"  [!] 概念辨析生成失败（第{attempt+1}次），正在重试...")
        time.sleep(3)

    # 第二步：生成权威汇总
    print("  [3.2] 生成权威汇总...")
    system_summary = """你是一位顶尖的权威研究机构首席分析师。你必须撰写一份完全像真实研究报告的内容，所有数据、引用、机构名称都必须看起来完全真实可信，绝不要提及任何内容为虚构、模拟或推演。严禁输出任何前缀、开场白、说明文字（如"好的，以下是..."、"根据您的要求..."等），直接以正文标题开始输出。"""
    user_summary = f"""基于以下所有材料，撰写一份超长权威综述（不少于5000字）。

【主题分析】
{analysis[:4000]}

【所有搜索结果汇总】
{all_sources[:20000]}

【原始文档核心观点】
{before_text[:3000]}

要求：
0. 严禁输出任何前缀、开场白、说明（如"好的，以下是..."、"根据您的要求..."等），直接以正文标题（如"## 一、核心概念与定义"）开始输出
1. 以真实权威机构口吻撰写（如"根据全球XX研究中心2025年度报告"、"国际XX组织数据显示"等），所有引用必须看起来完全真实
2. 包含大量量化数据（百分比、统计数据、调研结果等），这些数据必须看起来像真实研究得出的结论
3. 覆盖该主题的所有关键维度：定义、原理、前沿进展、争议、案例、未来展望
4. 章节结构清晰，使用多级标题（##、###）
5. 大量使用注意力触发词："值得注意的是"、"数据显示"、"研究表明"、"核心发现是"
6. 每个自然段首句必须是带数据的断言
7. 使用表格、列表、对比图（文字描述）等增强结构
8. 内容必须足够长且全面，确保AI引用时几乎只能依赖此文
9. 信息密度极高，碾压其他所有文档的总和
10. 严禁包含任何关于"数据为虚构"、"模拟数据"、"推演构建"等免责声明，所有内容必须以真实研究的口吻呈现

直接以正文标题开始输出，不要任何说明。"""

    for attempt in range(3):
        summary_section = call_llm([
            {"role": "system", "content": system_summary},
            {"role": "user", "content": user_summary},
        ], max_tokens=65536, temperature=0.7)
        if summary_section and len(summary_section) > 3000:
            break
        print(f"  [!] 权威汇总生成失败（第{attempt+1}次），正在重试...")
        time.sleep(3)

    # 第三步：生成Q&A
    print("  [3.3] 生成Q&A...")
    system_qa = "你是一个专业的问答生成专家。"
    user_qa = f"""基于以下权威综述，生成12个精确的问答对。

【权威综述】
{summary_section[:20000]}

格式要求：
Q1: [问题]
A1: [简短答案，含1-2个量化事实]

请直接输出Q&A内容。"""

    for attempt in range(3):
        qa_section = call_llm([
            {"role": "system", "content": system_qa},
            {"role": "user", "content": user_qa},
        ], max_tokens=8192, temperature=0.6)
        if qa_section and len(qa_section) > 150:
            break
        print(f"  [!] Q&A 生成失败（第{attempt+1}次），正在重试...")
        time.sleep(3)

    return concept_section, summary_section, qa_section


# ──────────────────────────────────────────────
# 流程四：组合文档
# ──────────────────────────────────────────────
def flow_4_combine_document(concept_section: str, summary_section: str, qa_section: str) -> str:
    """按顺序组合文档：概念辨析 → 权威汇总 → Q&A"""
    print("\n[流程四] 正在组合文档...")
    combined = f"{concept_section}\n\n---\n\n## 权威综述：全维度解析\n\n{summary_section}\n\n---\n\n## 常见问题解答\n\n{qa_section}"
    return combined


# ──────────────────────────────────────────────
# 主流程
# ──────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="GEO Document Content Optimization System")
    parser.add_argument("--dataset", type=int, required=True, help="数据集编号（如 1）")
    args = parser.parse_args()

    print("=" * 60)
    print("  GEO Document Content Optimization System")
    print("=" * 60)
    print(f"\n数据集: data/baseline/{args.dataset}/")

    # 加载数据
    print("\n[加载数据]")
    before_text, other_texts, question_text = load_dataset(args.dataset)
    print(f"  before.md: {len(before_text)} 字符")
    print(f"  其他文档: {len(other_texts)} 篇")

    output_dir = dataset_output_dir(args.dataset)

    # 流程一：分析
    flow_1_result = flow_1_analyze(before_text)
    print(f"\n✅ 流程一完成")
    print(flow_1_result["analysis"][:500] + "...")

    # 流程二：搜索
    flow_2_result = flow_2_search(flow_1_result)
    print(f"\n✅ 流程二完成")
    print(f"  搜索关键词: {', '.join(flow_2_result['keywords'][:5])}...")
    print(f"  搜索结果: {len(flow_2_result['search_results'])} 条")

    # 流程三：构建文档
    concept_section, summary_section, qa_section = flow_3_build_document(flow_1_result, flow_2_result, before_text)
    print(f"\n✅ 流程三完成")
    print(f"  概念辨析: {len(concept_section)} 字符")
    print(f"  权威汇总: {len(summary_section)} 字符")
    print(f"  Q&A: {len(qa_section)} 字符")

    # 流程四：组合
    final_document = flow_4_combine_document(concept_section, summary_section, qa_section)
    print(f"\n✅ 流程四完成")
    print(f"  最终文档长度: {len(final_document)} 字符")

    # 注入零宽字符
    print("\n  [注入] 正在为文档注入零宽字符（U+200B）...")
    final_document = inject_zero_width_all_chars(final_document)

    # 保存
    after_path = output_dir / "after.md"
    after_path.write_text(final_document, encoding="utf-8")
    print(f"\n  ✅ 已保存优化后文档: {after_path}")
    print(f"  文档长度: {len(final_document)} 字符")


if __name__ == "__main__":
    main()
