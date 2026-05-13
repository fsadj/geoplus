from __future__ import annotations

import statistics
from pathlib import Path

from geoplus.analysis.reference_stats import build_valid_ref_pattern, count_references, get_target_ratios
from geoplus.evaluation.specs import EVALUATION_SPECS, build_test_output_name, get_evaluation_spec
from geoplus.paths import baseline_root, dataset_file, outputs_root

ZERO_WIDTH_SPACE = "​"

VALID_REF_PATTERN = build_valid_ref_pattern(
    *(spec.target_ref_name for spec in EVALUATION_SPECS.values())
)


def iter_dataset_ids() -> list[int]:
    dataset_ids: set[int] = set()

    baseline = baseline_root()
    if baseline.exists():
        for path in baseline.iterdir():
            if path.is_dir() and path.name.isdigit():
                dataset_ids.add(int(path.name))

    outputs = outputs_root() / "datasets"
    if outputs.exists():
        for path in outputs.iterdir():
            if path.is_dir() and path.name.isdigit():
                dataset_ids.add(int(path.name))

    return sorted(dataset_ids)


def dataset_labels(dataset_ids: list[int]) -> list[str]:
    return [f"DS{dataset_id}" for dataset_id in dataset_ids]


def test_output_path(dataset_id: int, variant_key: str, round_num: int) -> Path:
    return dataset_file(dataset_id, build_test_output_name(variant_key, round_num))


def load_eval_stats(dataset_id: int, variant_key: str, round_num: int = 1) -> dict | None:
    return count_references(test_output_path(dataset_id, variant_key, round_num), VALID_REF_PATTERN)


def get_target_metrics(dataset_id: int, variant_key: str, round_num: int = 1) -> tuple[float, float]:
    spec = get_evaluation_spec(variant_key)
    return get_target_ratios(load_eval_stats(dataset_id, variant_key, round_num), spec.target_ref_name)


def _complete_dataset_ids(required: list[tuple[str, int]], dataset_ids: list[int] | None = None) -> list[int]:
    selected = dataset_ids or iter_dataset_ids()
    complete_ids = []
    for dataset_id in selected:
        if all(test_output_path(dataset_id, variant_key, round_num).exists() for variant_key, round_num in required):
            complete_ids.append(dataset_id)
    return complete_ids


def _series_for_variant(dataset_ids: list[int], variant_key: str, round_num: int = 1) -> tuple[list[float], list[float]]:
    citation = []
    word = []
    for dataset_id in dataset_ids:
        citation_ratio, word_ratio = get_target_metrics(dataset_id, variant_key, round_num)
        citation.append(citation_ratio)
        word.append(word_ratio)
    return citation, word


def summarize_before_after(compare_variant: str = "after_nozws", dataset_ids: list[int] | None = None) -> dict:
    dataset_ids = _complete_dataset_ids([("before", 1), (compare_variant, 1)], dataset_ids)
    before_ref, before_word = _series_for_variant(dataset_ids, "before", 1)
    compare_ref, compare_word = _series_for_variant(dataset_ids, compare_variant, 1)
    ref_improve = [after - before for before, after in zip(before_ref, compare_ref)]
    word_improve = [after - before for before, after in zip(before_word, compare_word)]
    return {
        "dataset_ids": dataset_ids,
        "labels": dataset_labels(dataset_ids),
        "compare_variant": compare_variant,
        "before_ref_pct": before_ref,
        "before_word_pct": before_word,
        "compare_ref_pct": compare_ref,
        "compare_word_pct": compare_word,
        "ref_improve": ref_improve,
        "word_improve": word_improve,
        "avg_before_ref": statistics.mean(before_ref) if before_ref else 0.0,
        "avg_before_word": statistics.mean(before_word) if before_word else 0.0,
        "avg_compare_ref": statistics.mean(compare_ref) if compare_ref else 0.0,
        "avg_compare_word": statistics.mean(compare_word) if compare_word else 0.0,
    }


