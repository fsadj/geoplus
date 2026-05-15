#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, replace
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from simulator.data import load_json_item
from simulator.objective import DEFAULT_OBJECTIVE_PROFILE, ObjectiveProfile, score_objective


@dataclass(frozen=True)
class CalibrationSample:
    label: str
    answer_text: str
    target_source_id: int
    official_word_volu: float
    official_posi_prom: float
    official_word_posi: float


def _parse_csv(raw: str) -> list[str]:
    return [part.strip() for part in raw.split(",") if part.strip()]


def _parse_float_csv(raw: str) -> list[float]:
    return [float(part) for part in _parse_csv(raw)]


def _profile_signature(profile: ObjectiveProfile) -> tuple[object, ...]:
    return (
        profile.sentence_split_mode,
        profile.ref_dedup_mode,
        profile.credit_allocation_mode,
        profile.position_credit_mode,
        round(profile.position_decay_alpha, 6),
        profile.coverage_denominator_mode,
        profile.position_denominator_mode,
        profile.weighted_visibility_denominator_mode,
        profile.char_count_mode,
    )


def _profile_name(profile: ObjectiveProfile) -> str:
    if profile == DEFAULT_OBJECTIVE_PROFILE:
        return DEFAULT_OBJECTIVE_PROFILE.name
    return (
        f"split={profile.sentence_split_mode}"
        f"|dedup={profile.ref_dedup_mode}"
        f"|credit={profile.credit_allocation_mode}"
        f"|pos={profile.position_credit_mode}"
        f"|alpha={profile.position_decay_alpha:g}"
        f"|cov={profile.coverage_denominator_mode}"
        f"|pp={profile.position_denominator_mode}"
        f"|denom={profile.weighted_visibility_denominator_mode}"
        f"|chars={profile.char_count_mode}"
    )


def _build_samples(args: argparse.Namespace) -> list[CalibrationSample]:
    samples: list[CalibrationSample] = []
    for item_json in args.item_json:
        item = load_json_item(item_json, input_mode=args.input_mode)
        if item.visibility_before is None or item.generated_original_answer is None:
            raise ValueError(f"item_json 缺少官方 before 分数或原始答案: {item_json}")
        samples.append(
            CalibrationSample(
                label=Path(item_json).stem,
                answer_text=item.generated_original_answer,
                target_source_id=item.target.source_id,
                official_word_volu=item.visibility_before.word_volu,
                official_posi_prom=item.visibility_before.posi_prom,
                official_word_posi=item.visibility_before.word_posi,
            )
        )
    if args.answer_path:
        answer_path = Path(args.answer_path)
        answer_text = answer_path.read_text(encoding="utf-8").strip()
        samples.append(
            CalibrationSample(
                label=args.label or answer_path.stem,
                answer_text=answer_text,
                target_source_id=args.target_source_id,
                official_word_volu=args.official_word_volu,
                official_posi_prom=args.official_posi_prom,
                official_word_posi=args.official_word_posi,
            )
        )
    if not samples:
        raise ValueError("至少提供 --item-json 或 --answer-path")
    return samples


def _build_profiles(args: argparse.Namespace) -> list[ObjectiveProfile]:
    profiles: list[ObjectiveProfile] = []
    seen: set[tuple[object, ...]] = set()
    for sentence_split_mode in _parse_csv(args.sentence_split_modes):
        for ref_dedup_mode in _parse_csv(args.ref_dedup_modes):
            for credit_allocation_mode in _parse_csv(args.credit_allocation_modes):
                for position_credit_mode in _parse_csv(args.position_credit_modes):
                    for position_decay_alpha in _parse_float_csv(args.position_decay_alphas):
                        for coverage_denominator_mode in _parse_csv(args.coverage_denominator_modes):
                            for position_denominator_mode in _parse_csv(args.position_denominator_modes):
                                for weighted_visibility_denominator_mode in _parse_csv(args.weighted_visibility_denominator_modes):
                                    for char_count_mode in _parse_csv(args.char_count_modes):
                                        profile = replace(
                                            DEFAULT_OBJECTIVE_PROFILE,
                                            sentence_split_mode=sentence_split_mode,
                                            ref_dedup_mode=ref_dedup_mode,
                                            credit_allocation_mode=credit_allocation_mode,
                                            position_credit_mode=position_credit_mode,
                                            position_decay_alpha=position_decay_alpha,
                                            coverage_denominator_mode=coverage_denominator_mode,
                                            position_denominator_mode=position_denominator_mode,
                                            weighted_visibility_denominator_mode=weighted_visibility_denominator_mode,
                                            char_count_mode=char_count_mode,
                                        )
                                        signature = _profile_signature(profile)
                                        if signature in seen:
                                            continue
                                        seen.add(signature)
                                        profile_name = _profile_name(profile)
                                        profiles.append(replace(profile, name=profile_name))
    return profiles


