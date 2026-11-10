# 先秦文献库与 Agent Harness 设计文档

- 日期：2026-11-10
- 状态：待确认
- 仓库：`xq-db`（建议托管 GitHub，公开）
- 目录：`/data/workspace/xq_db`

---

## 1. 意图

最终目标是写一部以先秦为背景的长篇小说。当前处于前期资料收集阶段。

这个项目要解决的不是"写小说"，而是**让写小说时能随时、可靠地取用海量先秦相关文本，并能沿着联想链发现素材**。

用户明确的两个优先级：

1. **广度优先**。尽可能多地收集文本，包括野史、逸闻、笔记、类书、方志、出土文献释文。质量参差、内容重复都可以接受；漏掉比收错更可惜。
2. **检索靠 AI Agent**。未来通过 Agent 做关键词检索、语义检索和联想式探索。但检索是后话，当前最重要的是语料库本身足够大。

## 2. 目标

- 建立可持续扩充、可溯源、可重建的先秦语料库。
- 每一批入库都经过常驻 Reviewer 审核，质量分级、存疑可查，而不是好坏不分地堆放。
- 语料以纯文本为主，保留出处、版本、年代、类目等元数据。
- 提供稳定的检索工具接口，供人类与 Agent 共用。
- 提供一组可复用的 Agent 角色（采集、清洗、编目、标注、研究、灵感）。
- 仓库长期可维护：clone 快、diff 可读、数据可重建。

## 3. 非目标

- 不做学术级校勘、版本对校。
- 不追求"先秦全集"的完备性，允许缺口和噪声。
- 不做多人协作的在线服务，不做 Web GUI（至少前四期不做）。
- 不收录现代人的点校本、译注、学术专著（版权与体量原因）。

## 4. 反目标（即使"能跑"也算失败）

- 语料无法溯源，不知道某段文字从哪来、经过什么处理。
- 数据与代码耦合：换分词器、换嵌入模型就得重做语料。
- 索引不可重建，或重建后结果不一致。
- 仓库因数据膨胀而无法 clone。
- Agent 输出没有出处，无法核对原文。

## 5. 已验证的环境事实

| 项 | 结果 |
|---|---|
| 工作目录 | `/data/workspace/xq_db`（当前为空） |
| 磁盘 | `/data` 约 659 GB 可用 |
| 内存 / CPU | 62 GB / 32 核 |
| Python | 3.11.6 |
| SQLite | 3.42.0，FTS5 可用，`trigram` 分词器可用 |
| 已装库 | `numpy`、`yaml` |
| 未装库 | `jieba`、`opencc`、`httpx`（需安装） |
| GitHub CLI | 已登录 `LeewayTang`，具备 `repo` 权限，SSH 协议 |
| 网络 | github.com、zh.wikisource.org、gutenberg.org 可达；**ctext.org 超时** |

## 6. 总体架构：三层分离

```
┌─────────────────────────────────────────────┐
│  L3 检索/Agent 层（可重建，不存档）           │
│  SQLite FTS5 + 向量索引 + MCP 工具 + Agent   │
└───────────────────▲─────────────────────────┘
                    │ 构建
┌───────────────────┴─────────────────────────┐
│  L2 规范层（Release 存档）                    │
│  一作品一文件、UTF-8、YAML 头、稳定 ID        │
└───────────────────▲─────────────────────────┘
                    │ 清洗转换
┌───────────────────┴─────────────────────────┐
│  L1 原始层（Release 存档，只读）              │
│  未改动的下载包，附来源 URL、时间、SHA256     │
└─────────────────────────────────────────────┘
```

**核心原则**：L1 与 L2 是资产，进入 GitHub Release；L3 是派生物，随时可删可重建，不进 git。仓库本身只放代码、模式定义、目录清单和少量测试样本。

### 为什么不用"数据库直接进 git"

- SQLite 是二进制，diff 无意义，merge 必冲突。
- 索引包含分词结果和嵌入向量，属于"特定模型 + 特定版本的产物"，不该被当作真相。
- 纯文本 + 清单才是长期可读、可迁移、可交给任何工具重建的形态。

## 7. 数据组织

### 7.1 仓库目录

