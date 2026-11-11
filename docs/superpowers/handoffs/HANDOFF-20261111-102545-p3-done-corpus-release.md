---
handoff_id: 20261111-102545
created: 2026-11-11T10:25:45+08:00
session: 1b304fd7-9754-4d6d-9a83-5f8ae28c8527
trigger: manual
status: superseded
superseded_by: HANDOFF-20261111-194322-corpus-index-rebuilt.md
supersedes: null
next: 确认 ws2 索引结果；决定是否做通用分章重跑
---

# Handoff：P3 完成、语料 Release 已存档

触发原因：trigger=manual

## 目标与当前阶段

先秦文献库的数据底座与 Agent 工具链。P0–P3 已上线，语料与知识层流水线可用；当前处于“扩充语料 + 提升检索与标注质量”阶段。

## 已完成项及证据

- P0/P1 语料流水线（ingest / normalize / review / index / search）：15,711 editions、38,222 sections、20.4M passages；`main` 已推送。
- P2 工具与 Agent：13 个工具、MCP server、6 个角色、带预算的无头 runner；174 项测试通过。
- P3 标注：切块、JSON Schema 校验、实体/关系/事件/时空/主题落库、JSONL 导出、LLM 复核、CLI。
- Wikisource：19 页，含清华简、郭店楚简、睡虎地秦简、竹书纪年三个版本；约 3.7 MB。
- 私有 Release `data-v2026.11.11` 已上传到 `LeewayTang/xq-corpus`：MANIFEST + raw 三片 + normalized。
- 规则与工具：`CLAUDE.md`（任务门 / handoff / 并行门）、`scripts/context-usage.py`、`scripts/handoff.py`。

## 进行中（尚未落盘）

- 后台任务 `btebk9ea9`：`review --batch ws2` 已完成（19 部，Q=0），随后 `xqdb index` 正在 47 GB 库上重建 `section_fts`，尚未结束。

## 已定决策

- FTS 按章节粒度索引，命中后回查段落。
- 真伪（provenance）与质量（quality）正交；规则 Q 不被 LLM 升级。
- 语料本体只进私有 Release；单个资产超过 2 GB 分片。
- `mcp` 钉 `<2`；同音实体/地名 ID 冲突时加短哈希后缀。
- 跨书按相关性排序，质量等级只用于同书不同版本取舍。

## 未决问题

- 是否实现通用分章（`卷X` / `第X回` 可靠，`一、` 噪声大）并重跑全库规范化。抽样 400 部中 77 部有可靠标题；重跑约需 40 分钟 + 审核 + 索引。
- 是否投入 API 预算跑真实标注/复核；目前所有 LLM 路径只用 FakeClient 测试。
- 维基文库若干页面仍是目录/消歧页（如 `老子 (帛書本)`），需要具体版本页或子页策略。

## 下一步动作

1. 确认 `btebk9ea9` 的 `xqdb index` 结束；跑 `xqdb search` 与 `xqdb stats` 复核。
2. 决定是否做通用分章；若做，先写计划与测试，再重跑 `normalize --force-annotated`。
3. 若有 API key，先小批量标注 20 个 chunk，抽样核对质量后再放量。