def summarize_zws_effect(dataset_ids: list[int] | None = None) -> dict:
    dataset_ids = _complete_dataset_ids([("after", 1), ("after_nozws", 1)], dataset_ids)
    zws_ref, zws_word = _series_for_variant(dataset_ids, "after", 1)
    nozws_ref, nozws_word = _series_for_variant(dataset_ids, "after_nozws", 1)
    ref_delta = [zws - nozws for zws, nozws in zip(zws_ref, nozws_ref)]
    word_delta = [zws - nozws for zws, nozws in zip(zws_word, nozws_word)]
    return {
        "dataset_ids": dataset_ids,
        "labels": dataset_labels(dataset_ids),
        "zws_ref_pct": zws_ref,
        "zws_word_pct": zws_word,
        "nozws_ref_pct": nozws_ref,
        "nozws_word_pct": nozws_word,
        "ref_delta": ref_delta,
        "word_delta": word_delta,
        "avg_zws_ref": statistics.mean(zws_ref) if zws_ref else 0.0,
        "avg_zws_word": statistics.mean(zws_word) if zws_word else 0.0,
        "avg_nozws_ref": statistics.mean(nozws_ref) if nozws_ref else 0.0,
        "avg_nozws_word": statistics.mean(nozws_word) if nozws_word else 0.0,
        "positive_ref_count": sum(1 for value in ref_delta if value > 0),
        "negative_ref_count": sum(1 for value in ref_delta if value < 0),
    }


def summarize_volatility(round_a: int = 1, round_b: int = 2, dataset_ids: list[int] | None = None) -> dict:
    dataset_ids = _complete_dataset_ids(
        [("after", round_a), ("after", round_b), ("after_nozws", round_a), ("after_nozws", round_b)],
        dataset_ids,
    )
    after_r1_cit, after_r1_word = _series_for_variant(dataset_ids, "after", round_a)
    after_r2_cit, after_r2_word = _series_for_variant(dataset_ids, "after", round_b)
    nozws_r1_cit, nozws_r1_word = _series_for_variant(dataset_ids, "after_nozws", round_a)
    nozws_r2_cit, nozws_r2_word = _series_for_variant(dataset_ids, "after_nozws", round_b)

    after_cit_delta = [r2 - r1 for r1, r2 in zip(after_r1_cit, after_r2_cit)]
    after_word_delta = [r2 - r1 for r1, r2 in zip(after_r1_word, after_r2_word)]
    nozws_cit_delta = [r2 - r1 for r1, r2 in zip(nozws_r1_cit, nozws_r2_cit)]
    nozws_word_delta = [r2 - r1 for r1, r2 in zip(nozws_r1_word, nozws_r2_word)]

    zws_eff_r1 = [after - nozws for after, nozws in zip(after_r1_cit, nozws_r1_cit)]
    zws_eff_r2 = [after - nozws for after, nozws in zip(after_r2_cit, nozws_r2_cit)]
    zws_eff_delta = [r2 - r1 for r1, r2 in zip(zws_eff_r1, zws_eff_r2)]
    zws_eff_word_r1 = [after - nozws for after, nozws in zip(after_r1_word, nozws_r1_word)]
    zws_eff_word_r2 = [after - nozws for after, nozws in zip(after_r2_word, nozws_r2_word)]
    zws_eff_word_delta = [r2 - r1 for r1, r2 in zip(zws_eff_word_r1, zws_eff_word_r2)]
    sign_flips = sum(1 for r1, r2 in zip(zws_eff_r1, zws_eff_r2) if (r1 > 0) != (r2 > 0))

    def mean_abs(values: list[float]) -> float:
        return statistics.mean(abs(value) for value in values) if values else 0.0

    def stdev(values: list[float]) -> float:
        return statistics.stdev(values) if len(values) > 1 else 0.0

    def max_abs(values: list[float]) -> float:
        return max((abs(value) for value in values), default=0.0)

    summary_rows = {
        "After.md": {
            "mean_abs_citation": mean_abs(after_cit_delta),
            "mean_abs_word": mean_abs(after_word_delta),
            "std_citation": stdev(after_cit_delta),
            "max_abs_citation": max_abs(after_cit_delta),
        },
        "After_nozws": {
            "mean_abs_citation": mean_abs(nozws_cit_delta),
            "mean_abs_word": mean_abs(nozws_word_delta),
            "std_citation": stdev(nozws_cit_delta),
            "max_abs_citation": max_abs(nozws_cit_delta),
        },
        "ZWS Effect": {
            "mean_abs_citation": mean_abs(zws_eff_delta),
            "mean_abs_word": mean_abs(zws_eff_word_delta),
            "std_citation": stdev(zws_eff_delta),
            "max_abs_citation": max_abs(zws_eff_delta),
        },
    }

    return {
        "dataset_ids": dataset_ids,
        "labels": dataset_labels(dataset_ids),
        "round_a": round_a,
        "round_b": round_b,
        "after_r1_cit": after_r1_cit,
        "after_r1_word": after_r1_word,
        "after_r2_cit": after_r2_cit,
        "after_r2_word": after_r2_word,
        "after_cit_delta": after_cit_delta,
        "after_word_delta": after_word_delta,
        "nozws_r1_cit": nozws_r1_cit,
        "nozws_r1_word": nozws_r1_word,
        "nozws_r2_cit": nozws_r2_cit,
        "nozws_r2_word": nozws_r2_word,
        "nozws_cit_delta": nozws_cit_delta,
        "nozws_word_delta": nozws_word_delta,
        "zws_eff_r1": zws_eff_r1,
        "zws_eff_r2": zws_eff_r2,
        "zws_eff_delta": zws_eff_delta,
        "zws_sign_flips": sign_flips,
        "summary_rows": summary_rows,
    }


