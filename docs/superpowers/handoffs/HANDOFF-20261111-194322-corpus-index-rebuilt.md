---
handoff_id: 20261111-194322
created: 2026-11-11T19:43:22+08:00
session: 1b304fd7-9754-4d6d-9a83-5f8ae28c8527
trigger: manual
status: active
supersedes: HANDOFF-20261111-102545-p3-done-corpus-release.md
next: 决定通用分章或开始小批量标注
---

# Handoff：全量索引完成，语料与 Release 就绪

触发原因：trigger=manual

## 目标与当前阶段

先秦语料库的数据底座、检索索引与 Agent 工具链。P0–P3 已完成；全量索引重建完成；当前可稳定检索，进入“扩充语料 + 提升质量”的阶段。

## 已完成项及证据

- 语料规模：15,715 editions、38,506 sections、20,379,937 passages（`xqdb stats`）。
- 全量 FTS：37,257 章节、49,818 个块；`xqdb search` 实测 0.6–0.7 秒；增量索引 0 变化耗时 2 分钟。
- Wikisource 19 页，含清华简、郭店楚简、睡虎地秦简、竹书纪年三个版本；3.7 MB。
- 私有 Release `data-v2026.11.11` 已上传到 `LeewayTang/xq-corpus`（MANIFEST + raw 三片 + normalized）。
- 177 项测试通过，ruff 干净；`main` 已推送。
- 规则与工具：任务门、`scripts/context-usage.py`（当前约 66%）、`scripts/handoff.py`、AGENTS 符号链接。
- 关键修复：WAL 读快照导致的 31 GB 膨胀；100k 字符分块；按 200 万字符提交；`passage(section_id, idx)` 复合索引。

## 进行中（尚未落盘）

- 无。后台索引、审核、上传任务均已结束。

## 已定决策

- FTS 按章节建索引、块内上限 100k 字符、命中后回查段落。
- 全量重建约 144 分钟，是一次性成本；之后走增量哈希。
- 真伪与质量正交；规则 Q 不被 LLM 升级。
- 语料只进私有 Release；超过 2 GB 分片。

## 未决问题

- 是否实现通用分章（`卷X` / `第X回` 可靠；`一、` 噪声大）。抽样 400 部中 77 部有可靠标题；重跑约 40 分钟 + 审核 + 索引。
- 是否投入 API 预算做真实标注/复核；目前 LLM 路径只用 FakeClient 测试。
- 数据库 47 GB 中仍有大量历史空页；`VACUUM` 可能缩到约 20 GB，但需要额外磁盘与时间。
- 三个旧门户页版本（道德經、馬王堆帛書、旧竹书纪年）仍留在库中，未清理。

## 下一步动作

1. 决定通用分章；若做，先写计划与测试（`卷X`/`第X回`），再 `normalize --source ... --force-annotated` 重跑。
2. 若有 API key，先标注 20 个 chunk，抽样核对后再放量。
3. 可选：`VACUUM` 回收数据库空页；清理三个旧门户版本。

