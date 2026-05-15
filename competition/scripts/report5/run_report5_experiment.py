#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / "config" / "report5_datasets.json"
PREPARE_SCRIPT = REPO_ROOT / "scripts" / "report5" / "prepare_report5_datasets.py"
REPEATED_COMPARE_SCRIPT = REPO_ROOT / "scripts" / "simulator" / "run_repeated_compare.py"
CHART_SCRIPT = REPO_ROOT / "scripts" / "charts" / "generate_repeated_experiment_charts.py"
DOC_PATH = REPO_ROOT / "docs" / "report5.md"
OUTPUT_ROOT = REPO_ROOT / "outputs" / "repeated_experiments"
CHART_ROOT = REPO_ROOT / "outputs" / "charts"

STAGE1_VARIANTS = [
    "after_nozws",
    "after_dimensions",
    "after_rebuttal",
    "after_rebuttal_extended",
    "after_coverage_floor",
    "after_query_anchored_novelty_gap",
]

DISPLAY_LABELS = {
    "after_nozws": "No-ZWS Baseline",
    "after_dimensions": "Dimensions",
    "after_rebuttal": "Rebuttal",
    "after_rebuttal_extended": "Rebuttal Extended",
    "after_coverage_floor": "Coverage Floor",
    "after_query_anchored_novelty_gap": "Anchored Novelty",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run report5 repeated experiments inside competition/")
    parser.add_argument("--stage", choices=("prepare", "stage1", "stage2"), required=True, help="Stage to execute")
    parser.add_argument("--config", default=str(CONFIG_PATH), help="Path to report5 dataset config JSON")
    parser.add_argument("--datasets", default=None, help="Comma-separated internal dataset ids; default uses all configured datasets")
    parser.add_argument("--variants", default=None, help="Optional comma-separated variant keys override")
    parser.add_argument("--generation-rounds", type=int, default=None, help="Override generation round count")
    parser.add_argument("--sim-rounds", type=int, default=None, help="Override simulator round count")
    parser.add_argument(
        "--refresh-cache-mode",
        choices=("never", "first", "always"),
        default="first",
        help="How often to refresh zh-CN search cache during generation",
    )
    parser.add_argument("--experiment-name", default=None, help="Override repeated experiment output directory name")
    parser.add_argument("--chart-prefix", default=None, help="Override chart output prefix")
    parser.add_argument("--skip-prepare", action="store_true", help="Skip dataset preparation step")
    parser.add_argument("--skip-report", action="store_true", help="Skip writing docs/report5.md")
    parser.add_argument("--force-prepare", action="store_true", help="Force-clear internal prepared datasets before copying")
    return parser.parse_args()


def parse_int_list(raw: str) -> list[int]:
    return [int(part.strip()) for part in raw.split(",") if part.strip()]


def parse_variant_list(raw: str) -> list[str]:
    result = []
    for part in raw.split(","):
        value = part.strip()
        if not value:
            continue
        result.append(value.removesuffix(".md"))
    return result


def load_config(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("report5 dataset config must be a JSON array")
    return payload


def run_command(command: list[str], description: str) -> None:
    print(f"[{description}] {' '.join(command)}")
    subprocess.run(command, check=True)


def stage_defaults(stage: str) -> dict[str, Any]:
    if stage == "stage1":
        return {
            "variants": STAGE1_VARIANTS,
            "generation_rounds": 3,
            "sim_rounds": 3,
            "experiment_name": "report5_stage1_mechanism_screen",
            "chart_prefix": "report5_stage1",
        }
    if stage == "stage2":
        return {
            "variants": None,
            "generation_rounds": 5,
            "sim_rounds": 5,
            "experiment_name": "report5_stage2_stability_confirm",
            "chart_prefix": "report5_stage2",
        }
    return {
        "variants": [],
        "generation_rounds": 0,
        "sim_rounds": 0,
        "experiment_name": "report5_prepare",
        "chart_prefix": "report5_prepare",
    }


def variant_label(variant_key: str) -> str:
    return DISPLAY_LABELS.get(variant_key, variant_key.removeprefix("after_").replace("_", " ").title())


def configured_dataset_ids(entries: list[dict[str, Any]]) -> list[int]:
    return [int(entry["internal_dataset_id"]) for entry in entries]


def prepare_datasets(config_path: Path, *, force: bool) -> None:
    command = [sys.executable, str(PREPARE_SCRIPT), "--config", str(config_path)]
    if force:
        command.append("--force")
    run_command(command, "prepare report5 datasets")


def experiment_dir(experiment_name: str) -> Path:
    return OUTPUT_ROOT / experiment_name


def select_stage2_variants(stage1_dir: Path) -> list[str]:
    summary_path = stage1_dir / "summary_by_variant.json"
    variance_path = stage1_dir / "variance_decomposition.json"
    if not summary_path.exists() or not variance_path.exists():
        raise FileNotFoundError(
            "stage1 outputs not found; run stage1 first or pass --variants explicitly for stage2"
        )

    summary_rows = json.loads(summary_path.read_text(encoding="utf-8"))
    variance_rows = json.loads(variance_path.read_text(encoding="utf-8"))
    variance_map = {row["variant"]: row for row in variance_rows}

    def rank_key(row: dict[str, Any]) -> tuple[float, float, float, float, float, float]:
        variance = float(variance_map.get(row["variant"], {}).get("mean_total_variance", 0.0))
        return (
            float(row.get("ci95_low", 0.0)),
            float(row.get("win_rate_ci95_low", 0.0)),
            float(row.get("win_rate", 0.0)),
            float(row.get("avg_delta", 0.0)),
            -variance,
            float(row.get("avg_ai_delta", 0.0)),
        )

    candidates = [row for row in summary_rows if row["variant"] != "after_nozws"]
    ranked = sorted(candidates, key=rank_key, reverse=True)
    selected = ["after_nozws", *[row["variant"] for row in ranked[:3]]]
    payload = {
        "selection_rule": [
            "higher ci95_low",
            "higher win_rate_ci95_low",
            "higher win_rate",
            "higher avg_delta",
            "lower mean_total_variance",
            "higher avg_ai_delta",
        ],
        "selected_variants": selected,
        "ranked_candidates": [
            {
                "variant": row["variant"],
                "avg_delta": row["avg_delta"],
                "ci95_low": row.get("ci95_low"),
                "win_rate": row.get("win_rate"),
                "win_rate_ci95_low": row.get("win_rate_ci95_low"),
                "mean_total_variance": variance_map.get(row["variant"], {}).get("mean_total_variance"),
                "avg_ai_delta": row.get("avg_ai_delta"),
            }
            for row in ranked
        ],
    }
    (stage1_dir / "stage2_selection.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return selected


def run_stage(
    *,
    stage: str,
    config_path: Path,
    dataset_ids: list[int],
    variants: list[str],
    generation_rounds: int,
    sim_rounds: int,
    refresh_cache_mode: str,
    experiment_name: str,
    chart_prefix: str,
) -> Path:
    output_dir = experiment_dir(experiment_name)
    command = [
        sys.executable,
        str(REPEATED_COMPARE_SCRIPT),
        "--datasets",
        ",".join(str(dataset_id) for dataset_id in dataset_ids),
        "--variants",
        ",".join(variants),
        "--generation-rounds",
        str(generation_rounds),
        "--sim-rounds",
        str(sim_rounds),
        "--refresh-cache-mode",
        refresh_cache_mode,
        "--experiment-name",
        experiment_name,
        "--output-root",
        str(output_dir),
        "--dataset-manifest",
        str(config_path),
    ]
    run_command(command, f"run report5 {stage}")
    run_command(
        [
            sys.executable,
            str(CHART_SCRIPT),
            "--experiment-dir",
            str(output_dir),
            "--prefix",
            chart_prefix,
        ],
        f"chart report5 {stage}",
    )
    return output_dir


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def render_dataset_mapping(entries: list[dict[str, Any]]) -> list[str]:
    lines = [
        "| Match | Internal | Legacy | Title |",
        "| --- | ---: | ---: | --- |",
    ]
    for entry in entries:
        lines.append(
            f"| Match{entry['match_dataset_id']} | DS{entry['internal_dataset_id']} | DS{entry['legacy_dataset_id']} | {entry['title']} |"
        )
    return lines


def render_variant_table(summary_rows: list[dict[str, Any]]) -> list[str]:
    ordered = sorted(summary_rows, key=lambda row: row["avg_delta"], reverse=True)
    lines = [
        "| Route | avg_delta | obj_delta | ai_delta | win_rate | delta 95% CI | variance |",
        "| --- | ---: | ---: | ---: | ---: | --- | ---: |",
    ]
    for row in ordered:
        lines.append(
            "| "
            f"`{row['variant']}` ({variant_label(row['variant'])}) | "
            f"{row['avg_delta']:+.2f} | "
            f"{row['avg_objective_delta']:+.2f} | "
            f"{row['avg_ai_delta']:+.2f} | "
            f"{row['win_rate']:.1f}% | "
            f"[{row['ci95_low']:+.2f}, {row['ci95_high']:+.2f}] | "
            f"{row.get('mean_total_variance', 0.0):.2f} |"
        )
    return lines


def render_chart_links(chart_prefix: str) -> list[str]:
    names = [
        f"{chart_prefix}_delta_ci.png",
        f"{chart_prefix}_per_dataset_delta.png",
        f"{chart_prefix}_variance_split.png",
        f"{chart_prefix}_metric_overview.png",
    ]
    lines = []
    for name in names:
        chart_path = CHART_ROOT / name
        if chart_path.exists():
            lines.append(f"![{name}](../outputs/charts/{name})")
    return lines


def stage_result(stage_name: str, experiment_name: str, chart_prefix: str) -> dict[str, Any] | None:
    output_dir = experiment_dir(experiment_name)
    summary_path = output_dir / "summary_by_variant.json"
    if not summary_path.exists():
        return None
    result = {
        "stage_name": stage_name,
        "output_dir": output_dir,
        "chart_prefix": chart_prefix,
        "manifest": load_json(output_dir / "manifest.json") if (output_dir / "manifest.json").exists() else None,
        "summary_by_variant": load_json(summary_path),
        "summary_by_dataset": load_json(output_dir / "summary_by_dataset.json"),
        "variance": load_json(output_dir / "variance_decomposition.json"),
        "selection": load_json(output_dir / "stage2_selection.json") if (output_dir / "stage2_selection.json").exists() else None,
    }
    variance_map = {row["variant"]: row for row in result["variance"]}
    for row in result["summary_by_variant"]:
        row["mean_total_variance"] = variance_map.get(row["variant"], {}).get("mean_total_variance", 0.0)
    return result


def recommendation_from_rows(summary_rows: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    candidates = [row for row in summary_rows if row["variant"] != "after_nozws"]
    ordered = sorted(
        candidates,
        key=lambda row: (
            row.get("ci95_low", 0.0),
            row.get("win_rate_ci95_low", 0.0),
            row.get("win_rate", 0.0),
            row.get("avg_delta", 0.0),
            -row.get("mean_total_variance", 0.0),
            row.get("avg_ai_delta", 0.0),
        ),
        reverse=True,
    )
    primary = ordered[0] if ordered else None
    backup = ordered[1] if len(ordered) > 1 else None
    return primary, backup


def write_report(config_entries: list[dict[str, Any]]) -> None:
    stage1 = stage_result("阶段一", "report5_stage1_mechanism_screen", "report5_stage1")
    stage2 = stage_result("阶段二", "report5_stage2_stability_confirm", "report5_stage2")

    lines: list[str] = []
    lines.append("# GEO+ 五组比赛数据稳定性验证（Report 5）")
    lines.append("")
    lines.append("> 本报告聚焦五组比赛题的独立验证，只使用 `competition/` 内部数据与脚本，不写回 `competition_match/`。")
    lines.append("")
    lines.append("## 一、实验目标")
    lines.append("")
    lines.append("围绕已验证过的 GEO 备选路线，在当前五组比赛题上比较均值收益、稳定性、客观得分增量与 AI 得分增量，筛出适合比赛默认使用的路线。")
    lines.append("")
    lines.append("## 二、数据映射")
    lines.append("")
    lines.extend(render_dataset_mapping(config_entries))
    lines.append("")

    for stage in [stage1, stage2]:
        if stage is None:
            continue
        manifest = stage.get("manifest") or {}
        lines.append(f"## {stage['stage_name']}结果")
        lines.append("")
        lines.append(
            f"- 数据集：{', '.join(f'DS{dataset_id}' for dataset_id in manifest.get('datasets', []))}"
        )
        lines.append(
            f"- 路线：{', '.join(f'`{variant}`' for variant in manifest.get('variants', []))}"
        )
        lines.append(
            f"- 重复规模：{manifest.get('generation_rounds', '?')} generation x {manifest.get('sim_rounds', '?')} simulator"
        )
        lines.append(
            f"- 输出目录：`competition/outputs/repeated_experiments/{stage['output_dir'].name}/`"
        )
        lines.append("")
        lines.extend(render_variant_table(stage["summary_by_variant"]))
        lines.append("")
        if stage.get("selection"):
            selected = ", ".join(f"`{variant}`" for variant in stage["selection"]["selected_variants"])
            lines.append(f"阶段二入围规则已按稳定性优先计算，当前入围路线：{selected}。")
            lines.append("")
        lines.extend(render_chart_links(stage["chart_prefix"]))
        lines.append("")

    lines.append("## 四、结论")
    lines.append("")
    reference_rows = stage2["summary_by_variant"] if stage2 else (stage1["summary_by_variant"] if stage1 else [])
    primary, backup = recommendation_from_rows(reference_rows)
    if primary is not None:
        lines.append(
            f"默认推荐路线是 `{primary['variant']}`（{variant_label(primary['variant'])}），因为它在当前可用结果里同时保持了较高的 `ci95_low`、`win_rate` 和 `avg_delta`。"
        )
    else:
        lines.append("当前还没有可用于下结论的完整阶段结果。")
    if backup is not None:
        lines.append(
            f"备选路线是 `{backup['variant']}`（{variant_label(backup['variant'])}），适合作为主路线失稳时的替代候选。"
        )
    if not stage2:
        lines.append("阶段二结果尚未生成时，本报告的推荐仅基于阶段一或当前已完成的结果，不视为最终比赛默认结论。")
    lines.append("")

    DOC_PATH.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    print(f"report={DOC_PATH}")


def main() -> None:
    args = parse_args()
    config_path = Path(args.config)
    config_entries = load_config(config_path)

    if args.stage == "prepare":
        prepare_datasets(config_path, force=args.force_prepare)
        return

    if not args.skip_prepare:
        prepare_datasets(config_path, force=args.force_prepare)

    defaults = stage_defaults(args.stage)
    dataset_ids = parse_int_list(args.datasets) if args.datasets else configured_dataset_ids(config_entries)

    if args.variants:
        variants = parse_variant_list(args.variants)
    elif args.stage == "stage2":
        variants = select_stage2_variants(experiment_dir("report5_stage1_mechanism_screen"))
    else:
        variants = list(defaults["variants"])

    generation_rounds = args.generation_rounds or defaults["generation_rounds"]
    sim_rounds = args.sim_rounds or defaults["sim_rounds"]
    experiment_name = args.experiment_name or defaults["experiment_name"]
    chart_prefix = args.chart_prefix or defaults["chart_prefix"]

    run_stage(
        stage=args.stage,
        config_path=config_path,
        dataset_ids=dataset_ids,
        variants=variants,
        generation_rounds=generation_rounds,
        sim_rounds=sim_rounds,
        refresh_cache_mode=args.refresh_cache_mode,
        experiment_name=experiment_name,
        chart_prefix=chart_prefix,
    )

    if not args.skip_report:
        write_report(config_entries)


if __name__ == "__main__":
    main()
