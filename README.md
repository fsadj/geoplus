# Workspace Overview

这个仓库现在拆分为两个并列入口，并额外保留一层历史归档。

- `competition/`：比赛/GEO/模拟评测子项目。这里包含当前可运行的生成、评测、分析、图表与 simulator 复刻链路。
- `main-project/`：原项目主入口占位区，用于承接与比赛无关的长期代码和文档。
- `archive/`：历史脚本、临时产物和冻结材料，只读归档，不作为默认工作流入口。

## Which Entry To Use

如果你要继续比赛相关工作，请直接从 [competition/README.md](competition/README.md) 开始。

如果你要整理或恢复原项目主线，请从 [main-project/README.md](main-project/README.md) 开始。

## Current Status

这次重组采用了真实物理迁移：原先根目录下的比赛运行资产已经整体移入 `competition/`，以保留其内部目录结构、脚本入口和路径约定。根目录不再承担比赛流程说明，只保留总导航职责。

## Archive Policy

`archive/` 中只保留 legacy 包装脚本、一次性测试产物、临时 JSON 和不再参与当前默认流程的冻结材料。当前仍被 `competition/` 内脚本或文档引用的文件，不会放入归档。