```
xq_db/
├── README.md
├── pyproject.toml
├── Makefile                     # 流水线入口
├── config/
│   └── config.yaml              # 路径、模型、并发、限额
├── catalog/                     # 【进 git】目录与清单，小体积
│   ├── sources.yaml             # 语料源定义（含许可证）
│   ├── works.index.jsonl        # 作品索引（仅元数据，自动生成）
│   └── release-manifest.json    # 每次 Release 的校验和与统计
├── schemas/
│   ├── schema.sql               # SQLite DDL
│   ├── work.schema.json         # 作品元数据 JSON Schema
│   └── annotations.schema.json  # Agent 标注输出 Schema
├── src/xqdb/
│   ├── ingest/                  # 采集器：daizhige / wikisource / github
│   ├── normalize/               # 编码、分章、繁简、去重、ID
│   ├── annotate/                # 实体抽取、主题标注
│   ├── index/                   # FTS、向量、混合检索
│   ├── harness/                 # Agent 运行时、工具体、运行记录
│   ├── store/                   # SQLite 访问层
│   └── cli.py
├── mcp_server/                  # MCP 工具服务（Claude Code 可直连）
├── agents/                      # Agent 角色定义（提示词 + 工具白名单）
│   ├── librarian.md
│   ├── curator.md
│   ├── annotator.md
│   ├── researcher.md
│   └── muse.md
├── tests/
├── samples/                     # 【进 git】少量测试用文本（如左传选段）
└── data/                        # 【不进 git】L1 + L2 + L3 全部产物
    ├── raw/
    ├── corpus/
    └── xq.db
```

### 7.2 规范层文件格式

一作品一文件，Markdown + YAML frontmatter。Markdown 标题即章节层级，GitHub 上可直接阅读，diff 友好。

```markdown
---
id: w:zuozhuan
title: 春秋左氏传
title_alt: [左传, 左氏春秋]
author: 左丘明
attributed_author: 左丘明
era: 春秋
genre: 史书
source: daizhige
edition: 通行本
license: public-domain
source_path: 史部/编年类/左传.txt
char_count: 196845
---

## 隐公

### 隐公元年

三月，公及邾仪父盟于蔑，邾子克也。……

### 隐公二年
```

- 原文保留繁体、异体字、原有标点。
- 不做简繁替换写入磁盘；简体化只发生在索引阶段。
- 分章依据源文件结构；源无结构时由清洗 Agent 提议，人工抽检。

### 7.3 ID 规范

| 类型 | 格式 | 示例 |
|---|---|---|
| 作品 | `w:<拼音slug>` | `w:zuozhuan` |
| 版本 | `e:<work-slug>:<source>` | `e:zuozhuan:wikisource` |
| 章节 | `s:<edition-id>:<序号路径>` | `s:e:zuozhuan:daizhige:01-03` |
| 段落 | `p:<section-id>:<三位序号>` | `p:...:01-03:007` |
| 实体 | `ent:<type>:<slug>` | `ent:person:kongzi` |
| 标签 | `tag:<slug>` | `tag:母题:复仇` |

ID 一经分配不再更改。作品标题变化时，`work.id` 不变，只改 `title`。同一作品来自多个源时，共用一个 `work`，各自生成 `edition`。

**版本与稳定性**：`edition` 一经发布即不可变。重新清洗或重新分章会产生新版本 `e:<work>:<source>:v2`，旧 `edition` 与其段落 ID 永久保留，通过别名表指向新版本。这样已有的标注、笔记和引用不会因为重新分词而失效。

### 7.4 元数据字段

`work`：`id, title, title_alt[], author, attributed_author, era, content_era, genre, relevance, summary, canonical, first_attested`
`edition`：`id, work_id, source_id, title_in_source, path, sha256, char_count, fetched_at, license`
`section`：`id, edition_id, parent_id, idx, title, level`
`passage`：`id, section_id, idx, text, text_norm, char_count`

`era` 采用可控词表：`上古 / 夏 / 商 / 西周 / 春秋 / 战国 / 秦 / 汉 / 魏晋 / 其他`。
"先秦相关"不只看成书年代，也看**内容年代**：汉代笔记里追述三代事迹，同样入选，用 `content_era` 标记。

### 7.5 SQLite 模式（要点）

