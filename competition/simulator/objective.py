from __future__ import annotations

import math
import re
from dataclasses import dataclass, replace

from .schemas import ObjectiveScore


REF_PATTERN = re.compile(r"\[(\d+)\]")
SENTENCE_SPLIT = re.compile(r"(?<=[。！？!?])|\n+")
PUNCT_SENTENCE_SPLIT = re.compile(r"(?<=[。！？!?])")
WHITESPACE_RE = re.compile(r"\s+")
TEXT_CHAR_RE = re.compile(r"[A-Za-z0-9一-鿿]")


@dataclass(frozen=True)
class ObjectiveProfile:
    name: str = "default"
    sentence_split_mode: str = "punct_or_newline"
    ref_dedup_mode: str = "unique"
    credit_allocation_mode: str = "unique_refs"
    position_credit_mode: str = "share"
    position_decay_alpha: float = 1.0
    weighted_visibility_denominator_mode: str = "total_chars"
    char_count_mode: str = "all"


LEGACY_OBJECTIVE_PROFILE = ObjectiveProfile(name="legacy")
CONTEST_CALIBRATED_V1_PROFILE = replace(
    LEGACY_OBJECTIVE_PROFILE,
    name="contest_calibrated_v1",
    weighted_visibility_denominator_mode="total_weighted_chars",
)
DEFAULT_OBJECTIVE_PROFILE = CONTEST_CALIBRATED_V1_PROFILE
OBJECTIVE_PROFILES = {
    profile.name: profile
    for profile in (
        DEFAULT_OBJECTIVE_PROFILE,
        LEGACY_OBJECTIVE_PROFILE,
        CONTEST_CALIBRATED_V1_PROFILE,
    )
}


def get_objective_profile(name: str) -> ObjectiveProfile:
    try:
        return OBJECTIVE_PROFILES[name]
    except KeyError as exc:
        raise ValueError(f"Unsupported objective profile: {name}") from exc


def _unique_ints(values: list[int]) -> list[int]:
    seen = set()
    result = []
    for number in values:
        if number not in seen:
            seen.add(number)
            result.append(number)
    return result


def _collapse_consecutive(values: list[int]) -> list[int]:
    if not values:
        return []
    result = [values[0]]
    for value in values[1:]:
        if value != result[-1]:
            result.append(value)
    return result


def _split_segments(answer_text: str, profile: ObjectiveProfile) -> list[str]:
    if profile.sentence_split_mode == "punct_or_newline":
        segments = SENTENCE_SPLIT.split(answer_text)
    elif profile.sentence_split_mode == "punct":
        segments = PUNCT_SENTENCE_SPLIT.split(answer_text)
    elif profile.sentence_split_mode == "paragraph":
        segments = re.split(r"\n\s*\n+", answer_text)
    else:
        raise ValueError(f"Unsupported sentence_split_mode: {profile.sentence_split_mode}")
    return [segment.strip() for segment in segments if segment.strip()]


def _extract_refs(segment: str, profile: ObjectiveProfile) -> list[int]:
    refs = [int(value) for value in REF_PATTERN.findall(segment)]
    if profile.ref_dedup_mode == "unique":
        return _unique_ints(refs)
    if profile.ref_dedup_mode == "raw":
        return refs
    if profile.ref_dedup_mode == "collapse_consecutive":
        return _collapse_consecutive(refs)
    raise ValueError(f"Unsupported ref_dedup_mode: {profile.ref_dedup_mode}")


def _content_length(text: str, profile: ObjectiveProfile) -> float:
    if profile.char_count_mode == "all":
        return float(len(text))
    if profile.char_count_mode == "strip_whitespace":
        return float(len(WHITESPACE_RE.sub("", text)))
    if profile.char_count_mode == "text_only":
        return float(len(TEXT_CHAR_RE.findall(text)))
    raise ValueError(f"Unsupported char_count_mode: {profile.char_count_mode}")


def _share_divisor(raw_refs: list[int], refs: list[int], profile: ObjectiveProfile) -> float:
    if profile.credit_allocation_mode == "unique_refs":
        return float(len(_unique_ints(raw_refs)) or len(refs) or 1)
    if profile.credit_allocation_mode == "raw_refs":
        return float(len(raw_refs) or len(refs) or 1)
    if profile.credit_allocation_mode == "full_if_target":
        return 1.0
    raise ValueError(f"Unsupported credit_allocation_mode: {profile.credit_allocation_mode}")


def _position_credit(weight: float, divisor: float, profile: ObjectiveProfile) -> float:
    if profile.position_credit_mode == "share":
        return weight / max(divisor, 1.0)
    if profile.position_credit_mode == "full_if_target":
        return weight
    raise ValueError(f"Unsupported position_credit_mode: {profile.position_credit_mode}")


def _weighted_visibility(total_chars: float, total_weighted_chars: float, target_weighted_chars: float, profile: ObjectiveProfile) -> float:
    if profile.weighted_visibility_denominator_mode == "total_chars":
        denominator = total_chars
    elif profile.weighted_visibility_denominator_mode == "total_weighted_chars":
        denominator = total_weighted_chars
    else:
        raise ValueError(
            "Unsupported weighted_visibility_denominator_mode: "
            f"{profile.weighted_visibility_denominator_mode}"
        )
    return target_weighted_chars / denominator * 100 if denominator else 0.0


def score_objective(
    answer_text: str,
    *,
    target_source_id: int,
    profile: ObjectiveProfile | None = None,
) -> ObjectiveScore:
    profile = profile or DEFAULT_OBJECTIVE_PROFILE
    raw_segments = _split_segments(answer_text, profile)
    total_chars = 0.0
    target_chars = 0.0
    total_weighted_chars = 0.0
    target_weighted_chars = 0.0
    total_position_weight = 0.0
    target_position_weight = 0.0
    target_sentence_hits = 0
    total_sentences = len(raw_segments)

    for idx, segment in enumerate(raw_segments, start=1):
        raw_refs = [int(value) for value in REF_PATTERN.findall(segment)]
        refs = _extract_refs(segment, profile)
        clean_segment = REF_PATTERN.sub("", segment).strip()
        content_len = _content_length(clean_segment, profile)
        if content_len <= 0:
            continue
        weight = math.exp(-profile.position_decay_alpha * idx / max(total_sentences, 1))
        total_chars += content_len
        total_weighted_chars += content_len * weight
        total_position_weight += weight
        if not refs or target_source_id not in refs:
            continue
        share_divisor = _share_divisor(raw_refs, refs, profile)
        target_sentence_hits += 1
        target_chars += content_len / max(share_divisor, 1.0)
        target_weighted_chars += content_len * weight / max(share_divisor, 1.0)
        target_position_weight += _position_credit(weight, share_divisor, profile)

    coverage_ratio = target_chars / total_chars * 100 if total_chars else 0.0
    weighted_visibility = _weighted_visibility(total_chars, total_weighted_chars, target_weighted_chars, profile)
    position_prominence = target_position_weight / total_position_weight * 100 if total_position_weight else 0.0
    return ObjectiveScore(
        weighted_visibility=weighted_visibility,
        coverage_ratio=coverage_ratio,
        position_prominence=position_prominence,
        target_chars=target_chars,
        total_chars=total_chars,
        target_weighted_chars=target_weighted_chars,
        total_weighted_chars=total_weighted_chars,
        target_position_weight=target_position_weight,
        total_position_weight=total_position_weight,
        target_sentence_hits=target_sentence_hits,
        total_sentences=total_sentences,
    )
