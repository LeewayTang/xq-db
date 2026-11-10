# xq-db 项目规则

本文件是本项目的基本工作约定，后续任何会话都应遵循。

## 沟通与协作

- 与用户交流用中文；代码、标识符、提交信息用英文。
- **只使用主会话模型**。需要并行时可用 `fork` 子代理（继承主会话模型），不要自行指定 Sonnet、Opus 等其他模型。
- 用户已授权连续推进：方向明确且没有必须由用户决定的问题时，不要反复暂停确认。

## 开发方式

- 严格 TDD：先写失败测试，看着它失败，再写最小实现，最后跑全量测试。
- 每个任务结束前必须：跑全量测试 + `ruff check`，并提交。
- 提交信息结尾固定加：
  `Co-Authored-By: Claude Code <noreply@anthropic.com>`
- 计划与设计文档放在 `docs/superpowers/`；执行计划中的偏差必须记录 ruling。

## 数据原则

- 仓库只放代码、schema、catalog、agent 定义与文档；`data/` 永不进 git。
- 语料本体通过私有仓库 `xq-corpus` 的 GitHub Release 存档。
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

## 时空约定

- 时间用带符号整数年份：`-770` = 公元前 770 年，无公元 0 年。
- 只存区间 `year_start/year_end` + `date_text` + `confidence` + `basis`，不存单一推定年份。
- 地名三层：`place` / `place_name` / `place_location`；坐标多假设并存，不覆盖、不取平均。
- 时空是标注层，不写进文件路径。

## 检索约定

- 所有检索结果必须带 `passage_id`、作品名、章节名、原文片段。
- Agent 的任何结论都必须可回指到段落。
- 全文检索用 FTS5 trigram；1–2 字查询回退 `LIKE`；繁简查询先转简体。

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
```
