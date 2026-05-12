from dataclasses import dataclass


@dataclass(frozen=True)
class EvaluationSpec:
    variant_key: str
    source_name: str
    target_ref_name: str
    style: str
    start_message: str
    missing_message: str | None = None


EVALUATION_SPECS: dict[str, EvaluationSpec] = {
    "before": EvaluationSpec(
        variant_key="before",
        source_name="before.md",
        target_ref_name="before.md",
        style="fullwidth",
        start_message="开始测试 before.md...",
    ),
    "after": EvaluationSpec(
        variant_key="after",
        source_name="after.md",
        target_ref_name="after.md",
        style="fullwidth",
        start_message="开始测试 after.md...",
    ),
    "after_nozws": EvaluationSpec(
        variant_key="after_nozws",
        source_name="after_nozws.md",
        target_ref_name="after_nozws.md",
        style="square",
        start_message="开始测试 after_nozws.md...",
    ),
    "after_salient": EvaluationSpec(
        variant_key="after_salient",
        source_name="after_salient.md",
        target_ref_name="after_salient.md",
        style="square",
        start_message="开始测试 after_salient.md...",
        missing_message="ERROR: {path} not found. Run generate_salient.py first.",
    ),
    "after_skeleton": EvaluationSpec(
        variant_key="after_skeleton",
        source_name="after_skeleton.md",
        target_ref_name="after_skeleton.md",
        style="square",
        start_message="开始测试 after_skeleton.md...",
    ),
    "after_stance": EvaluationSpec(
        variant_key="after_stance",
        source_name="after_stance.md",
        target_ref_name="after_stance.md",
        style="square",
        start_message="开始测试 after_stance.md...",
    ),
    "after_dimensions": EvaluationSpec(
        variant_key="after_dimensions",
        source_name="after_dimensions.md",
        target_ref_name="after_dimensions.md",
        style="square",
        start_message="开始测试 after_dimensions.md...",
    ),
    "after_evidence": EvaluationSpec(
        variant_key="after_evidence",
        source_name="after_evidence.md",
        target_ref_name="after_evidence.md",
        style="square",
        start_message="开始测试 after_evidence.md...",
    ),
    "after_rebuttal": EvaluationSpec(
        variant_key="after_rebuttal",
        source_name="after_rebuttal.md",
        target_ref_name="after_rebuttal.md",
        style="square",
        start_message="开始测试 after_rebuttal.md...",
    ),
}


def get_evaluation_spec(variant_key: str) -> EvaluationSpec:
    try:
        return EVALUATION_SPECS[variant_key]
    except KeyError as exc:
        valid = ", ".join(sorted(EVALUATION_SPECS))
        raise ValueError(f"Unknown variant '{variant_key}'. Valid values: {valid}") from exc


def build_test_output_name(variant_key: str, round_num: int) -> str:
    if round_num < 1:
        raise ValueError("round_num must be >= 1")

    base_name = f"test_{variant_key}.md"
    if round_num == 1:
        return base_name
    return f"test_{variant_key}_r{round_num}.md"


def format_start_message(spec: EvaluationSpec, round_num: int) -> str:
    if round_num == 1:
        return spec.start_message
    return f"开始测试 {spec.source_name} (Round {round_num})..."
