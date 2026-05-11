import re
from collections import defaultdict
from pathlib import Path

REF_PATTERN = re.compile(r"\[([^\]]+)\]")


def build_valid_ref_pattern(*names: str) -> re.Pattern[str]:
    escaped = "|".join(re.escape(name) for name in names)
    return re.compile(rf"^\d+\.md$|^(?:{escaped})$")


def count_references(file_path: Path, valid_ref_pattern: re.Pattern[str]) -> dict | None:
    if not file_path.exists():
        return None

    content = file_path.read_text(encoding="utf-8")
    if "[评审备注]" in content:
        main_content = content.split("[评审备注]", 1)[0].strip()
    else:
        main_content = content.strip()

    matches = [
        match
        for match in REF_PATTERN.finditer(main_content)
        if valid_ref_pattern.match(match.group(1).strip())
    ]
    total_ref = len(matches)
    if total_ref == 0:
        return {
            "file": file_path.name,
            "total_ref": 0,
            "total_words": 0,
            "ref_count": {},
            "ref_ratio": {},
            "ref_words": {},
            "ref_word_ratio": {},
        }

    ref_count = defaultdict(int)
    for match in matches:
        ref_count[match.group(1)] += 1

    ref_ratio = {name: count / total_ref * 100 for name, count in ref_count.items()}

    ref_words = defaultdict(int)
    total_words = 0
    index = 0
    while index < len(matches):
        group_start = index
        group_end = matches[index].end()
        next_index = index + 1
        while next_index < len(matches):
            between = main_content[matches[next_index - 1].end():matches[next_index].start()]
            if between.strip():
                break
            group_end = matches[next_index].end()
            next_index += 1

        if next_index < len(matches):
            text_block = main_content[group_end:matches[next_index].start()]
        else:
            text_block = main_content[group_end:]

        word_count = len(text_block.strip())
        for group_index in range(group_start, next_index):
            ref_words[matches[group_index].group(1)] += word_count
        total_words += word_count
        index = next_index

    ref_word_ratio = {
        name: word_count / total_words * 100 for name, word_count in ref_words.items()
    } if total_words > 0 else {}

    return {
        "file": file_path.name,
        "total_ref": total_ref,
        "total_words": total_words,
        "ref_count": dict(ref_count),
        "ref_ratio": ref_ratio,
        "ref_words": dict(ref_words),
        "ref_word_ratio": ref_word_ratio,
    }


def get_target_ratios(stats: dict | None, target_name: str) -> tuple[float, float]:
    if not stats or stats["total_ref"] == 0:
        return 0.0, 0.0
    return stats["ref_ratio"].get(target_name, 0.0), stats["ref_word_ratio"].get(target_name, 0.0)
