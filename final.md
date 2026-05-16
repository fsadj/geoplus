
# Final Pipeline — 实际实现文档

## 项目结构

```
final/
├── common.py               # 工具函数：文件读写、LLM客户端、URL抓取、文本清洗
├── main.py                 # CLI入口（argparse子命令）
├── adapters/
│   ├── __init__.py
│   ├── datasets.py         # 数据集管理：加载/准备/操作
│   ├── routes.py           # 路线规格（RouteSpec）
│   ├── search.py           # 搜索+参考池构建（Bocha API + 内容抓取）
│   └── evaluator.py        # 评测封装（复用 simulator pipeline）
├── pipeline/
│   ├── __init__.py
│   ├── step0_prepare.py    # 复制数据集到 final/data
│   ├── step1_reference_pool.py  # 搜索+构建参考文档池
│   ├── step2_generate_once.py   # 生成 5.2 中间稿（一次LLM调用）
│   ├── step2_build_5_3.py       # 生成 5.3 引用稿
│   ├── step3_finalize.py        # 最终定稿（after.md）
│   └── step4_evaluate.py        # 模拟评测
├── prompts/
│   └── __init__.py         # 所有提示词 + User Prompt 构建函数
├── data/datasets/{id}/     # 数据集（manifest、原文、问题等）
└── workspace/{id}/         # 工作区（参考池、中间稿、评测结果）
```

---

## 流程总览

CLI 子命令 | 对应步骤 | 说明
---|---|---
`prepare` | Step 0 | 从 `competition_match/data/{id}/` 复制 1-5.md、question.txt、test_before.md 到 `final/data/datasets/{id}/`
`reference-pool` | Step 1 | 生成问题组 → 联网搜索 → 清洗候选 → 获取正文 → 写入参考池
`generate-once` | Step 2 | 对每条启用路线，一次 LLM 调用产出一篇 5.2 锚点稿
`build-citation-drafts` | Step 2.5 | 根据 5.2 + 其他原文，生成 5.3 引用稿
`finalize` | Step 3 | 融合所有 5.3 稿，产生最终 `after.md`
`extra-once` | Step 3 备选 | 直接走 coverage_floor 路线一次生成（不经过 5.2/5.3 流程）
`evaluate` | Step 4 | 调用 simulator pipeline 评测优化后得分
`run-all` | 一键 | 按顺序执行 Step 0→1→2→2.5→3→4

---

## 步骤详解

### Step 0 — 数据准备 (`step0_prepare.py`)
- 根据 `competition/config/report5_datasets.json` 中的映射关系，将 `competition_match/data/{match_dataset_id}/` 下的 1-5.md、question.md、test_before.md 拷贝到 `final/data/datasets/{internal_dataset_id}/`
- 生成 `manifest.json` 记录映射信息

### Step 1 — 参考文档池构建 (`adapters/search.py:build_reference_pool`)

#### 1a. 生成问题组 (`generate_question_groups`)
- 调用一次 LLM（`QUESTION_SYSTEM_PROMPT`），根据五篇原文和初始引用答案生成**5个问题组**
- 每个问题组包含 `question`（搜索用核心问题）+ 2条 `aliases`（同义表述）
- 如果有原始主问题，第 1 组固定使用该主问题，另选 2 条同义表述为 aliases
- 结果写入 `question_groups.json` 和 `question.txt`

**实际输出：5个问题组（不同于原始设计中的15个问题）**

#### 1b. 联网搜索
- 对每个 question 调用博查 Web Search API，`count=5`
- 每次请求间隔 0.2 秒，结果缓存到 `workspace/shared_cache/bocha_search_{sha1}.json`
- API 地址：`https://api.bochaai.com/v1/web-search`
- API Key 必须从环境变量 `BOCHA_API_KEY` 读取（代码中无默认值，未设置时将报错）

#### 1c. AI 清洗候选结果 (`clean_candidates`)
- 调用一次 LLM（`CLEAN_RESULTS_SYSTEM_PROMPT`），根据问题组和候选结果（标题、snippet、summary），判断哪些 URL 值得抓取正文
- 保留 20-30 篇候选
- 不足 20 篇时自动补足；超过 30 篇时截断

#### 1d. 获取正文内容
- 对保留的 URL 调用 `fetch_url()`（requests + trafilatura 或 HTML 回退解析）
- 正文留存于 `workspace/{id}/reference_pool/refs/` 目录，文件名自动截取标题 slug
- 不足 200 字符的内容视为无效

**输出文件：**
- `search_payload.json` — 完整搜索结果池
- `available.json` — 可用参考文档列表
- `rejected.json` — 被过滤的候选列表
- `refs/*.md` — 正文文件

### Step 2 — 一次生成 5.2 稿 (`step2_generate_once.py`)

**路线定义（`routes.py`）:**

| 路线名称 | source_index | 说明 | 默认启用 |
|---|---|---|---|
| `after_primary_spine` | 1 | 主路线：围绕前三问沉淀一条最稳的主结论、责任链和制度依据 | ✓ |
| `after_boundary_cases` | 3 | 边界补强：专门补主线容易缺失的高价值边界、反驳、责任防火墙 | ✓ |
| `after_extra_coverage_floor` | 2 | 备选：沿用旧 coverage_floor 模式 | ✗ |

每条路线调用一次 LLM（`STEP2_SYSTEM_PROMPT`），输入包括：
- 目标原文 + 其余四篇原文
- 初始引用答案（test_before.md）
- 前三个核心问题
- 参考文档池（已清洗可用文档）

**输出：** `workspace/{id}/step2/{route_name}.md`

核心约束：
- 每篇完全只调用一次 LLM
- 不写成长综述，只沉淀可单独摘取的强句
- 保留大量独特信息锚点（具体案例、独特论证、观点、独特引用）
- 不得出现 [1]、[2]、文档1、来源2 等引用标记