```sql
-- 目录与文本
source(id, name, url, fetched_at, license, trust, notes)
work(id, title, author, era, content_era, genre, relevance, summary, canonical)
edition(id, work_id, source_id, title_in_source, path, sha256, char_count,
        review_status, quality_grade, provenance_class)
section(id, edition_id, parent_id, idx, title, level)
passage(id, section_id, idx, text, text_norm, char_count)

-- 审核记录（常驻 Reviewer 产出）
review_finding(id, edition_id, kind, severity, evidence, reviewer, decided_at)

-- 知识层（Agent 产出，带证据）
entity(id, type, name, name_alt, description, era)
mention(id, passage_id, entity_id, surface, role, confidence)
relation(id, src_entity, dst_entity, kind, evidence_passage_id)
quotation(id, passage_id, quoted_work_id, quoted_title, confidence)  -- 类书引文/佚文

-- 时空层
place(id, canonical_name, type, description, era, notes)
place_name(id, place_id, name, name_type, period, source_passage_id, is_preferred)
place_location(id, place_id, lat, lon, precision_m, valid_from, valid_to,
               modern_province, modern_city, modern_county, modern_detail,
               hypothesis, confidence, evidence, is_primary)
place_hierarchy(child_id, parent_id, relation, period_start, period_end)
passage_place(passage_id, place_id, role, confidence)
passage_time(passage_id, year_start, year_end, confidence, basis)
event_place(event_id, place_id, role, seq)
event(id, name, date_text, year_start, year_end, place_id, summary)
event_participant(event_id, entity_id, role)
tag(id, name, category)
passage_tag(passage_id, tag_id, confidence)

-- 个人层
note(id, target_type, target_id, body, created_at)
story_seed(id, title, premise, status, created_at)
seed_passage(seed_id, passage_id)
highlight(id, passage_id, kind, note, created_at)   -- 用户手动标记
link(id, a_type, a_id, b_type, b_id, kind)   -- 通用联想链接

-- 检索层（派生）
CREATE VIRTUAL TABLE passage_fts USING fts5(
  text_norm, content='passage', content_rowid='rowid',
  tokenize='trigram'
);
CREATE TABLE embedding(passage_id, model, dim, vec BLOB);
CREATE TABLE index_meta(key, value);  -- 语料版本、模型名、构建时间
```

**分词选择**：FTS5 的 `trigram` 分词器对中文无需分词即可做子串与短语匹配，天然容忍异体字差异较小的情况；再叠加一层 `jieba` 预分词列做词级检索。两路结果用 RRF 融合。

**向量**：只对"先秦相关"子集和高亮段落建嵌入，不对三万部书全量建。模型通过 `config.yaml` 配置，接口抽象为 `Embedder`，可替换。

### 7.6 耐久层与可重建层

L3 不能笼统地说"可重建"。按成本与不可替代性拆成三类：

| 存储 | 内容 | 性质 | 处理 |
|---|---|---|---|
| `xq_index.db` | FTS、向量、统计 | 纯派生，重建成本低 | 可删，不进 git |
| `data/knowledge/*.jsonl` | 实体、提及、关系、标签、事件 | LLM 产出，成本高、不可复现 | **导出存档，纳入 Release** |
| `data/personal/` | 笔记、灵感种子、高亮 | 不可替代 | 永不发布，单独备份 |

标注范围默认只覆盖 `relevance = core` 的作品，避免对三万部书全量跑 LLM。`highlight` 是用户手动标记的段落，既可用于检索加权，也可作为后续标注的优先队列。

**相关性分层**（全量入库、分层索引）：

| relevance | 含义 | FTS | 向量 / LLM 标注 |
|---|---|---|---|
| `core` | 先秦文本及直接注疏 | 是 | 是 |
| `extended` | 后世追述、类书、野史、方志中含先秦内容 | 是 | 按需 |
| `peripheral` | 与先秦关系弱，但可能有引用价值 | 是 | 否 |
| `irrelevant` | 与先秦无关（佛藏、道藏、医藏等） | 是 | 否 |

原始层与规范层全量保留十藏，全文检索覆盖所有文本；只有 `core` 建向量、跑 LLM 标注，`extended` 按需。广度不丢，成本可控。

**注疏的定位**：杜预注、郭璞注这类传统注疏作为**独立作品**收录，用 `annotates` 关系链接到底本。注疏里有大量异说、地理考据和逸闻，是小说素材的重要来源，不能只当成原文的附属字段。

