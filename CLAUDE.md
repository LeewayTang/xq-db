# xq-db 项目规则

适用：在 `xq-db` 仓库内执行的任何任务。
优先级：用户在当前对话里的明确指令 > 本守则 > 默认行为。

在第一次工具调用之前，先过任务门，用一行写出来：

```text
[任务门] 长程：是/否 | 上下文：<xx% / 未知> | 计划：<路径 / SDD ledger / n/a> | 并行：<启用 N 槽（模型：主会话） / 不启用，理由>
```

示例：

```text
[任务门] 长程：是 | 上下文：42% | 计划：docs/superpowers/plans/2026-11-12-xqdb-p3-annotation.md | 并行：启用 1 槽（独立复审；模型：主会话）
[任务门] 长程：否 | 上下文：未知 | 计划：n/a | 并行：不启用（单文件修复，强耦合）
```

## 门 1 · 任务分级与计划落盘

### 短任务还是长程任务

满足任意一条即为长程任务：

- 跨多个工作单元，或可能跨会话；
- 需要 3 个以上步骤，或改动 2 个以上文件/目录；
- 包含“研究 → 设计 → 实现 → 验证”中的两个以上阶段；
- 需要批量处理、跑流水线、对比多个版本；
- 预计超过 30 分钟，或超过 20 次工具调用；
- 用户明确要求先给计划。

短任务（纯问答、只读查询、单文件小改）不建计划，但任务门仍要写“长程：否”和一句理由。

### 长程任务：先落盘，再动手

- **阶段级计划**：`docs/superpowers/plans/YYYY-MM-DD-<slug>.md`，包含目标、非目标、编号清单与完成证据、风险与止损线、并行决策、当前状态。
- **任务级执行**：使用 SDD ledger `.superpowers/sdd/<plan-basename>/progress.md`，每完成一项写 `Task N: complete`，偏差写 `Ruling:`。
- 计划超过 150 行或 30 项时，按交付物拆分，不要堆成一个文件。
- 方向明确时按用户授权直接推进，不必每项都等确认；方向改变、不可逆操作或需要用户决策时才停下来问。
- 汇报时逐项说状态；有未勾选项不能汇报为“完成”；降级项标 `partial` 并写原因。

## 上下文预算与 handoff

- 长程任务开始前检查上下文占用；达到 70% 或收到压缩提示时，先停在工作单元边界。
- 写 `docs/superpowers/handoffs/HANDOFF-YYYYMMDD-HHMMSS-<slug>.md`，包含：
  1. 目标与当前阶段；
  2. 已完成项及证据（提交、测试、产物路径）；
  3. 进行中、尚未落盘的工作；
  4. 已定决策；
  5. 未决问题；
  6. 下一步动作与相关文件。
- 同一提交内更新 `HANDOFF-LATEST.md` 指针，旧 handoff 标 `superseded`。
- 恢复时读 handoff 文件并用 `git log --oneline -5`、`git status --short` 校验，**不从对话摘要恢复**。

## 门 2 · 并行化评估（每次都要做）

开始执行前显式回答：是否存在 2 个以上相互独立、无共享可变状态的工作单元？

| 工作形态 | 策略 |
|---|---|
| 多个仓库/文档的独立调研 | 并发，各自给结论 |
| 多个独立脚本、实验、来源抓取 | 并发，各自独立目录 |
| 同一文件的连续编辑 | 串行 |
| 实现 + 独立复审 | 先实现，再交给 fork reviewer |
| SQLite 写入 / 索引重建 | 串行（单写者），不要并发写同一个库 |
| 需要统一术语的索引型文档 | 单 agent |

### Sub-agent 约定

- **模型必须与主会话一致（硬性）**：禁止传 `model` 参数，禁止使用写死其他模型的 agent 类型；需要严格继承时用 `subagent_type: "fork"`。
- 每个 sub-agent 有独立输出目录或明确文件边界，不共享可写文件。
- 输入用绝对路径；报告必须给“产物路径 + 验证证据”。
- 父 agent 负责合并、去重、统一口径、跑最终验证。
- 不在 sub-agent 里执行需要用户确认的破坏性操作。
- 可以用 `SendMessage` 继续已有 sub-agent，避免重复加载上下文。
- 只有用户明确要求多 agent 编排时才用 Workflow。