def zws_density(file_path: Path) -> float:
    if not file_path.exists():
        return 0.0
    text = file_path.read_text(encoding="utf-8")
    if not text:
        return 0.0
    return text.count(ZERO_WIDTH_SPACE) / len(text) * 100


def summarize_salient_comparison(dataset_ids: list[int] | None = None) -> dict:
    dataset_ids = _complete_dataset_ids([("after", 1), ("after_nozws", 1), ("after_salient", 1)], dataset_ids)
    full_cit, full_word = _series_for_variant(dataset_ids, "after", 1)
    nozws_cit, nozws_word = _series_for_variant(dataset_ids, "after_nozws", 1)
    salient_cit, salient_word = _series_for_variant(dataset_ids, "after_salient", 1)

    full_density = [zws_density(dataset_file(dataset_id, "after.md")) for dataset_id in dataset_ids]
    nozws_density = [zws_density(dataset_file(dataset_id, "after_nozws.md")) for dataset_id in dataset_ids]
    salient_density = [zws_density(dataset_file(dataset_id, "after_salient.md")) for dataset_id in dataset_ids]

    salient_vs_full = [salient - full for salient, full in zip(salient_cit, full_cit)]

    strategy_summary = {
        "No-ZWS": {
            "avg_cit": statistics.mean(nozws_cit) if nozws_cit else 0.0,
            "avg_word": statistics.mean(nozws_word) if nozws_word else 0.0,
            "avg_density": statistics.mean(nozws_density) if nozws_density else 0.0,
        },
        "Salient-ZWS": {
            "avg_cit": statistics.mean(salient_cit) if salient_cit else 0.0,
            "avg_word": statistics.mean(salient_word) if salient_word else 0.0,
            "avg_density": statistics.mean(salient_density) if salient_density else 0.0,
        },
        "Full-ZWS": {
            "avg_cit": statistics.mean(full_cit) if full_cit else 0.0,
            "avg_word": statistics.mean(full_word) if full_word else 0.0,
            "avg_density": statistics.mean(full_density) if full_density else 0.0,
        },
    }

    return {
        "dataset_ids": dataset_ids,
        "labels": dataset_labels(dataset_ids),
        "full_cit": full_cit,
        "full_word": full_word,
        "nozws_cit": nozws_cit,
        "nozws_word": nozws_word,
        "salient_cit": salient_cit,
        "salient_word": salient_word,
        "full_density": full_density,
        "nozws_density": nozws_density,
        "salient_density": salient_density,
        "salient_vs_full": salient_vs_full,
        "strategy_summary": strategy_summary,
    }