### 7.7 纪年处理

先秦纪年不可靠，不追求绝对年份：

- `date_text` 保留原文纪年（如"鲁隐公元年""周宣王三十九年"）。
- `year_start` / `year_end` 给出**区间**，允许上下浮动。
- `confidence`（high / medium / low）标记推定可信度。
- `basis` 记录换算依据（王年表、月相、碳十四等）。

**年份约定**：使用带符号整数，`-770` 表示公元前 770 年，`453` 表示公元 453 年；不存在公元 0 年。显示层负责转成"公元前 770 年"。所有时间区间按**重叠**判断，不假设精确单点。

### 7.8 空间与地名模型

先秦地名有三类复杂性：一地多名、一名多地、古今对应有争议。因此不能把地名塞进一个字段，需要分层建模：

| 表 | 作用 |
|---|---|
| `place` | 地点的规范实体 |
| `place_name` | 历史名称、别名、现代行政区名 |
| `place_location` | 坐标与定位假设，可多条并存 |
| `place_hierarchy` | 历史行政或地理隶属关系 |

```sql
place(id, canonical_name, type, description, era, notes)
place_name(id, place_id, name, name_type, period,
           source_passage_id, is_preferred)
place_location(id, place_id, lat, lon, precision_m, valid_from, valid_to,
               modern_province, modern_city, modern_county, modern_detail,
               hypothesis, confidence, evidence, is_primary)
place_hierarchy(child_id, parent_id, relation, period_start, period_end)
passage_place(passage_id, place_id, role, confidence)
passage_time(passage_id, year_start, year_end, confidence, basis)
event_place(event_id, place_id, role, seq)
```

- `name_type`：`ancient / alias / administrative / modern / variant / transliteration`。
- 同一地点允许多个坐标假设（如"鸣条"的安邑说、夏县说），用 `hypothesis` 与 `confidence` 并存，**不覆盖、不取平均**。
- `precision_m` 表示定位精度；`is_primary` 标记默认展示的假设。
- `resolve_place(name)` 同时匹配古名、别名、现代名，返回地点及其全部坐标假设。
- 检索支持 `time_range`、`place_id`、`radius_km` 三种过滤，组合时取交集。
- 时间与空间是**标注层**，不写进文件路径；同一作品的不同段落可以落在不同时空。

## 8. Agent Harness 设计

Harness = **模型 + 工具 + 循环 + 上下文管理 + 运行记录**。设计目标是：工具稳定，Agent 角色可替换。

### 8.1 工具层（MCP Server）

`mcp_server/` 暴露以下工具，Claude Code 或其他 Agent 均可调用：

| 工具 | 作用 |
|---|---|
| `search_keyword(query, filters, limit)` | 全文/短语检索，返回段落级命中 |
| `search_semantic(query, filters, k)` | 向量检索 |
| `search_hybrid(query, filters, k)` | 两路融合 |
| `get_passage(id, context)` | 取回段落及上下文 |
| `get_work(id, sections)` | 取回作品结构或全文 |
| `list_works(filter)` | 按年代/类目/来源浏览 |
| `entity_lookup(name)` | 实体、别名、提及、关系 |
| `timeline(start, end, entity)` | 纪年检索 |
| `corpus_stats()` | 语料规模与覆盖统计 |
| `note_add / note_search` | 个人笔记 |
| `seed_add / seed_list` | 灵感种子 |
| `ingest_run(source)` | 触发采集（管理权限） |

**硬性约定**：所有检索类工具必须返回 `passage_id`、作品名、章节名、原文片段。Agent 的任何结论都要能回指到段落，否则视为不可用。

### 8.2 Agent 角色

| 角色 | 职责 | 关键约束 |
|---|---|---|
| `librarian` 采集 | 发现语料源、评估许可与质量、写 `sources.yaml` | 只读网络，不直接写语料 |
| `curator` 编目 | 判定作者/年代/类目、去重、合并作品 | 必须给依据 |
| `reviewer` 审核 | 常驻质量门：来源准入、质量分级 A/B/C/Q、性质标注（不改质量等级） | 独立上下文；只打标不改文；必须附证据 |
| `annotator` 标注 | 抽取人物、地名、国名、职官、事件、主题 | 输出 JSON Schema 校验，必须带证据段落 |
| `researcher` 研究 | 多轮检索、交叉比对、写带引用的综述 | 每个论断附段落 ID |
| `muse` 灵感 | 从语料生成母题、场景、冲突、人物弧光 | 明确区分"史料"与"虚构提议" |