## 开发方式

- 严格 TDD：先写失败测试，看着它失败，再写最小实现，最后跑全量测试。
- 每个任务结束前必须：`python3 -m pytest -q` + `python3 -m ruff check src tests`，并提交。
- 提交信息结尾固定加：`Co-Authored-By: Claude Code <noreply@anthropic.com>`。
- 计划中的偏差必须写 ruling，不把决定藏在代码里。
- 只使用主会话模型；有明确下一步时不要停下来询问。

## 数据原则

- 仓库只放代码、schema、catalog、agent 定义与文档；`data/` 永不进 git。
- 语料本体通过私有仓库 `xq-corpus` 的 GitHub Release 存档；单个资产超过 2 GB 必须分片。
- 原始层只读；规范层一作品一 Markdown；索引层随时可重建。
- 不收录现代点校本、译注、学术专著、外文译本。
- 殆知阁无 LICENSE：仅本地与私有 Release 使用，不公开分发。

## 质量与真伪

- **真伪与质量是两个正交维度**。
  - `provenance_class`：contemporary / retrospective / pseudepigraphic / unknown，只作描述。
  - `quality_grade`：A/B/C/Q，才决定是否可检索。
- 托古、伪托不因“伪”降级；《列子》这类文本按 A/B 收录。
- 只有“低信息量、碎片化、损坏、伪作混入”才降为 C/Q。
- 默认检索 A+B；C 可显式开启；Q 不发布。
- 审核默认值：证据不足判 C，明确损坏才判 Q；单批 Q 率 ≥10% 冻结。
- 规则 Q 不允许被 LLM 复核升级。

## 时空约定

- 时间用带符号整数年份：`-770` = 公元前 770 年，无公元 0 年。
- 只存区间 `year_start/year_end` + `date_text` + `confidence` + `basis`，不存单一推定年份。
- 地名三层：`place` / `place_name` / `place_location`；坐标多假设并存，不覆盖、不取平均。
- 时空是标注层，不写进文件路径。

## 检索约定

- 所有检索结果必须带 `passage_id`、作品名、章节名、原文片段。
- Agent 的任何结论都必须可回指到段落。
- 全文检索用 FTS5 trigram，**按章节粒度建索引**，命中后回查具体段落；1–2 字查询回退 `LIKE`；繁简查询先转简体。
- 跨书排序按相关性；质量等级只在同一作品的不同版本之间取舍。

## 完成定义

一个任务只有同时满足以下条件才算完成：

- 计划/ledger 清单全部勾选，或有明确的 `partial` 说明；
- 声明的验证命令全部跑过，并保留输出；
- 交付物路径和复现命令写进回复；
- 没有把“检查通过”当成“需求满足”；
- 工作区干净，或明确说明哪些文件故意未提交。

## 固定位置

| 内容 | 位置 |
|---|---|
| 阶段计划 | `docs/superpowers/plans/YYYY-MM-DD-<slug>.md` |
| 设计文档 | `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md` |
| 执行 ledger | `.superpowers/sdd/<plan-basename>/progress.md` |
| handoff | `docs/superpowers/handoffs/HANDOFF-YYYYMMDD-HHMMSS-<slug>.md` |
| 语料源清单 | `catalog/sources.yaml` |
| 数据库模式 | `schemas/schema.sql` 与 `src/xqdb/schema.sql`（必须同步） |
| Agent 角色 | `agents/*.md` + `schemas/agents/*.schema.json` |
| 运行日志 | `data/runs/` |
| 知识层导出 | `data/knowledge/*.jsonl` |
| 语料 Release | 私有仓 `LeewayTang/xq-corpus` |

## 常用命令

```bash
make test
make lint
make init
make ingest
make normalize
make review
make index
make search Q="郑伯克段"
make place NAME="新郑"
make near LAT=34.4 LON=113.75 RADIUS=50
make when START=-770 END=-750
xqdb tools
xqdb agent roles
xqdb annotate run --role annotator --dry-run
xqdb review --llm --dry-run
```
