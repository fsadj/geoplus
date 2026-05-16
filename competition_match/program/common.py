from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Callable, Iterable
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPETITION_ROOT = REPO_ROOT / "competition"
SRC_ROOT = COMPETITION_ROOT / "src"

for path in (str(COMPETITION_ROOT), str(SRC_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

DATA_ROOT = REPO_ROOT / "competition_match" / "data"
OUTPUT_ROOT = REPO_ROOT / "competition_match" / "outputs"

TOKEN_RE = re.compile(r"[A-Za-z0-9]+|[一-鿿]{2,8}")
HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s*(.+?)\s*$")
CITATION_RE = re.compile(r"\[(\d+)\]")
SENTENCE_RE = re.compile(r"(?<=[。！？!?；;])|\n+")
FORBIDDEN_REFERENCE_PATTERNS = [
    re.compile(r"\[\s*\d+\s*\]"),
    re.compile(r"(?:文档|来源)\s*\d+"),
    re.compile(r"(?im)^\s*(?:参考资料|参考文献|引用来源|资料来源|references?)\s*$"),
]
SEARCH_CACHE_SCHEMA_VERSION = 4
FETCH_CACHE_SCHEMA_VERSION = 2
QUERY_PLAN_VERSION = 3

LOW_SIGNAL_HOSTS = {
    "dictionary.cambridge.org",
    "global.bing.com",
    "www.iciba.com",
    "iciba.com",
    "xueshu.baidu.com",
    "easylearn.baidu.com",
    "zhidao.baidu.com",
    "jingyan.baidu.com",
    "baijiahao.baidu.com",
    "wen.baidu.com",
    "www.zhihu.com",
    "zhuanlan.zhihu.com",
    "www.360doc.com",
    "www.doc88.com",
    "max.book118.com",
    "ishare.iask.sina.com.cn",
    "www.sohu.com",
    "www.163.com",
    "www.qq.com",
    "blog.csdn.net",
}
LOW_SIGNAL_PATH_PARTS = (
    "/dict/",
    "/question/",
    "/video/",
    "/download",
    "/thread",
    "/tag/",
    "/topic/",
)
LOW_SIGNAL_TITLE_PARTS = (
    "词典",
    "是什么意思",
    "翻译",
    "dict",
    "dictionary",
    "下载",
    "在线看",
    "百度经验",
    "qq邮箱",
    "招生网",
    "学校简介",
    "联系我们",
    "机构设置",
    "现任领导",
    "虚拟校园",
    "博客",
)
LOW_SIGNAL_SNIPPET_PARTS = (
    "学校简介",
    "联系我们",
    "机构设置",
    "虚拟校园",
    "校园文化",
    "历任领导",
    "现任领导",
    "下载app",
)
HIGH_VALUE_SIGNAL_RE = re.compile(
    r"法|条例|规定|办法|指引|指南|白皮书|判决|法院|委员会|国务院|报告|研究|调查|试验|案例|数据|统计|风险|边界|条件|例外"
)

STOPWORDS = {
    "一个",
    "一些",
    "以及",
    "为了",
    "可以",
    "需要",
    "问题",
    "核心",
    "文章",
    "内容",
    "本文",
    "我们",
    "你们",
    "他们",
    "这个",
    "那个",
    "这些",
    "那些",
    "进行",
    "基于",
    "关于",
    "相关",
    "结果",
    "分析",
    "说明",
    "情况",
    "方法",
    "部分",
    "标题",
    "文本",
    "数据",
    "方案",
    "优化",
}


class ParagraphExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.paragraphs: list[str] = []
        self.current = ""
        self.in_p = False

    def handle_starttag(self, tag, attrs):
        if tag in {"p", "li", "div", "section", "article"}:
            self.in_p = True

    def handle_endtag(self, tag):
        if tag in {"p", "li", "div", "section", "article"}:
            text = normalize_whitespace(self.current)
            if text:
                self.paragraphs.append(text)
            self.current = ""
            self.in_p = False

    def handle_data(self, data):
        if self.in_p:
            self.current += data


def dataset_dir(dataset_id: int) -> Path:
    return DATA_ROOT / str(dataset_id)


def shared_cache_dir() -> Path:
    path = OUTPUT_ROOT / "shared_cache"
    path.mkdir(parents=True, exist_ok=True)
    return path


def local_cache_dir(base_dir: Path) -> Path:
    path = base_dir / "_cache"
    path.mkdir(parents=True, exist_ok=True)
    return path


def read_text(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(path)
    return path.read_text(encoding="utf-8").strip()


def read_optional_text(path: Path) -> str | None:
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8").strip()


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def write_json(path: Path, payload: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_json(path: Path) -> dict | list | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def load_docs(dataset_id: int) -> list[dict[str, object]]:
    base = dataset_dir(dataset_id)
    docs: list[dict[str, object]] = []
    for index in range(1, 6):
        path = base / f"{index}.md"
        docs.append(
            {
                "index": index,
                "path": path,
                "name": path.name,
                "content": read_text(path),
            }
        )
    return docs


def tokenize(text: str) -> list[str]:
    return [token for token in TOKEN_RE.findall(text) if len(token) >= 2 and token not in STOPWORDS]


def extract_keywords(texts: Iterable[str], limit: int = 12) -> list[str]:
    counter: Counter[str] = Counter()
    for text in texts:
        for token in tokenize(text):
            counter[token] += 1
    return [token for token, _ in counter.most_common(limit)]


def keyword_priority(token: str) -> int:
    score = 0
    if len(token) >= 4:
        score += 2
    if re.search(r"法|条例|规定|办法|指引|指南|白皮书|法院|判决|责任|人格|主体|风险|边界|条件|案例|数据|模型|技术|教育|抑郁|基因|收入|人工智能", token):
        score += 4
    if re.search(r"大学|学院|委员会|国务院|联合国|WHO|CRISPR|UBI|AI", token, re.IGNORECASE):
        score += 3
    if token in {"问题", "内容", "情况", "分析", "特征", "这一问题", "视域", "相关"}:
        score -= 6
    return score


def rank_keywords(tokens: Iterable[str], limit: int = 12) -> list[str]:
    counter: Counter[str] = Counter()
    for token in tokens:
        normalized = normalize_whitespace(token)
        if not normalized:
            continue
        counter[normalized] += max(1, keyword_priority(normalized) + 1)
    ranked = sorted(counter.items(), key=lambda item: (item[1], keyword_priority(item[0]), len(item[0])), reverse=True)
    return [token for token, _ in ranked[:limit]]



def build_question_shingles(question: str, size: int = 4, limit: int = 10) -> list[str]:
    compact = re.sub(r"[\s\-—_，。！？?：:；;、“”‘’'\"（）()\[\]【】]", "", question)
    if len(compact) <= size:
        return [compact] if compact else []
    shingles: list[str] = []
    for index in range(0, len(compact) - size + 1):
        shingle = compact[index:index + size]
        if len(shingle) == size:
            shingles.append(shingle)
    return rank_keywords(shingles, limit=limit)



def looks_like_site_nav(text: str) -> bool:
    lowered = text.lower()
    hits = sum(1 for part in LOW_SIGNAL_SNIPPET_PARTS if part in lowered or part in text)
    return hits >= 2



def looks_garbled(text: str) -> bool:
    if not text:
        return False
    noise_chars = sum(1 for char in text if char in "ÃÂÅÆÇÐÑØÙÚÛÜÝÞßàáâãäåæçèéêëìíîïðñòóôõöøùúûüýþÿ¼½¾")
    return noise_chars >= max(12, len(text) // 18)



def split_sentences(text: str) -> list[str]:
    return [part.strip() for part in SENTENCE_RE.split(text) if normalize_whitespace(part)]


def extract_headings(text: str) -> list[str]:
    headings: list[str] = []
    for line in text.splitlines():
        match = HEADING_RE.match(line)
        if match:
            headings.append(match.group(1).strip())
    return headings


def infer_question_from_docs(docs: list[dict[str, object]]) -> str:
    headings: list[str] = []
    for doc in docs:
        headings.extend(extract_headings(str(doc["content"])))
    if headings:
        counts = Counter(headings)
        topic = counts.most_common(1)[0][0]
        return topic if topic.endswith(("?", "？")) else f"{topic}是什么？"

    keywords = extract_keywords((str(doc["content"]) for doc in docs), limit=6)
    if len(keywords) >= 2:
        return f"{keywords[0]}和{keywords[1]}的核心问题是什么？"
    if keywords:
        return f"{keywords[0]}是什么？"
    return "这组文章讨论的核心问题是什么？"


def ensure_question(dataset_id: int) -> tuple[str, Path, bool]:
    base = dataset_dir(dataset_id)
    path = base / "question.md"
    existing = read_optional_text(path)
    if existing:
        return existing, path, False
    docs = load_docs(dataset_id)
    question = infer_question_from_docs(docs)
    write_text(path, question)
    return question, path, True


def parse_question_lines(text: str | None) -> list[str]:
    if not text:
        return []
    lines: list[str] = []
    seen: set[str] = set()
    for raw_line in str(text).splitlines():
        line = re.sub(r"^\s*(?:[-*]|\d+[.)、])\s*", "", raw_line).strip()
        normalized = normalize_whitespace(line)
        if not normalized:
            continue
        normalized = normalized.rstrip("。；;")
        if normalized not in seen:
            seen.add(normalized)
            lines.append(normalized)
    return lines


def load_baseline_answer(dataset_id: int) -> tuple[str, Path]:
    base = dataset_dir(dataset_id)
    path = base / "test_before.md"
    return read_text(path), path


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
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned


def assert_no_reference_markers(text: str) -> None:
    for pattern in FORBIDDEN_REFERENCE_PATTERNS:
        match = pattern.search(text)
        if match:
            raise ValueError(f"forbidden reference marker remains: {match.group(0)!r}")


def doc_blocks(docs: list[dict[str, object]]) -> str:
    blocks: list[str] = []
    for doc in docs:
        index = int(doc["index"])
        content = str(doc["content"])
        path = doc["path"]
        blocks.append(
            f"[文档{index}]\n"
            f"文件: {path.name}\n"
            f"内容:\n{content}"
        )
    return "\n\n".join(blocks)


def source_summary(docs: list[dict[str, object]]) -> str:
    keywords = extract_keywords((str(doc["content"]) for doc in docs), limit=10)
    if not keywords:
        return ""
    return "、".join(keywords)


def build_heuristic_article(
    question: str,
    target_doc: dict[str, object],
    other_docs: list[dict[str, object]],
    baseline_answer: str,
) -> str:
    target_content = str(target_doc["content"])
    target_headings = extract_headings(target_content)
    title = target_headings[0] if target_headings else question.rstrip("？?")
    if not title:
        title = f"第{target_doc['index']}篇文章优化稿"

    target_sentences = split_sentences(target_content)
    baseline_sentences = split_sentences(baseline_answer)
    shared_keywords = extract_keywords((str(doc["content"]) for doc in [target_doc, *other_docs]), limit=8)
    shared_line = "、".join(shared_keywords[:5]) if shared_keywords else ""

    lead = target_sentences[0] if target_sentences else target_content[:140]
    support = target_sentences[1:4] if len(target_sentences) > 1 else []
    baseline_hint = baseline_sentences[0] if baseline_sentences else ""

    lines = [f"# {title}", "", "## 核心表述", lead]
    if baseline_hint:
        lines.extend(["", "## 初始引用线索", baseline_hint])
    if shared_line:
        lines.extend(["", "## 共同信息", f"本文围绕 {shared_line} 展开，并尽量把与其他文章一致的关键点写得更清楚。"])
    if support:
        lines.extend(["", "## 细化补充"])
        for sentence in support:
            lines.append(f"- {sentence}")
    lines.extend([
        "",
        "## 结论",
        f"{question.rstrip('？?')}相关的核心内容在本文中已经尽量前置，便于后续生成答案时优先引用。",
    ])
    return "\n".join(line for line in lines if line is not None).strip() + "\n"


def search_cache_file(query: str) -> Path:
    digest = hashlib.sha1(query.encode("utf-8")).hexdigest()[:16]
    return shared_cache_dir() / f"search_{digest}.json"


def fetch_cache_file(url: str) -> Path:
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]
    return shared_cache_dir() / f"fetch_{digest}.json"


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

    if host in LOW_SIGNAL_HOSTS:
        if host != "global.bing.com" or path.startswith("/dict/"):
            return True
    if any(part in path for part in LOW_SIGNAL_PATH_PARTS):
        return True
    return any(part in lowered_title for part in LOW_SIGNAL_TITLE_PARTS)


def _normalize_search_result(raw: dict) -> dict | None:
    url = str(raw.get("url", "")).strip()
    if not url.startswith("http"):
        return None
    title = str(raw.get("title", "")).strip()
    if _is_low_signal_result(url, title):
        return None
    snippet = str(raw.get("content") or raw.get("snippet") or "").strip()[:300]
    if looks_like_site_nav(f"{title} {snippet}"):
        return None
    domain = (urlparse(url).hostname or "").lower()
    return {"title": title, "url": url, "snippet": snippet, "domain": domain}


def domain_quality_score(domain: str) -> int:
    score = 0
    if domain.endswith(".gov.cn"):
        score += 6
    if domain.endswith(".edu.cn") or domain.endswith(".edu"):
        score += 5
    if any(part in domain for part in ("court", "gov", "cass", "pku", "tsinghua", "who", "nature", "pubmed", "arxiv", "ieee")):
        score += 4
    if any(part in domain for part in ("news", "people", "xinhuanet", "caixin", "paper", "thepaper")):
        score += 2
    if any(part in domain for part in ("zhidao", "baijiahao", "doc88", "book118", "zhihu", "qq.com", "163.com", "sohu.com")):
        score -= 6
    return score


def assign_result_slot(query_spec: dict[str, str], row: dict[str, str]) -> str:
    text = normalize_whitespace(f"{row.get('title', '')} {row.get('snippet', '')}")
    if re.search(r"条件|边界|例外|前提|范围|仅限", text):
        return "boundary"
    if re.search(r"案例|数据|调查|研究|统计|样本", text):
        return "case_data"
    if re.search(r"指南|白皮书|报告|判决|法院|委员会|国务院", text):
        return "authority"
    if re.search(r"风险|责任|后果|损害", text):
        return "risk"
    return query_spec["slot"]


def score_search_result(question: str, row: dict[str, str], query_spec: dict[str, str], anchors: list[str]) -> tuple[int, str]:
    title = str(row.get("title", ""))
    snippet = str(row.get("snippet", ""))
    domain = str(row.get("domain", ""))
    text = normalize_whitespace(f"{title} {snippet}")
    score = domain_quality_score(domain)
    reason_parts: list[str] = []

    question_text = str(query_spec.get("question") or question)
    question_tokens = tokenize(question_text)
    overlap = [token for token in question_tokens if token in text]
    score += min(6, len(overlap) * 2)
    if overlap:
        reason_parts.append("命中题目核心词")

    question_shingles = build_question_shingles(question_text, size=4, limit=10)
    shingle_hits = [shingle for shingle in question_shingles if shingle and shingle in text][:4]
    score += min(8, len(shingle_hits) * 2)
    if shingle_hits:
        reason_parts.append("命中题目短语")

    anchor_hits = [anchor for anchor in anchors if anchor in text][:4]
    score += min(8, len(anchor_hits) * 2)
    if anchor_hits:
        reason_parts.append("命中材料锚点")

    if not overlap and not shingle_hits and not anchor_hits:
        score -= 10
        reason_parts.append("题目相关性弱")

    if HIGH_VALUE_SIGNAL_RE.search(text):
        score += 4
        reason_parts.append("包含高价值证据信号")

    if query_spec["slot"] in {"boundary", "risk"} and re.search(r"条件|边界|例外|前提|风险|责任|后果", text):
        score += 3
        reason_parts.append("贴合边界或风险槽位")
    if query_spec["slot"] in {"authority", "authority_or_case"} and re.search(r"指南|白皮书|报告|判决|法院|委员会|国务院", text):
        score += 4
        reason_parts.append("贴合权威槽位")
    if query_spec["slot"] == "case_data" and re.search(r"案例|数据|调查|研究|统计|样本", text):
        score += 4
        reason_parts.append("贴合案例数据槽位")

    if len(text) < 24:
        score -= 3
    if looks_like_site_nav(text):
        score -= 8
        reason_parts.append("疑似站点导航页")
    if not reason_parts:
        reason_parts.append("仅弱匹配题目")
    return score, "；".join(reason_parts)


def infer_query_slots(question: str, *, role: str) -> list[dict[str, str]]:
    primary_slots = [
        {"slot": "direct", "suffix": "", "reason": "直接回答题目"},
        {"slot": "direct", "suffix": "定义 争议", "reason": "补直接定义与核心争议"},
        {"slot": "boundary", "suffix": "条件 边界 例外", "reason": "补条件与边界"},
        {"slot": "authority", "suffix": "指南 白皮书 报告 判决", "reason": "补权威依据"},
        {"slot": "case_data", "suffix": "案例 数据 调查 研究", "reason": "补案例与数据"},
        {"slot": "risk", "suffix": "风险 责任 后果", "reason": "补风险与制度后果"},
    ]
    branch_slots = [
        {"slot": "direct", "suffix": "", "reason": "从分支问题补直接答案"},
        {"slot": "boundary", "suffix": "条件 边界 例外", "reason": "从分支问题补边界"},
        {"slot": "authority", "suffix": "指南 报告 判决", "reason": "从分支问题补权威依据"},
    ]
    return primary_slots if role == "primary" else branch_slots



def extract_search_anchor_terms(question: str, docs: list[dict[str, object]], limit: int = 10) -> list[str]:
    heading_tokens: list[str] = []
    strong_sentence_tokens: list[str] = []
    for doc in docs:
        heading_tokens.extend(tokenize(" ".join(extract_headings(str(doc["content"])))) )
        for sentence in extract_ranked_sentences(str(doc["content"]), limit=6):
            strong_sentence_tokens.extend(tokenize(sentence))
    question_tokens = tokenize(question)
    shared_tokens = extract_keywords((str(doc["content"]) for doc in docs), limit=16)
    ranked = rank_keywords([*question_tokens, *heading_tokens, *strong_sentence_tokens, *shared_tokens], limit=limit)
    return [token for token in ranked if keyword_priority(token) > 0][:limit]



def coerce_question_list(question_or_questions: str | Iterable[str]) -> list[str]:
    if isinstance(question_or_questions, str):
        questions = parse_question_lines(question_or_questions)
    else:
        questions = []
        for item in question_or_questions:
            questions.extend(parse_question_lines(str(item)))
    deduped: list[str] = []
    seen: set[str] = set()
    for question in questions:
        normalized = normalize_whitespace(question)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped



def build_search_queries(question_or_questions: str | Iterable[str], docs: list[dict[str, object]], limit: int = 15) -> list[dict[str, str]]:
    questions = coerce_question_list(question_or_questions)
    primary_question = questions[0] if questions else ""
    anchors = extract_search_anchor_terms(primary_question, docs, limit=10) if primary_question else []
    query_specs: list[dict[str, str]] = []

    for question_index, question_text in enumerate(questions[:4]):
        role = "primary" if question_index == 0 else "branch"
        for slot_spec in infer_query_slots(question_text, role=role):
            query = normalize_whitespace(f"{question_text} {slot_spec['suffix']}")
            query_specs.append(
                {
                    "query": query,
                    "question": question_text,
                    "question_role": role,
                    "slot": slot_spec["slot"],
                    "query_type": "direct" if slot_spec["slot"] == "direct" else "gap_filling",
                    "reason": slot_spec["reason"],
                }
            )

    if primary_question and len(anchors) >= 2:
        query_specs.append(
            {
                "query": normalize_whitespace(f"{primary_question} {anchors[0]} {anchors[1]}"),
                "question": primary_question,
                "question_role": "primary",
                "slot": "anchored_core",
                "query_type": "anchored",
                "reason": "用最强锚点压实题目核心对象与术语",
            }
        )
    if primary_question and len(anchors) >= 4:
        query_specs.append(
            {
                "query": normalize_whitespace(f"{primary_question} {anchors[2]} {anchors[3]}"),
                "question": primary_question,
                "question_role": "primary",
                "slot": "anchored_support",
                "query_type": "anchored",
                "reason": "补第二组锚点，提升召回多样性",
            }
        )
    if primary_question and anchors:
        query_specs.extend(
            [
                {
                    "query": normalize_whitespace(f"{primary_question} {anchors[0]} 研究 报告"),
                    "question": primary_question,
                    "question_role": "primary",
                    "slot": "authority_or_case",
                    "query_type": "authority_or_case",
                    "reason": "围绕第一锚点补权威研究或报告",
                },
                {
                    "query": normalize_whitespace(f"{primary_question} {anchors[0]} 风险 责任 后果"),
                    "question": primary_question,
                    "question_role": "primary",
                    "slot": "risk",
                    "query_type": "anchored",
                    "reason": "围绕核心锚点补风险和责任后果",
                },
                {
                    "query": normalize_whitespace(f"{primary_question} {anchors[0]} 案例 判决"),
                    "question": primary_question,
                    "question_role": "primary",
                    "slot": "case_data",
                    "query_type": "anchored",
                    "reason": "围绕核心锚点补案例与裁判材料",
                },
            ]
        )

    deduped: list[dict[str, str]] = []
    seen: set[str] = set()
    for spec in query_specs:
        query = spec["query"]
        if not query or query in seen:
            continue
        seen.add(query)
        deduped.append(spec)
        if len(deduped) >= limit:
            break
    return deduped



def search_web(query: str, num_results: int = 8) -> list[dict]:
    try:
        import requests
    except ImportError:
        return []

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
            response = session.get(f"{base_url}/search", params=params, timeout=_searxng_timeout())
            response.raise_for_status()
            payload = response.json()
    except Exception:
        return []

    results = payload.get("results")
    if not isinstance(results, list):
        return []

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
    try:
        import requests
    except ImportError:
        return ""

    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
        response.raise_for_status()
    except Exception:
        return ""

    try:
        import trafilatura

        text = trafilatura.extract(response.text, include_comments=False, include_tables=True)
        if text and len(text) > 200:
            return text[:8000]
    except ImportError:
        pass
    except Exception:
        pass

    parser = ParagraphExtractor()
    parser.feed(response.text)
    content = "\n\n".join(parser.paragraphs)
    return content[:8000]


def extract_highlight_sentences(content: str, question: str, anchors: list[str], limit: int = 4) -> list[str]:
    ranked: list[tuple[int, int, str]] = []
    question_tokens = tokenize(question)
    for index, sentence in enumerate(extract_ranked_sentences(content, limit=20)):
        score = sentence_strength(sentence)
        text = normalize_whitespace(sentence)
        score += sum(2 for token in question_tokens if token in text)
        score += sum(2 for anchor in anchors[:6] if anchor in text)
        if HIGH_VALUE_SIGNAL_RE.search(text):
            score += 3
        ranked.append((score, -index, sentence))
    ranked.sort(reverse=True)
    return [sentence for _, _, sentence in ranked[:limit]]


def gather_search_payload(
    question: str,
    docs: list[dict[str, object]],
    *,
    question_variants: list[str] | None = None,
    query_specs: list[dict[str, str]] | None = None,
    result_cleaner: Callable[[str, list[str], list[dict]], list[dict[str, str]]] | None = None,
    content_cleaner: Callable[[str, str, str], str] | None = None,
    refresh_cache: bool = False,
) -> dict:
    questions = coerce_question_list(question_variants or [question]) or [normalize_whitespace(question)]
    primary_question = questions[0]
    query_specs = query_specs or build_search_queries(questions, docs, limit=15)
    anchors = extract_search_anchor_terms(primary_question, docs, limit=10)
    merged_results: dict[str, dict] = {}
    search_cache_hits = 0
    search_cache_misses = 0
    filtered_out = 0

    for query_spec in query_specs:
        query = query_spec["query"]
        cache_path = search_cache_file(query)
        cached = load_json(cache_path)
        cache_ok = (
            isinstance(cached, dict)
            and cached.get("cache_schema_version") == SEARCH_CACHE_SCHEMA_VERSION
            and cached.get("query") == query
            and isinstance(cached.get("results"), list)
        )
        if cache_ok and not refresh_cache:
            rows = cached.get("results", [])
            search_cache_hits += 1
        else:
            rows = search_web(query, num_results=12)
            write_json(
                cache_path,
                {
                    "cache_schema_version": SEARCH_CACHE_SCHEMA_VERSION,
                    "query_plan_version": QUERY_PLAN_VERSION,
                    "query": query,
                    "query_spec": query_spec,
                    "results": rows,
                    "saved_at": timestamp(),
                },
            )
            search_cache_misses += 1
            time.sleep(1)

        if not rows:
            continue
        for row in rows:
            url = str(row.get("url", "")).strip()
            if not url:
                filtered_out += 1
                continue
            slot = assign_result_slot(query_spec, row)
            score, reason = score_search_result(primary_question, row, query_spec, anchors)
            if score < 4:
                filtered_out += 1
                continue
            existing = merged_results.get(url)
            if existing is None:
                merged_results[url] = {
                    **row,
                    "score": score,
                    "slots": [slot],
                    "matched_queries": [query],
                    "matched_questions": [str(query_spec.get("question", primary_question))],
                    "reasons": [reason],
                }
                continue
            existing["score"] = max(int(existing.get("score", 0)), score)
            if slot not in existing["slots"]:
                existing["slots"].append(slot)
            if query not in existing["matched_queries"]:
                existing["matched_queries"].append(query)
            matched_question = str(query_spec.get("question", primary_question))
            if matched_question not in existing["matched_questions"]:
                existing["matched_questions"].append(matched_question)
            if reason not in existing["reasons"]:
                existing["reasons"].append(reason)

    ranked_results = sorted(
        merged_results.values(),
        key=lambda row: (int(row.get("score", 0)), domain_quality_score(str(row.get("domain", ""))), len(str(row.get("snippet", "")))),
        reverse=True,
    )

    selected_results: list[dict] = []
    cleaned_candidates: list[dict[str, str]] | None = None
    if result_cleaner:
        try:
            cleaned_candidates = result_cleaner(primary_question, questions, ranked_results[:20])
        except Exception:
            cleaned_candidates = None
    if cleaned_candidates is not None:
        ranked_by_url = {str(row.get("url", "")): row for row in ranked_results}
        for cleaned in cleaned_candidates[:8]:
            url = str(cleaned.get("url", "")).strip()
            row = ranked_by_url.get(url)
            if row is None:
                continue
            clean_slot = str(cleaned.get("slot", "")).strip()
            if clean_slot and clean_slot not in row.get("slots", []):
                row["slots"] = [clean_slot, *row.get("slots", [])]
            clean_reason = str(cleaned.get("reason", "")).strip()
            if clean_reason:
                row.setdefault("clean_reasons", []).append(clean_reason)
            selected_results.append(row)
    else:
        slot_quota = {
            "direct": 3,
            "boundary": 2,
            "authority": 2,
            "case_data": 2,
            "risk": 2,
            "anchored_core": 1,
            "anchored_support": 1,
            "authority_or_case": 2,
        }
        slot_counts: Counter[str] = Counter()
        domain_counts: Counter[str] = Counter()
        for row in ranked_results:
            domain = str(row.get("domain", ""))
            primary_slot = str((row.get("slots") or ["direct"])[0])
            if domain and domain_counts[domain] >= 2:
                continue
            if slot_counts[primary_slot] >= slot_quota.get(primary_slot, 1):
                continue
            selected_results.append(row)
            domain_counts[domain] += 1
            slot_counts[primary_slot] += 1
            if len(selected_results) >= 10:
                break
        if len(selected_results) < 6:
            for row in ranked_results:
                if row in selected_results:
                    continue
                selected_results.append(row)
                if len(selected_results) >= 8:
                    break

    fetched_contents: list[dict] = []
    fetch_cache_hits = 0
    fetch_cache_misses = 0
    for row in selected_results[:8]:
        url = str(row.get("url", "")).strip()
        if not url:
            continue
        cache_path = fetch_cache_file(url)
        cached = load_json(cache_path)
        cache_ok = (
            isinstance(cached, dict)
            and cached.get("cache_schema_version") == FETCH_CACHE_SCHEMA_VERSION
            and cached.get("url") == url
            and isinstance(cached.get("cleaned_content"), str)
        )
        if cache_ok and not refresh_cache:
            content = str(cached.get("cleaned_content", ""))
            fetch_cache_hits += 1
        else:
            raw_content = fetch_url(url)
            content = raw_content
            if content_cleaner and len(raw_content) >= 200:
                try:
                    content = content_cleaner(url, str(row.get("title", "")), raw_content)
                except Exception:
                    content = raw_content
            write_json(
                cache_path,
                {
                    "cache_schema_version": FETCH_CACHE_SCHEMA_VERSION,
                    "url": url,
                    "title": row.get("title", ""),
                    "raw_content": raw_content,
                    "cleaned_content": content,
                    "saved_at": timestamp(),
                },
            )
            fetch_cache_misses += 1
            time.sleep(1)
        if len(content) < 200 or looks_garbled(content):
            continue
        fetched_contents.append(
            {
                "url": url,
                "title": row.get("title", ""),
                "slot": (row.get("slots") or ["direct"])[0],
                "score": row.get("score", 0),
                "reason": "；".join([*row.get("clean_reasons", [])[:1], *row.get("reasons", [])[:2]]),
                "matched_questions": row.get("matched_questions", []),
                "highlights": extract_highlight_sentences(content, primary_question, anchors, limit=4),
                "content": content,
            }
        )

    return {
        "query_plan_version": QUERY_PLAN_VERSION,
        "question": primary_question,
        "questions": questions,
        "query_plan": query_specs,
        "anchors": anchors,
        "search_results": selected_results,
        "all_ranked_results": ranked_results[:20],
        "fetched_contents": fetched_contents,
        "cache_stats": {
            "search_hits": search_cache_hits,
            "search_misses": search_cache_misses,
            "fetch_hits": fetch_cache_hits,
            "fetch_misses": fetch_cache_misses,
            "filtered_out": filtered_out,
            "queries": len(query_specs),
            "selected_results": len(selected_results),
            "fetched_results": len(fetched_contents),
            "unique_domains": len({str(row.get('domain', '')) for row in selected_results if row.get('domain')}),
        },
    }


def sentence_strength(sentence: str) -> int:
    score = 0
    text = normalize_whitespace(sentence)
    if len(text) < 14:
        return -1
    if len(text) <= 80:
        score += 2
    if re.search(r"\d", text):
        score += 2
    if re.search(r"法|条例|标准|指南|白皮书|会议|法院|研究|报告|数据|调查|试验", text):
        score += 2
    if re.search(r"不应|不能|必须|应当|意味着|关键在于|并不等于|而不是|尤其", text):
        score += 3
    if re.search(r"公司|大学|学院|委员会|国务院|民法典|联合国|世卫|WHO|CRISPR|AI|UBI", text, re.IGNORECASE):
        score += 2
    if len(text) > 110:
        score -= 2
    return score


def extract_ranked_sentences(text: str, limit: int = 8) -> list[str]:
    ranked: list[tuple[int, int, str]] = []
    seen: set[str] = set()
    for index, sentence in enumerate(split_sentences(text)):
        normalized = normalize_whitespace(sentence)
        if normalized in seen:
            continue
        seen.add(normalized)
        score = sentence_strength(normalized)
        if score < 0:
            continue
        ranked.append((score, -index, normalized))
    ranked.sort(reverse=True)
    return [sentence for _, _, sentence in ranked[:limit]]


def build_evidence_inventory(docs: list[dict[str, object]], baseline_answer: str) -> dict:
    per_doc: list[dict[str, object]] = []
    for doc in docs:
        per_doc.append(
            {
                "index": int(doc["index"]),
                "name": str(doc["name"]),
                "sentences": extract_ranked_sentences(str(doc["content"]), limit=8),
            }
        )
    baseline_sentences = extract_ranked_sentences(baseline_answer, limit=10)
    return {
        "per_doc": per_doc,
        "baseline_sentences": baseline_sentences,
        "shared_keywords": extract_keywords((str(doc["content"]) for doc in docs), limit=12),
    }


def render_evidence_inventory(inventory: dict) -> str:
    lines: list[str] = []
    shared_keywords = inventory.get("shared_keywords") or []
    if shared_keywords:
        lines.extend(["## 共享主题词", "、".join(shared_keywords), ""])
    baseline_sentences = inventory.get("baseline_sentences") or []
    if baseline_sentences:
        lines.extend(["## 基线引用里的强句", *[f"- {sentence}" for sentence in baseline_sentences], ""])
    for row in inventory.get("per_doc", []):
        lines.append(f"## 文档{row['index']} 强证据句")
        for sentence in row.get("sentences", []):
            lines.append(f"- {sentence}")
        lines.append("")
    return "\n".join(lines).strip()


def render_search_context(search_payload: dict) -> str:
    lines: list[str] = []
    questions = search_payload.get("questions") or []
    query_plan = search_payload.get("query_plan") or []
    search_results = search_payload.get("search_results") or []
    fetched_rows = search_payload.get("fetched_contents") or []
    fetched_by_url = {str(row.get("url", "")): row for row in fetched_rows}
    cache_stats = search_payload.get("cache_stats") or {}

    if questions:
        lines.extend(["## 搜索问题组", *[f"- {question}" for question in questions], ""])

    if cache_stats:
        lines.extend(
            [
                "## 检索概况",
                f"- query 数: {cache_stats.get('queries', 0)}",
                f"- 入选结果数: {cache_stats.get('selected_results', 0)}",
                f"- 抓取成功数: {cache_stats.get('fetched_results', 0)}",
                f"- 唯一域名数: {cache_stats.get('unique_domains', 0)}",
                f"- 被过滤结果数: {cache_stats.get('filtered_out', 0)}",
                "",
            ]
        )

    if query_plan:
        lines.append("## 搜索意图")
        for spec in query_plan[:15]:
            lines.append(
                f"- [{spec.get('slot', 'direct')}] {spec.get('query', '')} | 原因: {spec.get('reason', '')}"
            )
        lines.append("")

    slot_titles = {
        "direct": "## 高价值直接证据",
        "anchored_core": "## 高价值直接证据",
        "anchored_support": "## 高价值直接证据",
        "boundary": "## 条件与边界证据",
        "risk": "## 条件与边界证据",
        "authority": "## 权威依据与案例数据",
        "authority_or_case": "## 权威依据与案例数据",
        "case_data": "## 权威依据与案例数据",
    }
    grouped: dict[str, list[dict]] = {
        "## 高价值直接证据": [],
        "## 条件与边界证据": [],
        "## 权威依据与案例数据": [],
    }
    for row in search_results[:8]:
        slots = row.get("slots") or ["direct"]
        primary_slot = str(slots[0])
        section = slot_titles.get(primary_slot, "## 高价值直接证据")
        grouped[section].append(row)

    for section_title, rows in grouped.items():
        if not rows:
            continue
        lines.append(section_title)
        for row in rows:
            url = str(row.get("url", ""))
            fetched = fetched_by_url.get(url, {})
            highlights = fetched.get("highlights") or []
            snippet = normalize_whitespace(str(row.get("snippet", "")))
            evidence_excerpt = " / ".join(highlights[:2]) if highlights else snippet[:220]
            why_keep = "；".join(row.get("reasons", [])[:2]) or str(fetched.get("reason", ""))
            matched_questions = row.get("matched_questions") or []
            lines.append(f"- 标题: {row.get('title', '')}")
            lines.append(f"  URL: {url}")
            lines.append(f"  命中问题: {'；'.join(matched_questions[:2]) if matched_questions else search_payload.get('question', '')}")
            lines.append(f"  命中槽位: {'、'.join(row.get('slots', []))}")
            lines.append(f"  保留理由: {why_keep}")
            lines.append(f"  可用摘句: {evidence_excerpt}")
        lines.append("")

    return "\n".join(lines).strip()


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()