每个角色一个 Markdown 文件：`frontmatter`（工具白名单、输出 schema、预算）+ 提示词正文。

### 8.3 运行与可复现

- 每次 Agent 运行写入 `data/runs/<date>/<run_id>/`：输入、工具调用序列、输出、耗时、成本。
- 结构化输出一律过 JSON Schema 校验，失败重试上限可配。
- 写操作只落 SQLite，不直接改 `corpus/`；由 `xqdb export` 统一导出为规范层文件。
- 批量标注采用"抽样审计"：每批随机抽 50–100 部人工核对，错误率超阈值则调整提示词。

### 8.4 上下文策略

- 检索默认返回 200 字摘要 + 元数据，Agent 再按需 `get_passage` 展开。
- 长文本分段投喂，避免一次性塞入整部书。
- 每次任务设定 token 预算，超出时强制收敛并输出已有结论。

### 8.5 批量执行与预算

- **交互运行时**：Claude Code + MCP，用于研究、探索和少量标注。
- **批量运行时**：`xqdb agent run --role annotator --batch <id>`，走 Anthropic API，无头执行，可断点续跑。
- **预算控制**：`config.yaml` 设每批 token 上限、单次运行费用上限、全局月度上限；超限即停并写报告。
- **成本校准**：先在 100 部样本上测提示词质量与单部成本，再放大批次，避免一上来全量跑。
- 每次运行记录输入、工具调用、输出、token 与费用，落 `data/runs/`。

## 9. 质量审核与常驻 Reviewer

### 9.1 真伪与质量是两个正交维度

必须把两件事分开：

- **真伪 / 成书年代**是一种**描述**，不是评价。今本《列子》是魏晋人托古，但它作为"魏晋人对先秦的想象"信息量充足、文本完整，是高价值素材。托古文本不因"伪"而降级。
- **质量**才决定可用性。这里的"质量差"有明确所指：**没有信息量、也没有文史价值**的文本，例如高度重复的堆砌、只剩目录没有正文、断裂的残简碎片、乱码、网络伪作或无关内容混入。

因此审核产出两个独立标签：`provenance_class`（性质）和 `quality_grade`（质量）。检索默认排除低质量，但**不会因为托古而排除**。

### 9.2 维度一：史料性质（provenance_class）

| 类别 | 含义 |
|---|---|
| `contemporary` | 先秦及同时代文献 |
| `retrospective` | 后世追述先秦（汉人笔记、类书引文） |
| `pseudepigraphic` | 托古、伪托、作者归属存疑（如《列子》《孔子家语》） |
| `unknown` | 无法判定 |

这个标签只用于说明"这段材料是什么"，供创作时判断如何使用，不参与质量排序。

### 9.3 维度二：文本质量（quality_grade）

| 等级 | 含义 | 默认检索 | 进 Release |
|---|---|---|---|
| A | 完整、可读、信息密度高 | 是 | 是 |
| B | 有残缺或噪声，但仍有实质内容 | 是 | 是 |
| C | 低信息量：高度重复、碎片化、仅有目录、套话堆砌 | 否（可显式开启） | 是，单独目录 |
| Q | 损坏：乱码、截断、不可解析 | 否 | 否，仅留清单 |

判定"质量差"的具体依据，必须可量化、可复核：

- **重复度**：与库内已有文本的 n-gram 重合率超过阈值，且没有新增信息。
- **完整性**：正文缺失、仅存标题或目录、明显断简。
- **可读性**：乱码率、异常字符率、编码替换符比例。
- **信息密度**：独特实词与实体的比例，套话与模板化表述的占比。
- **来源可核验性**：无法追溯出处、无法与任何版本对应。

### 9.4 三道门

1. **来源准入**：`source.trust ∈ {primary, secondary, tertiary, unknown}`。低信任源默认进隔离区，需人工放行。
2. **质量判定**：按 9.3 的五项依据打分，定 A/B/C/Q。
3. **性质判定**：按 9.2 定 `provenance_class`，并记录判据（伪书清单、时代错置、作者归属争议）。这一步**只打标签，不影响质量等级**。