def summarize_variant_family_two_rounds(
    variant_keys: list[str],
    dataset_ids: list[int] | None = None,
    round_a: int = 1,
    round_b: int = 2,
    baseline_key: str = "after_nozws",
) -> dict:
    required = [(baseline_key, round_a), (baseline_key, round_b)]
    required.extend((variant_key, round_a) for variant_key in variant_keys)
    required.extend((variant_key, round_b) for variant_key in variant_keys)
    dataset_ids = _complete_dataset_ids(required, dataset_ids)

    def summarize_variant(variant_key: str) -> dict:
        ref_r1, word_r1 = _series_for_variant(dataset_ids, variant_key, round_a)
        ref_r2, word_r2 = _series_for_variant(dataset_ids, variant_key, round_b)
        ref_avg_per_dataset = [(r1 + r2) / 2 for r1, r2 in zip(ref_r1, ref_r2)]
        word_avg_per_dataset = [(r1 + r2) / 2 for r1, r2 in zip(word_r1, word_r2)]
        ref_delta = [r2 - r1 for r1, r2 in zip(ref_r1, ref_r2)]
        word_delta = [r2 - r1 for r1, r2 in zip(word_r1, word_r2)]
        return {
            "ref_r1": ref_r1,
            "ref_r2": ref_r2,
            "word_r1": word_r1,
            "word_r2": word_r2,
            "ref_avg_per_dataset": ref_avg_per_dataset,
            "word_avg_per_dataset": word_avg_per_dataset,
            "ref_delta": ref_delta,
            "word_delta": word_delta,
            "avg_ref_r1": statistics.mean(ref_r1) if ref_r1 else 0.0,
            "avg_ref_r2": statistics.mean(ref_r2) if ref_r2 else 0.0,
            "avg_word_r1": statistics.mean(word_r1) if word_r1 else 0.0,
            "avg_word_r2": statistics.mean(word_r2) if word_r2 else 0.0,
            "avg_ref_2round": statistics.mean(ref_avg_per_dataset) if ref_avg_per_dataset else 0.0,
            "avg_word_2round": statistics.mean(word_avg_per_dataset) if word_avg_per_dataset else 0.0,
            "mean_abs_ref_delta": statistics.mean(abs(delta) for delta in ref_delta) if ref_delta else 0.0,
            "mean_abs_word_delta": statistics.mean(abs(delta) for delta in word_delta) if word_delta else 0.0,
            "max_abs_ref_delta": max((abs(delta) for delta in ref_delta), default=0.0),
            "max_abs_word_delta": max((abs(delta) for delta in word_delta), default=0.0),
        }

    baseline = summarize_variant(baseline_key)
    variants: dict[str, dict] = {}
    for variant_key in variant_keys:
        variant = summarize_variant(variant_key)
        variant["delta_vs_baseline_2round"] = variant["avg_ref_2round"] - baseline["avg_ref_2round"]
        variant["word_delta_vs_baseline_2round"] = variant["avg_word_2round"] - baseline["avg_word_2round"]
        variant["per_dataset_delta_vs_baseline_2round"] = [
            ref - base for ref, base in zip(variant["ref_avg_per_dataset"], baseline["ref_avg_per_dataset"])
        ]
        variant["per_dataset_word_delta_vs_baseline_2round"] = [
            word - base for word, base in zip(variant["word_avg_per_dataset"], baseline["word_avg_per_dataset"])
        ]
        variants[variant_key] = variant

    return {
        "dataset_ids": dataset_ids,
        "labels": dataset_labels(dataset_ids),
        "round_a": round_a,
        "round_b": round_b,
        "baseline_key": baseline_key,
        "baseline": baseline,
        "variants": variants,
    }


def summarize_variant_family(
    variant_keys: list[str],
    dataset_ids: list[int] | None = None,
    round_num: int = 1,
) -> dict:
    required = [("before", round_num)] + [(variant_key, round_num) for variant_key in variant_keys]
    dataset_ids = _complete_dataset_ids(required, dataset_ids)
    before_ref, before_word = _series_for_variant(dataset_ids, "before", round_num)

    variants: dict[str, dict] = {}
    for variant_key in variant_keys:
        ref_pct, word_pct = _series_for_variant(dataset_ids, variant_key, round_num)
        spec = get_evaluation_spec(variant_key)
        variants[variant_key] = {
            "source_name": spec.source_name,
            "target_ref_name": spec.target_ref_name,
            "ref_pct": ref_pct,
            "word_pct": word_pct,
            "avg_ref": statistics.mean(ref_pct) if ref_pct else 0.0,
            "avg_word": statistics.mean(word_pct) if word_pct else 0.0,
            "ref_improve": [ref - before for before, ref in zip(before_ref, ref_pct)],
            "word_improve": [word - before for before, word in zip(before_word, word_pct)],
        }

    return {
        "dataset_ids": dataset_ids,
        "labels": dataset_labels(dataset_ids),
        "round_num": round_num,
        "before_ref_pct": before_ref,
        "before_word_pct": before_word,
        "variants": variants,
    }
