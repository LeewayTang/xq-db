# xq-db · 先秦文献库与检索流水线

收集、整理、检索与先秦有关的文本资料，最终服务于一部先秦背景长篇小说的创作。

当前阶段是**语料底座**：把公开古籍文本拉下来、统一编码、分章、审核分级，并建立可重建的中文全文索引。

## 设计原则

- **广度优先**：野史、笔记、类书、方志、注疏都收；漏掉比收错更可惜。
- **真伪与质量分开**：托古、伪托是「性质」，不是「质量」；《列子》不因晚出而降级。
- **数据与代码分离**：仓库只放代码、模式、目录与角色定义；语料走私有 Release。
- **索引可重建**：SQLite 只是派生层，随时可删可重建。
- **引用可回溯**：每条检索结果都带 `passage_id`、作品名和章节名。

## 快速开始

```bash
python3 -m pip install -e ".[dev]"

make init                      # 创建 data/ 与 SQLite 数据库
make ingest                    # 克隆殆知阁到 data/raw/daizhige/repo
make normalize                 # 原始层 -> data/corpus/*.md
make review                    # 规则审核与 A/B/C/Q 分级
make index                     # 重建 FTS5 trigram 索引
make search Q="郑伯克段"       # 检索并输出带引用的结果
make test                      # 运行测试
```

## 目录

```
catalog/        语料源清单（sources.yaml）
config/         路径配置
schemas/        SQLite DDL
src/xqdb/       入库、规范化、审核、索引、CLI
agents/         （后续）Agent 角色定义
mcp_server/     （后续）MCP 工具服务
docs/           设计文档与实施计划
tests/          测试与小型 fixture
data/           原始层 / 规范层 / 索引（不提交）
```

## 数据分层

| 层 | 位置 | 是否入库 | 说明 |
|---|---|---|---|
| L1 原始层 | `data/raw/` | 否 | 未改动的下载包，附 SHA256 |
| L2 规范层 | `data/corpus/` | 否 | 一作品一 Markdown，YAML frontmatter |
| 知识层 | `data/knowledge/` | 否 | 实体、关系、审核记录（后续） |
| 索引层 | `data/xq_index.db` | 否 | FTS5，可重建 |
| 个人层 | `data/personal/` | 否 | 笔记与灵感，永不发布 |

语料本体通过私有仓库 `xq-corpus` 的 Release 存档；本仓库公开，只含代码与文档。

## 质量分级

| 等级 | 含义 | 默认检索 |
|---|---|---|
| A | 完整、可读、信息密度高 | 是 |
| B | 有残缺或噪声，但仍有实质内容 | 是 |
| C | 低信息量：高度重复、碎片、仅有目录 | 否（可显式开启） |
| Q | 损坏：乱码、截断、不可解析 | 否 |

真伪另用 `provenance_class` 标注（contemporary / retrospective / pseudepigraphic / unknown），不影响质量等级。

## 语料来源与合规

- 殆知阁古代文献 V2.0：无 LICENSE 声明，仅本地与私有 Release 使用。
- 中文维基文库：CC BY-SA 4.0，需保留署名与相同方式共享。
- 不收录现代点校本、译注、学术专著与外文译本。

## 开发

```bash
python3 -m pytest -q
python3 -m ruff check src tests
```

设计文档：`docs/superpowers/specs/2026-11-10-xianqin-corpus-harness-design.md`
实施计划：`docs/superpowers/plans/2026-11-10-xqdb-p0-corpus-pipeline.md`
