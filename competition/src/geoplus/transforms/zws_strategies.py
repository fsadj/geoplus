#!/usr/bin/env python3
"""
ZWS injection strategies for GEO+.
Strategy: LLM semantic analysis -> identify citation-worthy sentences -> inject ZWS only there.
"""
import json
import re
import sys

from geoplus.anthropic_client import call_model
from geoplus.paths import dataset_file

ZWS = '​'

CITABLE_PROMPT = """找出以下文本中所有包含"可引用特征"的句子，返回JSON。

可引用特征（满足任一）：
- 含数字：百分比/样本量(N=)/效应量(g/d/r)/统计值(p<,t=)/具体数值/年份
- 含来源：机构名/研究项目/学者名+年份/et al/报告名
- 含主张："发现"/"显示"/"表明"/"证明"/"值得注意的是"/"核心"/"结论"/"关键"

返回纯JSON，不要其他文字：{{"citable":["原句1","原句2"]}}
如果没有，返回：{{"citable":[]}}

文本：
{chunk}"""


def call_llm(prompt, timeout=120):
    """Call the Anthropic-compatible model API for sentence identification."""
    try:
        return call_model(
            [{"role": "user", "content": prompt}],
            max_tokens=4096,
            timeout=timeout,
        )
    except Exception as e:
        print(f"  [API error] {e}", file=sys.stderr)
        return ""


def parse_json_response(response):
    """Extract citable sentences from LLM response. Returns list or None."""
    if not response:
        return None
    # Strip markdown code fences if present
    cleaned = re.sub(r'^```(?:json)?\s*', '', response.strip())
    cleaned = re.sub(r'\s*```$', '', cleaned)
    try:
        return json.loads(cleaned).get("citable", [])
    except json.JSONDecodeError:
        pass
    # Try regex extraction
    json_match = re.search(r'\{"citable"\s*:\s*\[.*?\]\}', response, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(0)).get("citable", [])
        except json.JSONDecodeError:
            pass
    return None


def split_into_chunks(text, max_chars=5000):
    """Split document into chunks at paragraph boundaries."""
    paragraphs = text.split('\n\n')
    chunks = []
    current = ""
    for para in paragraphs:
        if len(current) + len(para) + 2 <= max_chars:
            current = (current + '\n\n' + para) if current else para
        else:
            if current:
                chunks.append(current)
            current = para
    if current:
        chunks.append(current)
    return chunks


def identify_citable_sentences(text, verbose=True):
    """
    Use the configured model to identify citation-worthy sentences.
    Returns a list of exact sentence strings that should get ZWS injection.
    """
    chunks = split_into_chunks(text)
    all_citable = []

    for i, chunk in enumerate(chunks):
        if verbose:
            print(f"  [{i+1}/{len(chunks)}] Chunk {len(chunk)} chars...", end=" ", flush=True)

        prompt = CITABLE_PROMPT.format(chunk=chunk)
        response = call_llm(prompt)
        found = parse_json_response(response)

        if found is not None:
            if verbose:
                print(f"{len(found)} sentences")
            all_citable.extend(found)
        else:
            if verbose:
                snippet = response[:100].replace('\n', ' ') if response else "(empty)"
                print(f"parse fail: {snippet}")

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for s in all_citable:
        cleaned = s.strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            unique.append(cleaned)

    if verbose:
        print(f"  Total: {len(unique)} unique citable sentences")
    return unique


def inject_zws_salient(text, citable_sentences):
    """
    Inject ZWS between non-whitespace chars ONLY in citable sentences.
    Non-citable text is left untouched.
    """
    if not citable_sentences:
        return text

    citable_set = set(s.strip() for s in citable_sentences if s.strip())

    result = []
    lines = text.split('\n')
    for line in lines:
        if not line.strip():
            result.append(line)
            continue

        stripped = line.strip()
        if re.match(r'^#{1,4}\s', stripped):
            result.append(line)
            continue
        if re.match(r'^[-|]+$', stripped) or re.match(r'^[QA]\d+[：:]', stripped):
            result.append(line)
            continue

        if stripped in citable_set:
            result.append(inject_zero_width_all_chars(line))
            continue

        # Split into sub-sentences for fine-grained matching
        sub_sentences = re.split(r'(?<=[。！？])(?=\S)', line)
        has_match = any(s.strip() in citable_set for s in sub_sentences)
        if has_match:
            processed = []
            for sub in sub_sentences:
                if sub.strip() in citable_set:
                    processed.append(inject_zero_width_all_chars(sub))
                else:
                    processed.append(sub)
            result.append(''.join(processed))
        else:
            result.append(line)

    return '\n'.join(result)


def inject_zero_width_all_chars(text: str) -> str:
    """Inject ZWS between all non-whitespace character pairs."""
    if not text:
        return text
    result = ''
    for i in range(len(text)):
        result += text[i]
        if i < len(text) - 1:
            if not text[i].isspace() and not text[i + 1].isspace():
                result += ZWS
    return result


def build_salient_document(nozws_text, verbose=True):
    """Full pipeline: identify → inject → return result + stats."""
    if verbose:
        print(f"  Document: {len(nozws_text)} chars, ~{len(split_into_chunks(nozws_text))} chunks to analyze")

    citable = identify_citable_sentences(nozws_text, verbose=verbose)

    if verbose:
        print(f"  Injecting ZWS into {len(citable)} sentences...", end=" ")
    result = inject_zws_salient(nozws_text, citable)

    zwsp_count = result.count(ZWS)
    total_chars = len(result)
    density = (zwsp_count / total_chars * 100) if total_chars > 0 else 0
    if verbose:
        print(f"ZWS: {zwsp_count}/{total_chars} ({density:.1f}%)")

    return result, len(citable), density


if __name__ == "__main__":
    text = dataset_file(1, "after_nozws.md").read_text(encoding="utf-8")
    result, num_citable, density = build_salient_document(text)
    out_path = dataset_file(1, "after_salient.md")
    out_path.write_text(result, encoding="utf-8")
    print(f"\nDS1 done: {num_citable} sentences, {density:.1f}% density -> {out_path}")
