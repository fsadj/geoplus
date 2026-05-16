# GEO+ — 生成式搜索引擎优化（GSE Optimization）竞赛项目

天枢杯生成式搜索引擎优化(GEO)决赛技术方案。该项目从零构建了一套完整的 GEO 优化管线，涵盖模拟器复刻、多路线竞合、自动化生成与手动精调，最终获得冠军。

## 项目结构

```
.
├── competition/              # 主比赛代码
│   ├── simulator/            # GSE 模拟器复刻（评测管线）
│   ├── prompts/              # 系统提示词
│   ├── scripts/              # 生成、评测、分析、图表脚本
│   ├── config/               # 数据集映射配置
│   ├── docs/                 # 实验报告
│   └── outputs/              # 评测产物、图表
├── final/                    # 决赛自动化管线
│   ├── pipeline/             # 5 步管线（prepare → search → generate → finalize → evaluate）
│   ├── adapters/             # 数据管理、搜索、路线规格
│   ├── prompts/              # 全部系统提示词（7 组）
│   ├── data/datasets/{id}/   # 决赛 6 题数据集
│   └── workspace/{id}/       # 工作区（参考池、中间稿）
├── competition_match/        # 初始路线实验
│   ├── program/              # 优化与评测入口
│   └── data/{id}/            # 实验数据集
├── scripts/
│   └── generate_report_charts.py  # 复盘报告图表生成
└── .env.example              # 环境变量模板
```

## 环境变量

所有敏感信息（API 密钥、认证令牌）均通过环境变量传入，源代码中不包含任何默认密钥。

| 变量 | 说明 | 必需 |
|------|------|:----:|
| `ANTHROPIC_AUTH_TOKEN` | LLM API 认证令牌 | **是** |
| `BOCHA_API_KEY` | 博查搜索 API 密钥 | **是** |
| `ANTHROPIC_BASE_URL` | API 端点（默认 `https://api.deepseek.com/anthropic`） | 否 |
| `ANTHROPIC_MODEL` | 模型名（默认 `deepseek-v4-flash`） | 否 |
| `SIMULATOR_AUTH_TOKEN` | 模拟器令牌（备用 ANTHROPIC_AUTH_TOKEN） | 否 |

参见 `.env.example`。

## 快速开始

### 1. 安装

```bash
pip install -r competition/requirements.txt
```

### 2. 设置环境变量

```bash
export ANTHROPIC_AUTH_TOKEN="your-token-here"
export BOCHA_API_KEY="your-bocha-key-here"
```

### 3. 运行决赛管线（单数据集）

```bash
python final/main.py competition --dataset 3001
```

### 4. 运行模拟器评测

```bash
python competition/simulator/cli.py evaluate --dataset 101
python competition/simulator/cli.py batch --datasets 101,102,103
```

### 5. 编译路线对比

```bash
python competition/scripts/simulator/compare_variants.py
```

## 核心方法论

### 管线流程

```
Step 0: prepare     → 复制数据集到 final/data
Step 1: search      → LLM 生成问题组 → 博查搜索 → AI 清洗候选 → 正文抓取
Step 2: 5.2 生成    → 双路线（主路线 + 边界补强），各一条独立 LLM 调用
Step 2.5: 5.3 收束  → 每条路线压缩为更短的引用稿
Step 3: finalize    → 多路线竞合+高密度写作策略 → 最终 after.md
Step 4: evaluate    → 调用模拟器评测
```

### 内容路线（实验阶段）

经过系统对比实验验证的 6 条路线：

| 路线 | 核心思路 | 最佳表现 |
|------|---------|----------|
| coverage_floor | 最小必要引用覆盖 | avg Δ +22.06 |
| novelty_gap | 识别信息缺口独占引用 | 方差最小 |
| rebuttal | 反驳→重构信息差 | 最均衡 |
| dimensions | 维度化+粗体锚点 | 结构化最强 |
| simulator_consensus | 汇总多轮评测反馈提炼偏好 | 补充实验最优 |
| nozws（原始基线） | 默认基线 | 方差最大，已淘汰 |

关键发现：零宽字符注入（ZWS）为高方差噪声，内容本身才是主增益来源。

### 手动精调策略

决赛 6 道题在自动化管线基础之上手动精调，策略为：
- 发现评测系统比较的是"增量"（优化后 − 优化前）
- 保留原始全部内容，叠加全新信息维度
- 逐篇对照 question.txt 的子问题确保全覆盖
- 每篇叠加 4-7 个新维度（神经科学机制、退货运费分析、车龄阶段策略等）

## 关键定量结果

| 指标 | 优化前 | 优化后 | 提升 |
|------|:-----:|:-----:|:----:|
| 平均引用次数占比 | 13.6% | 52.9% | +39.4pp |
| 平均引用内容字数占比 | 18.6% | 62.7% | +44.1pp |
| 14 组数据集正向提升率 | — | 100% | 全部正向 |

详见 `competition/docs/` 下的系列实验报告。

## 项目文档

- [决赛技术复盘报告](../比赛技术复盘报告.md) — 万字完整复盘
- [主实验报告](competition/docs/report.md) — 14 组数据集基线评测
- [路线实验报告](competition/docs/report3.md) — 6 条路线对比
- [比赛数据验证报告](competition/docs/report5.md) — 5 组决赛题路线筛选
- [比赛说明](competition/docs/比赛具体信息.md) — 赛题规则

## License

MIT