### 9.5 常驻机制

| 命令 | 时机 | 作用 |
|---|---|---|
| `xqdb review batch <id>` | 每批采集/清洗后 | 未通过不得进入索引 |
| `xqdb review release <tag>` | 发布前 | 全量复检 |
| `xqdb review watch` | 可选常驻进程 | 监听 `data/inbox/`，文件落地即审 |

报告写入 `data/reviews/<date>/`，逐条记录 `review_finding`：类型、严重度、证据、判定者、时间。判定必须附证据（具体行、具体比例、具体出处），不允许只给结论。

### 9.6 独立性约束

- Reviewer 每次运行**新开上下文**，不继承采集或标注 Agent 的推理历史，避免自我确认偏差。
- Reviewer 不修改原文，只打标；修改建议以 finding 形式提出，由清洗流程执行。
- 人工抽样按批次而非全库：每批随机抽 50–100 部，C/Q 类 100% 复核；低风险批次可无人值守，只看自动报告。误收率或误杀率超过阈值即回滚审核策略。

### 9.7 审核字段

`review_finding.kind` 词表：

- 质量类：`encoding_corrupt / truncated / high_duplication / low_information / fragmentary / unparsable / synthetic_forgery`
- 性质类：`disputed_authorship / late_composition / known_forgery / anachronism / metadata_mismatch`

### 9.8 判定粒度、默认值与门禁行为

- **粒度**：`provenance_class` 属于 `work`（书本身的性质）；`quality_grade` 属于 `edition`（这一份文件的质量）；`source.trust` 属于 `source`。同一作品的不同版本可以质量不同，但性质相同。检索默认按 `work` 去重，取质量最高的可见版本。
- **默认值**：证据不足时判 `quality_grade = C`（保留、默认隐藏），不判 Q。Q 只用于明确损坏或不可解析。"漏掉比收错更可惜"在这里落地为：宁可留下并标 C，也不要直接丢弃。
- **门禁行为**：Q 按文件隔离，不阻塞整批；只有当批次 Q 率超过 10%，或人工抽样错误率超过阈值时，才冻结该批次并回滚规则。
- **分工**：LLM Reviewer 做全量初判；人工只处理 C/Q 清单和每批抽样，不参与全量审核。
- **记录耐久性**：`review_finding` 与分级结果导出到 `data/knowledge/reviews.jsonl` 并纳入 Release。重新审核产生新记录，旧记录保留，以 `decided_at` 最新者为准，不覆盖历史。

## 10. 语料源与合规

### 10.1 优先级

| 层级 | 来源 | 说明 |
|---|---|---|
| A 批量底座 | `garychowcmu/daizhigev20` | 约 2.1 GB、三万余部，经史子集 + 野史笔记。GitHub 可达 |
| B 质量骨架 | 中文维基文库（API + dump） | 先秦核心文本，出处清楚，适合做校对基准 |
| C 专题补充 | 公开 GitHub 古籍仓库 | 二十四史、诸子、楚辞、山海经等 |
| D 出土文献 | 甲骨、金文、简帛释文 | 待调研来源，优先级低于传世文献 |
| — 放弃 | ctext.org | 本机不可达 |

### 10.2 合规原则

- 只收**古籍原文**与其公开数字转录；不收现代点校、译注、专著，也不收外文译本。
- 出土文献的现代释文若来源明确、可溯源，可收；其版权状态单独标记。
- 每个源登记：URL、抓取时间、许可证/使用条款、SHA256。
- Release 附 `MANIFEST.json`，列明全部来源与许可。
- 若某源许可不明，标记 `license: unknown` 并单独隔离，不进入默认发布包。

## 11. 流水线

```
ingest → normalize → review → catalog → annotate → index → export/release
```

- 每个阶段幂等，以内容哈希判断是否需要重跑。
- 可中断续跑，失败记录进 `data/runs/`。
- `review` 是门禁：未通过的批次不得进入索引；C 级进入索引但默认不可见，Q 级只留清单。
- `make ingest SOURCE=daizhige`、`make review`、`make index`、`make release TAG=data-v2026.11.0`。

## 12. GitHub 仓库与 Release 策略

采用双仓：