def _score_sample(sample: CalibrationSample, profile: ObjectiveProfile) -> dict[str, object]:
    objective = score_objective(sample.answer_text, target_source_id=sample.target_source_id, profile=profile)
    word_volu_gap = objective.word_volu - sample.official_word_volu
    posi_prom_gap = objective.posi_prom - sample.official_posi_prom
    word_posi_gap = objective.word_posi - sample.official_word_posi
    abs_errors = [abs(word_volu_gap), abs(posi_prom_gap), abs(word_posi_gap)]
    return {
        "label": sample.label,
        "target_source_id": sample.target_source_id,
        "official_word_volu": sample.official_word_volu,
        "simulator_word_volu": objective.word_volu,
        "word_volu_gap": word_volu_gap,
        "official_posi_prom": sample.official_posi_prom,
        "simulator_posi_prom": objective.posi_prom,
        "posi_prom_gap": posi_prom_gap,
        "official_word_posi": sample.official_word_posi,
        "simulator_word_posi": objective.word_posi,
        "word_posi_gap": word_posi_gap,
        "mean_abs_error": sum(abs_errors) / len(abs_errors),
        "max_abs_error": max(abs_errors),
        "objective": objective.to_dict(include_aliases=True),
    }


def _evaluate_profiles(samples: list[CalibrationSample], profiles: list[ObjectiveProfile]) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    for profile in profiles:
        sample_results = [_score_sample(sample, profile) for sample in samples]
        word_volu_mae = sum(abs(item["word_volu_gap"]) for item in sample_results) / len(sample_results)
        posi_prom_mae = sum(abs(item["posi_prom_gap"]) for item in sample_results) / len(sample_results)
        word_posi_mae = sum(abs(item["word_posi_gap"]) for item in sample_results) / len(sample_results)
        max_abs_error = max(item["max_abs_error"] for item in sample_results)
        results.append(
            {
                "profile_name": profile.name,
                "profile": asdict(profile),
                "sample_count": len(sample_results),
                "word_volu_mae": word_volu_mae,
                "posi_prom_mae": posi_prom_mae,
                "word_posi_mae": word_posi_mae,
                "mean_abs_error": (word_volu_mae + posi_prom_mae + word_posi_mae) / 3.0,
                "max_abs_error": max_abs_error,
                "sample_results": sample_results,
            }
        )
    results.sort(key=lambda item: (item["mean_abs_error"], item["max_abs_error"], item["word_posi_mae"]))
    return results


def _default_output_path() -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return REPO_ROOT / "outputs" / "objective_tuning" / f"tune_objective_{timestamp}.json"


def _print_top(results: list[dict[str, object]], top_n: int) -> None:
    for index, result in enumerate(results[:top_n], start=1):
        print(
            json.dumps(
                {
                    "rank": index,
                    "profile_name": result["profile_name"],
                    "sample_count": result["sample_count"],
                    "word_volu_mae": result["word_volu_mae"],
                    "posi_prom_mae": result["posi_prom_mae"],
                    "word_posi_mae": result["word_posi_mae"],
                    "mean_abs_error": result["mean_abs_error"],
                    "max_abs_error": result["max_abs_error"],
                },
                ensure_ascii=False,
            )
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Search objective-scoring profiles against official reference scores")
    parser.add_argument("--item-json", action="append", default=[], help="Path to one official-style simulator item JSON; repeatable")
    parser.add_argument("--input-mode", choices=("strict", "compat"), default="strict")
    parser.add_argument("--answer-path", help="Path to a reference answer text file")
    parser.add_argument("--target-source-id", type=int, help="Target source id for --answer-path")
    parser.add_argument("--official-word-volu", type=float, help="Official word_volu for --answer-path")
    parser.add_argument("--official-posi-prom", type=float, help="Official posi_prom for --answer-path")
    parser.add_argument("--official-word-posi", type=float, help="Official word_posi for --answer-path")
    parser.add_argument("--label", help="Optional sample label for --answer-path")
    parser.add_argument("--sentence-split-modes", default="punct_or_newline,punct,paragraph")
    parser.add_argument("--ref-dedup-modes", default="unique,raw,collapse_consecutive")
    parser.add_argument("--credit-allocation-modes", default="unique_refs,raw_refs,full_if_target")
    parser.add_argument("--position-credit-modes", default="share,full_if_target")
    parser.add_argument("--position-decay-alphas", default="0.75,1.0,1.25")
    parser.add_argument("--coverage-denominator-modes", default="total_chars,cited_chars")
    parser.add_argument("--position-denominator-modes", default="total_position_weight,cited_position_weight")
    parser.add_argument("--weighted-visibility-denominator-modes", default="total_chars,cited_chars,total_weighted_chars,cited_weighted_chars")
    parser.add_argument("--char-count-modes", default="all,strip_whitespace,text_only")
    parser.add_argument("--top", type=int, default=10, help="How many top profiles to print")
    parser.add_argument("--output", help="Output JSON path")
    args = parser.parse_args()

    if args.answer_path:
        required_manual = {
            "--target-source-id": args.target_source_id,
            "--official-word-volu": args.official_word_volu,
            "--official-posi-prom": args.official_posi_prom,
            "--official-word-posi": args.official_word_posi,
        }
        missing = [name for name, value in required_manual.items() if value is None]
        if missing:
            raise SystemExit(f"使用 --answer-path 时缺少参数: {', '.join(missing)}")

    samples = _build_samples(args)
    profiles = _build_profiles(args)
    results = _evaluate_profiles(samples, profiles)
    output_path = Path(args.output) if args.output else _default_output_path()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "sample_count": len(samples),
        "profile_count": len(profiles),
        "samples": [asdict(sample) for sample in samples],
        "results": results,
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _print_top(results, args.top)
    print(f"output_path={output_path}")


if __name__ == "__main__":
    main()