### Step 2.5 — 构建 5.3 引用稿 (`step2_build_5_3.py`)

对每条路线的 5.2 稿，结合其余 4 篇未优化的原文，调用一次 LLM（`STEP2_CITATION_SYSTEM_PROMPT`）生成 5.3 引用稿。

任务：将 5.2 压成更短、更硬、主线更清楚的 5.3，围绕前三个问题组织内容，保留强句但删除长背景和低收益解释。

**输出：** `workspace/{id}/step2_citation/{route_name}.md`

### Step 3 — 最终定稿 (`step3_finalize.py`)

#### `run()` — 主流程
- 读取所有 5.3 引用稿，调用一次 LLM（`FINALIZE_SYSTEM_PROMPT`）
- 优先优化客观可见性与 AI 七维可见性得分，默认采用骨架：
  - `## 直接结论`（前 2 段直接回答问题，后接 4-6 条短硬判断句）
  - `## 关键依据`
  - `## 条件与边界`
  - `## 最终判断`
  - `## 可复用问答`（固定 6 条）
  - 可选追加 `## 核心概念辨析`
- 不得平均融合两篇 5.3，以更强者为主稿

**输出：** `data/datasets/{id}/after.md`

#### `run_extra()` — 备选路线
- 对 `after_extra_coverage_floor` 路线，不经过 5.2/5.3 流程，直接生成最终稿
- 使用 `EXTRA_COVERAGE_SYSTEM_PROMPT`

**输出：** `workspace/{id}/extra/{route_name}.md`

### Step 4 — 模拟评测 (`step4_evaluate.py`)
- 封装 `simulator.pipeline.evaluate_item_before_after()` 进行评测
- 复用 `simulator` 模块的 `SimulatorConfig` 和 `aggregate_results`
- 结果写入 `test_after.md`（评测用副本）和 `score.json`
- 支持单数据集评测和批量评测

---

## 提示词（`prompts/__init__.py`）

共 7 个系统提示词 + 对应 User Prompt 构建函数：

| 提示词 | 用途 | User Prompt Builder |
|---|---|---|
| `QUESTION_SYSTEM_PROMPT` | 生成问题组 | `build_question_user_prompt()` |
| `CLEAN_RESULTS_SYSTEM_PROMPT` | 清洗搜索结果 | `build_clean_results_user_prompt()` |
| `STEP2_SYSTEM_PROMPT` | 生成 5.2 锚点稿 | `build_step2_user_prompt()` |
| `STEP2_CITATION_SYSTEM_PROMPT` | 生成 5.3 引用稿 | `build_step2_citation_user_prompt()` |
| `FINALIZE_SYSTEM_PROMPT` | 最终定稿 | `build_finalize_user_prompt()` |
| `EXTRA_COVERAGE_SYSTEM_PROMPT` | 备选用直出路线 | `build_extra_coverage_floor_user_prompt()` |

全部系统提示词遵循以下原则：
- 只写结果、拿掉流程（直接告诉模型要什么，而非分步指令）
- 极致清晰消除歧义
- 避免元话语（"补洞""独占""前置"等）出现在最终文中

---

## LLM 客户端

复用 `competition/simulator/` 模块的 `SimulatorConfig` + `GPTMessagesClient`：
- `final/common.py:load_gpt_client()` 加载配置
- `final/common.py:call_with_retry()` 封装带重试的调用（最多 3 次，指数退避）
- 默认端点：`https://api.deepseek.com/anthropic/v1/messages`
- 默认模型：`deepseek-v4-flash`，由 `ANTHROPIC_MODEL` 环境变量覆盖

---

## 搜索方案

使用博查 Web Search API（Bocha AI）：
- 端点：`https://api.bochaai.com/v1/web-search`
- 认证：`Authorization: Bearer ${BOCHA_API_KEY}`（通过环境变量设置，未设置时将报错）
- 每次请求 5 条结果，开启 `summary: true`
- 结果缓存到 `workspace/shared_cache/`（SHA1 摘要键名）
- 请求间隔 0.2 秒

---

## 评测体系

复用 `competition/simulator/` 的完整评测流程：
- 答案生成 → 评测打分
- 七维可见性评分：相关性（relevance）、流畅性（fluency）、多样性（diversity）、独特性（uniqueness）、点击跟随可能性（click_follow）、位置显著性（subj_posi）、内容体量（subj_volu）
- 不计算 delta（只输出优化后分数）

---

## 数据集映射

定义于 `competition/config/report5_datasets.json`，每行包含：
- `match_dataset_id` — `competition_match/data/` 下的目录 ID
- `internal_dataset_id` — `final/data/datasets/` 下的目录 ID
- `legacy_dataset_id` — 沿用原实验系统的 ID
- `title` — 数据集标题
- `baseline_source_dir` — 基线源路径
- `simulator_source_file` — 模拟器 JSON 数据路径

---

## 公共工具函数（`common.py`）

| 函数 | 用途 |
|---|---|
| `read_text / read_optional_text / write_text` | 文本文件读写 |
| `write_json / load_json` | JSON 文件读写 |
| `parse_question_lines` | 解析多行文本为问题列表（去重、去除编号前缀） |
| `strip_code_fence / sanitize_output` | 清除代码围栏和引用标记 |
| `assert_no_reference_markers` | 校验不包含 [1]、文档1 等标记 |
| `fetch_url` | HTTP 抓取正文（trafilatura 或 HTMLParser 回退） |
| `short_slug` | URL/标题转短文件名 |
| `timestamp` | UTC ISO 时间戳 |
| `ParagraphExtractor` | HTML 正文提取器 |
| `normalize_whitespace` | 空白规范化 |
