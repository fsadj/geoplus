# GEO+ Competition Project

这个子项目承载当前所有比赛相关的生成、评测、分析、图表和 simulator 复刻工作流。仓库重组后，比赛内容已经从根目录整体迁入 `competition/`，后续所有比赛相关操作都应以这里为入口。

## Scope

本子项目包含 4 条主线：

- 生成主线：把 `before.md` 扩展成更强的信息型候选文本，默认产出 `after_nozws.md`，并派生 `after.md` 等变体。
- 评测主线：运行 `before/after` 多轮评测，生成 `test_<variant>_rN.md` 等结果文件。
- 分析与图表主线：对引用次数、字数占比、波动性、内容路线和长度实验做汇总统计。
- simulator 主线：复刻比赛题面、校准客观评分口径、比较候选变体、生成质询图表。

## Layout

```text
competition/
├── README.md
├── data/
│   └── baseline/{id}/
├── docs/
│   ├── report.md
│   ├── 比赛具体信息.md
│   ├── 关于官方客观评分口径的质询报告.md
│   └── assets/
├── outputs/
│   ├── charts/
│   ├── datasets/{id}/
│   ├── objective_tuning/
│   └── pdf/
├── prompts/
├── scripts/
│   ├── pipeline/
│   ├── transforms/
│   ├── evaluation/
│   ├── analysis/
│   ├── charts/
│   └── simulator/
├── simulator/
├── src/geoplus/
├── requirements.txt
└── data.md
```

## Install

从 `competition/` 目录执行：

```bash
pip install -r requirements.txt
```

模型调用默认走 `src/geoplus/anthropic_client.py`，可通过这些环境变量覆盖：

- `ANTHROPIC_BASE_URL`
- `ANTHROPIC_AUTH_TOKEN`
- `ANTHROPIC_MODEL`

联网搜索默认走本地 SearXNG：`http://127.0.0.1:18080`，并默认使用中文搜索关键词，可通过这些环境变量覆盖：

- `SEARXNG_BASE_URL`
- `SEARXNG_TIMEOUT`
- `SEARXNG_ENGINES`（默认 `bing,baidu,sogou`）

流程二当前使用中文缓存文件名 `flow2_<profile>_search_zh_v2.json`。旧的英文缓存文件 `flow2_<profile>_search.json` 不会再被默认复用。

如果切换了搜索后端、关键词口径或想强制重跑流程二缓存，请在生成命令中加 `--refresh-cache`。批量重复实验是否重跑中文搜索缓存，由 `scripts/simulator/run_repeated_compare.py` 的 `--refresh-cache-mode` 控制。

## Main Workflow

生成指定数据集的默认基线 `after_nozws.md`，并同步派生 Full-ZWS 版本 `after.md`：

```bash
python scripts/pipeline/main.py --dataset 1
```

输入来自 `data/baseline/1/`，输出写到 `outputs/datasets/1/after_nozws.md` 和 `outputs/datasets/1/after.md`。

## Variant Transforms

从 `after.md` 重建 `after_nozws.md`：

```bash
python scripts/transforms/strip_zwsp.py --dataset 1
```

对 `after_nozws.md` 做语义级 ZWS 注入，生成 `after_salient.md`：

```bash
python scripts/transforms/generate_salient.py --dataset 1
python scripts/transforms/generate_salient.py --all
```

## Evaluation Workflow

统一评测入口：

```bash
python scripts/evaluation/run_eval.py --dataset 1 --variant before --round 1
python scripts/evaluation/run_eval.py --dataset 1 --variant after_nozws --round 1
python scripts/analysis/count_references.py --dataset 1
```

常用分析脚本：

```bash
python scripts/analysis/analyze_volatility.py
python scripts/analysis/count_zws_effect.py --dataset 1
python scripts/analysis/compare_salient.py
python scripts/analysis/compare_content_experiments.py --format markdown
```

legacy 包装脚本 `test_before.py`、`test_after.py`、`test_after_r2.py`、`test_after_nozws.py`、`test_after_nozws_r2.py`、`test_after_salient.py` 已迁入 [`../archive/competition-legacy/`](../archive/competition-legacy/)。后续新增轮次统一使用 `scripts/evaluation/run_eval.py`。

## Chart Workflow

```bash
python scripts/charts/generate_charts.py
python scripts/charts/generate_zws_charts.py
python scripts/charts/generate_volatility_charts.py
python scripts/charts/generate_content_experiment_charts.py
python scripts/charts/generate_length_band_charts.py
python scripts/charts/generate_report2_charts.py
```

图表统一输出到 `outputs/charts/`。

## Simulator Workflow

`simulator/` 与 `scripts/simulator/` 承担比赛题面复刻、官方格式物化、客观评分口径校准与变体比较。常用入口包括：

```bash
python simulator/cli.py evaluate --dataset 101
python simulator/cli.py batch --datasets 101,102,103
python scripts/simulator/materialize_data_md.py
python scripts/simulator/tune_objective.py --help
python scripts/simulator/compare_variants.py --help
```

## Data And Naming Conventions

`data/baseline/{id}/` 只保留输入文件：

- `before.md`
- `question.md`
- `1.md`
- `2.md`
- `3.md`
- `4.md`

`outputs/datasets/{id}/` 保存生成与评测产物。以下命名约定被整条分析链复用，请不要随意改名：

- `after_nozws.md`
- `after.md`
- `after_salient.md`
- `test_<variant>_rN.md`
- `simulator_item_ds{id}.json`

## Docs

- 实验总报告：[`docs/report.md`](docs/report.md)
- 比赛说明：[`docs/比赛具体信息.md`](docs/比赛具体信息.md)
- 客观评分口径质询报告：[`docs/关于官方客观评分口径的质询报告.md`](docs/关于官方客观评分口径的质询报告.md)

## Notes

- 评测脚本使用的系统提示词位于 `prompts/main_prompt.md`，不是 `scripts/pipeline/main.py` 的输入。
- `outputs/curated_data_manifest.json` 记录了 `data.md` 物化出的 curated 题目清单。
- 中文 PDF 字体测试产物已经移入归档，`scripts/charts/test_font_pdf.py` 如需继续使用，可在 `outputs/pdf/` 下重新生成。