| 仓库 | 可见性 | 内容 |
|---|---|---|
| `xq-db` | 公开 | 代码、`schemas/`、`catalog/`、`agents/`、`samples/`、文档 |
| `xq-corpus` | 私有 | 语料 Release：`raw-*.tar.zst`、`normalized-*.tar.zst`、`knowledge-*.jsonl.tar.zst`、`MANIFEST.json` |

- 数据仍托管在 GitHub，但不公开分发，规避殆知阁许可不明的风险。
- 主仓 `.gitignore` 排除 `data/`、`*.db`、模型缓存、运行日志。
- Release 在本地构建（`make release`），再用 `gh release upload` 上传。GitHub Actions 拿不到被 gitignore 的 2 GB 数据；若要自动化，只能挂自托管 runner。
- 单文件控制在 2 GB 以内；必要时按藏或类目分卷。
- `xq_index.db` 是派生物，不发布；`xq_knowledge` 的 JSONL 导出必须发布。

## 13. 分期计划

| 期 | 内容 | 产出 |
|---|---|---|
| P0 | 仓库骨架、SQLite 模式、`sources.yaml`；拉取殆知阁；抓维基文库先秦核心；建立 Reviewer 骨架与三道门规则 | 可统计、已分级的语料底座 |
| P1 | 规范化、分章、繁简索引、关键词检索 CLI；review 接入流水线门禁 | `xqdb search "..."` + 审核报告 |
| P2 | MCP Server + `researcher` 角色 | Agent 可检索并引用 |
| P3 | 实体/主题标注（人物、地名、国名、事件） | 知识层与时间线 |
| P4 | 语义检索 + `muse` 角色 | 联想式探索 |
| P5 | 笔记、灵感种子、导出写作素材 | 创作工作流 |

## 14. 已做的技术决定（可由你推翻）

1. 语言用 Python 3.11，数据库用 SQLite（单文件、零运维、FTS5 + trigram 够用）。
2. 仓库公开；现代版权内容一律不入库。
3. 原文保留繁体，索引期用 OpenCC 转简并保留映射，检索同时命中简繁。
4. 嵌入只覆盖先秦相关子集，避免对三万部书全量向量化。
5. Agent 主运行时是 Claude Code + MCP；另留 `xqdb agent run` 的无头接口。
6. 语料文件用 Markdown + YAML frontmatter，而非自定义二进制或 CSV。
7. 作品 ID 用拼音 slug，天然可读、跨源稳定。
8. 真伪与质量分开：`provenance_class` 只作描述，`quality_grade` 才决定可用性；托古文本不因伪降级。
9. 只有"低信息量、碎片化、损坏、伪作混入"才降为 C/Q。
10. 双仓：代码仓 `xq-db` 公开，语料仓 `xq-corpus` 私有，数据仍以 GitHub Release 存档。
11. 十藏全量入库，用 `relevance` 分层；只有 `core` 建向量与跑 LLM 标注。
12. 批量 Agent 走无头 Anthropic API，设 token 与费用上限，先小样本校准再放量。
13. 传统注疏作为独立作品收录，用 `annotates` 关系链接底本。
14. 人工复核只覆盖异常与抽样，常规批次无人值守。
15. 时间用带符号年份（`-770` = 公元前 770 年），只存区间与置信度，不存单一推定年份。
16. 地名用 `place / place_name / place_location` 三层建模；坐标多假设并存，不覆盖、不取平均。

## 15. 风险与对策

| 风险 | 对策 |
|---|---|
| 殆知阁编码混杂（GBK/UTF-8）、OCR 错误 | 统一转码 + 乱码检测 + 低质量文件隔离 |
| 同书多版本重复 | `work` / `edition` 分离，检索按 work 去重 |
| 繁简、异体、通假导致漏检 | 索引期归一化 + trigram 子串匹配 |
| LLM 标注幻觉 | 强制证据段落 + 抽样审计 |
| 语料膨胀拖垮仓库 | 数据只进 Release，仓库只放清单 |
| 来源许可不明 | `license` 字段 + 隔离区 |
| 审核误杀有价值的素材 | 低质量才降级；托古文本按 A/B 收录，仅标注性质 |
| 把"伪"误判为"差" | 两个维度独立打分，质量判定不看真伪，只按 9.3 的五项依据 |
| Reviewer 与生成者共享盲区 | 独立上下文、每次新开会话、抽样人工复核；不使用多模型交叉（统一用主会话模型） |
