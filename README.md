# GEO+

GEO+ 是一个面向多文档竞争场景的实验仓库。它会把 `before.md` 扩展成信息密度更高的 `after.md`，再通过独立评测脚本、统计脚本和图表脚本比较不同策略的引用表现。

## 目录结构

```text
geoplus/
├── data/
│   └── baseline/{id}/            # 原始输入：before.md、question.md、1.md-4.md
├── docs/
│   └── report.md                 # 实验报告
├── outputs/
│   ├── charts/                   # 已生成图表
│   ├── datasets/{id}/            # 生成文档和评测结果
│   └── pdf/                      # PDF 导出物
├── prompts/
│   └── main_prompt.md            # 评测脚本使用的系统提示词
├── scripts/
│   ├── pipeline/                 # 主生成入口
│   ├── transforms/               # after_nozws / after_salient 生成脚本
│   ├── evaluation/               # 评测脚本
│   ├── analysis/                 # 统计分析脚本
│   └── charts/                   # 图表脚本
├── src/geoplus/                  # 共享库代码
├── requirements.txt
└── README.md
```

## 环境变量

模型调用统一走 [src/geoplus/anthropic_client.py](/Users/brazion/Desktop/geoplus/src/geoplus/anthropic_client.py)。默认配置如下，也可以通过环境变量覆盖：

- `ANTHROPIC_BASE_URL`
- `ANTHROPIC_AUTH_TOKEN`
- `ANTHROPIC_MODEL`

当前默认值指向一个 Anthropic-compatible gateway，默认模型名是 `gpt-5.4`。

## 安装

```bash
pip install -r requirements.txt
```

## 主生成流程

生成指定数据集的 `after.md`：

```bash
python scripts/pipeline/main.py --dataset 1
```

输入来自 `data/baseline/1/`，输出写到 `outputs/datasets/1/after.md`。

## 变体生成

去掉零宽字符，生成 `after_nozws.md`：

```bash
python scripts/transforms/strip_zwsp.py --dataset 1
```

对 `after_nozws.md` 做语义级 ZWS 注入，生成 `after_salient.md`：

```bash
python scripts/transforms/generate_salient.py --dataset 1
python scripts/transforms/generate_salient.py --all
```

默认不带参数时处理 DS1-DS5；`--all` 会处理 DS1-DS14。

## 评测流程

基础评测：

```bash
python scripts/evaluation/test_before.py --dataset 1
python scripts/evaluation/test_after.py --dataset 1
python scripts/analysis/count_references.py --dataset 1
```

ZWS 消融：

```bash
python scripts/transforms/strip_zwsp.py --dataset 1
python scripts/evaluation/test_after.py --dataset 1
python scripts/evaluation/test_after_nozws.py --dataset 1
python scripts/analysis/count_zws_effect.py --dataset 1
```

波动性复测：

```bash
python scripts/evaluation/test_after.py --dataset 1
python scripts/evaluation/test_after_r2.py --dataset 1
python scripts/evaluation/test_after_nozws.py --dataset 1
python scripts/evaluation/test_after_nozws_r2.py --dataset 1
python scripts/analysis/analyze_volatility.py
```

Salient-ZWS 评测：

```bash
python scripts/transforms/generate_salient.py --dataset 1
python scripts/evaluation/test_after_salient.py --dataset 1
python scripts/analysis/compare_salient.py
```

## 图表脚本

```bash
python scripts/charts/generate_charts.py
python scripts/charts/generate_zws_charts.py
python scripts/charts/generate_volatility_charts.py
python scripts/charts/chart_salient_comparison.py
```

图表统一输出到 `outputs/charts/`。

注意：这些图表脚本当前仍使用脚本内硬编码的数据数组，不会自动从 `outputs/datasets/` 动态统计最新结果。统计逻辑和图表逻辑已经分目录整理，但数据源尚未彻底打通。

## 数据约定

`data/baseline/{id}/` 只保留输入文件：

- `before.md`
- `question.md`
- `1.md`
- `2.md`
- `3.md`
- `4.md`

`outputs/datasets/{id}/` 保存生成和评测产物：

- `after.md`
- `after_nozws.md`
- `after_salient.md`
- `test_before.md`
- `test_after.md`
- `test_after_r2.md`
- `test_after_nozws.md`
- `test_after_nozws_r2.md`
- `test_after_salient.md`

这些叶子文件名本身就是实验约定的一部分。评测提示词、统计脚本和引用分析都依赖 `[after.md]`、`[after_nozws.md]`、`[after_salient.md]` 这类标识，因此不要随意重命名。

## 补充说明

- 评测脚本读取的系统提示词在 `prompts/main_prompt.md`，不是主生成流程 `scripts/pipeline/main.py` 的输入。
- 实验报告位于 `docs/report.md`。
- 中文 PDF 字体测试脚本位于 `scripts/charts/test_font_pdf.py`，输出写入 `outputs/pdf/`。
