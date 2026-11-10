# 先秦文献库 P2：MCP 工具服务与 Agent Harness 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把现有检索与语料能力包装成稳定的工具层，通过 MCP 暴露给 Claude Code 或其他 Agent，并提供可复现、受预算约束的无头 Agent 运行器与六个角色定义。

**Architecture:** 工具层（`xqdb.tools`）是纯函数 + `ToolContext`，不依赖 MCP；`xqdb.mcp_server` 只是把 `TOOL_SPECS` 注册到 FastMCP。Harness 层（`xqdb.harness`）负责角色加载、预算、LLM 客户端协议、运行循环与运行日志。Agent 角色是带 frontmatter 的 Markdown 文件，工具白名单与预算写在角色里，而不是写死在代码里。

**Tech Stack:** Python 3.11、SQLite（现有）、`jsonschema`、`anthropic`（仅真实运行时）、`mcp`（可选，stdio 服务）、pytest、ruff。

**Spec:** `docs/superpowers/specs/2026-11-10-xianqin-corpus-harness-design.md` 第 8、9 节

## Global Constraints

- 数据目录（`data/`）永不提交；运行日志写 `data/runs/`，不写仓库。
- 所有工具返回必须是 JSON 可序列化对象；不得返回 `sqlite3.Row`。
- 所有检索类工具必须返回 `passage_id`、`work`、`section`、`text`、`score`。
- 找不到对象时返回结构化错误 `{"error": "...", ...}`，不得抛异常给调用方。
- 工具白名单由角色 frontmatter 决定；未列出的工具不得调用。
- `ingest_run` 是管理工具，默认不注册、不进入任何角色白名单。
- 预算只减不增；任一上限触发即停止并写运行日志，状态 `budget_exceeded`。
- 测试不得访问网络、不得调用真实 LLM；使用 `FakeLLMClient` 与 fixture。
- 中文文本 UTF-8；时间戳 ISO-8601 UTC。
- 每条 git commit message 末尾必须附：`Co-Authored-By: Claude Code <noreply@anthropic.com>`。

## Review Focus

- **工具返回序列化**：任何工具结果经 `json.dumps` 不得失败。
- **不存在的 ID**：`get_passage` / `get_work` / `entity_lookup` 返回错误对象而不是崩溃。
- **空检索**：查询为空、无结果、`grades=()` 时返回 `[]` 而不是异常。
- **预算边界**：恰好达到上限时允许通过；超过一个 token/一次调用即停止。
- **工具越权**：角色未授权的工具调用必须被拒绝，且不执行。
- **运行日志完整性**：失败与预算超限也必须留下 `run.json`。
- **MCP 可选依赖**：未安装 `mcp` 时，核心工具测试仍全部通过。

---

## 文件结构

```
src/xqdb/
  tools/
    __init__.py        # 导出公开函数与 TOOL_SPECS
    context.py         # ToolContext、上下文管理器、序列化
    search.py          # search_keyword / search_semantic / search_hybrid
    corpus.py          # get_passage / get_work / list_works / corpus_stats
    knowledge.py       # entity_lookup / timeline
    personal.py        # note_add / note_search / seed_add / seed_list
    registry.py        # ToolSpec、TOOL_SPECS
    admin.py           # ingest_run（默认不注册）
  harness/
    __init__.py
    config.py          # AgentConfig
    roles.py           # AgentRole、load_roles
    budget.py          # Budget、BudgetExceeded
    client.py          # LLMClient 协议、AnthropicClient
    runner.py          # Runner、RunResult
    runlog.py          # RunLog
  mcp_server/
    __init__.py
    server.py          # create_server、main
agents/
  librarian.md
  curator.md
  reviewer.md
  annotator.md
  researcher.md
  muse.md
schemas/agents/
  librarian.schema.json
  curator.schema.json
  reviewer.schema.json
  annotator.schema.json
  researcher.schema.json
  muse.schema.json
tests/
  conftest.py            # 共享 ctx fixture
  fixtures/agents/       # 六个角色的测试夹具
  test_tools_search.py
  test_tools_corpus.py
  test_tools_knowledge.py
  test_tools_personal.py
  test_tool_registry.py
  test_roles.py
  test_budget.py
  test_runner.py
  test_mcp_server.py
```

---

### Task 1: 工具上下文与检索工具

**Files:**
- Create: `src/xqdb/tools/__init__.py`, `src/xqdb/tools/context.py`, `src/xqdb/tools/search.py`
- Create: `tests/conftest.py`
- Test: `tests/test_tools_search.py`

**Interfaces:**
- Consumes: `Config`、`connect`、`index.fts.search`、`index.fts.Hit`
- Produces: `@dataclass ToolContext(cfg, conn, embedder=None)`；`@contextmanager tool_context(root: Path | None = None)`；`hit_to_dict(hit: Hit) -> dict`；`search_keyword(ctx, query, *, limit=20, grades=("A","B"), era=None, genre=None, relevance=None) -> list[dict]`；`search_semantic(ctx, query, *, k=10, **filters) -> dict`；`search_hybrid(ctx, query, *, k=10, **filters) -> dict`；pytest fixture `ctx`

- [ ] **Step 1: 写失败测试**

```python
# tests/conftest.py
import pytest

from xqdb.config import load_config
from xqdb.index.fts import rebuild_fts
from xqdb.store.db import connect, init_db
from xqdb.tools.context import ToolContext


@pytest.fixture
def ctx(tmp_path):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "config.yaml").write_text("", encoding="utf-8")
    cfg = load_config(tmp_path)
    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    conn = connect(cfg.db_path)
    init_db(conn)
    conn.execute(
        "insert into source(id,name,url,license,trust) "
        "values('s','s','u','x','secondary')")
    conn.execute("insert into work(id,title) values('w:z','春秋左传')")
    conn.execute(
        "insert into edition(id,work_id,source_id,char_count,quality_grade) "
        "values('e:z','w:z','s',10,'A')")
    conn.execute(
        "insert into section(id,edition_id,idx,title,level) "
        "values('s:z:1','e:z',1,'隐公元年',1)")
    conn.execute(
        "insert into passage(id,section_id,idx,text,text_norm,char_count) "
        "values('p:z:1:001','s:z:1',1,'郑伯克段于鄢','郑伯克段于鄢',7)")
    conn.commit()
    rebuild_fts(conn)
    yield ToolContext(cfg=cfg, conn=conn)
    conn.close()
```

```python
# tests/test_tools_search.py
import json
from xqdb.tools.search import search_hybrid, search_keyword, search_semantic


def test_search_returns_citation_fields(ctx):
    hits = search_keyword(ctx, "郑伯克段")
    assert hits[0]["passage_id"] == "p:z:1:001"
    assert {"work", "section", "text", "score"} <= set(hits[0])


def test_results_are_json_serializable(ctx):
    json.dumps(search_keyword(ctx, "郑伯克段"), ensure_ascii=False)


def test_empty_query_returns_empty_list(ctx):
    assert search_keyword(ctx, "   ") == []


def test_semantic_without_embedder_is_explicit(ctx):
    result = search_semantic(ctx, "礼")
    assert result == {"results": [], "semantic_available": False}


def test_hybrid_falls_back_to_keyword(ctx):
    result = search_hybrid(ctx, "郑伯克段")
    assert result["mode"] == "keyword_fallback"
    assert result["results"][0]["passage_id"] == "p:z:1:001"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_tools_search.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'xqdb.tools'`

- [ ] **Step 3: 实现 context 与 search**

`ToolContext` 是 frozen dataclass，字段 `cfg, conn, embedder`。`tool_context` 用 `@contextmanager` 打开 `connect(cfg.db_path)`，结束时 `conn.close()`。`hit_to_dict` 用 `dataclasses.asdict` 并把 `score` 转 `float`。

`search_keyword` 调用 `index.fts.search`，把结果转 dict；`era/genre/relevance` 过滤在 Python 侧按 `work` 元数据做（先查 `work` 表建映射，避免改 FTS SQL）。

`search_semantic`：`ctx.embedder is None` 时返回 `{"results": [], "semantic_available": False}`；否则调用 `embedder.embed([query])`，本任务不实现向量检索，返回 `{"results": [], "semantic_available": True}`。

`search_hybrid`：语义不可用时返回 `{"results": search_keyword(...), "mode": "keyword_fallback"}`。

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_tools_search.py -v`
Expected: 5 passed

- [ ] **Step 5: 提交**

```bash
git add src/xqdb/tools tests/test_tools_search.py
git commit -m "feat: add tool context and search tools"
```

---

### Task 2: 语料浏览工具

**Files:**
- Create: `src/xqdb/tools/corpus.py`
- Test: `tests/test_tools_corpus.py`

**Interfaces:**
- Consumes: `ToolContext`
- Produces: `get_passage(ctx, passage_id: str, context: int = 1) -> dict`；`get_work(ctx, work_id: str, include_text: bool = False, max_passages: int = 2000) -> dict`；`list_works(ctx, *, era=None, genre=None, relevance=None, limit=50, offset=0) -> list[dict]`；`corpus_stats(ctx) -> dict`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_tools_corpus.py
from xqdb.tools.corpus import corpus_stats, get_passage, get_work, list_works


def test_get_passage_includes_neighbors(ctx):
    ctx.conn.execute(
        "insert into passage(id,section_id,idx,text,text_norm,char_count) "
        "values('p:z:1:002','s:z:1',2,'夏五月','夏五月',3)")
    ctx.conn.commit()
    result = get_passage(ctx, "p:z:1:001")
    assert result["work"] == "春秋左传" and result["section"] == "隐公元年"
    assert result["after"][0]["passage_id"] == "p:z:1:002"


def test_get_passage_missing_returns_error(ctx):
    assert get_passage(ctx, "p:none")["error"] == "passage not found"


def test_get_work_lists_sections(ctx):
    result = get_work(ctx, "w:z")
    assert result["title"] == "春秋左传"
    assert result["sections"][0]["title"] == "隐公元年"


def test_get_work_missing_returns_error(ctx):
    assert get_work(ctx, "w:none")["error"] == "work not found"


def test_list_works_and_stats(ctx):
    assert list_works(ctx)[0]["id"] == "w:z"
    stats = corpus_stats(ctx)
    assert stats["works"] == 1 and stats["passages"] == 1
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_tools_corpus.py -v`
Expected: FAIL，`ModuleNotFoundError`

- [ ] **Step 3: 实现**

`get_passage` 查段落 + 所属 section/edition/work，再按 `section_id` 和 `idx` 取前后各 `context` 条。返回 `{"passage": {...}, "before": [...], "after": [...], "work", "section", "work_id", "edition_id"}`。缺失返回 `{"error": "passage not found", "passage_id": ...}`。

`get_work` 查 `work` 与 `edition`，列 `section`；`include_text=True` 时按 section 顺序取段落，超过 `max_passages` 截断并返回 `"truncated": True`。

`list_works` 支持 `era/genre/relevance` 过滤与分页，返回 `id,title,author,era,genre,relevance`。

`corpus_stats` 返回 `works/editions/sections/passages`、`grades` 字典、`index_meta` 的 `schema_version`。

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_tools_corpus.py -v`
Expected: 5 passed

- [ ] **Step 5: 提交**

```bash
git add src/xqdb/tools/corpus.py tests/test_tools_corpus.py
git commit -m "feat: add corpus browsing tools"
```

---

### Task 3: 实体与时间线工具

**Files:**
- Create: `src/xqdb/tools/knowledge.py`
- Test: `tests/test_tools_knowledge.py`

**Interfaces:**
- Consumes: `ToolContext`、`space.resolve_place`、`space.passages_in_time`
- Produces: `entity_lookup(ctx, name: str) -> dict`；`timeline(ctx, start: int, end: int, *, entity: str | None = None, limit: int = 20) -> list[dict]`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_tools_knowledge.py
from xqdb.tools.knowledge import entity_lookup, timeline


def test_entity_lookup_known_and_unknown(ctx):
    ctx.conn.execute(
        "insert into entity(id,type,name,name_alt) "
        "values('ent:person:zhuang','person','郑庄公','[\"寤生\"]')")
    ctx.conn.commit()
    known = entity_lookup(ctx, "郑庄公")
    assert known["found"] is True
    assert known["entity"]["id"] == "ent:person:zhuang"
    assert entity_lookup(ctx, "不存在")["found"] is False


def test_timeline_returns_interval_and_citation(ctx):
    ctx.conn.execute(
        "insert into passage_time"
        "(passage_id,year_start,year_end,confidence,basis) "
        "values('p:z:1:001',-770,-750,'high','王年表')")
    ctx.conn.commit()
    rows = timeline(ctx, -760, -755)
    assert rows[0]["passage_id"] == "p:z:1:001"
    assert rows[0]["year_start"] == -770 and rows[0]["confidence"] == "high"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_tools_knowledge.py -v`
Expected: FAIL

- [ ] **Step 3: 实现**

`entity_lookup` 精确匹配 `entity.name` 或 `name_alt`（`LIKE '%"name"%'`），返回实体、提及数、关系列表；无结果返回 `{"found": False, "name": name}`。

`timeline` 自己写 SQL（不复用 `passages_in_time`，因为需要年份字段）：`passage_time join passage/section/edition/work`，按 `year_start <= end AND year_end >= start`，过滤 A/B，按 `year_start` 排序。`entity` 非空时 `join mention`。返回 `passage_id, work, section, text, year_start, year_end, confidence, basis`。

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_tools_knowledge.py -v`
Expected: 2 passed

- [ ] **Step 5: 提交**

```bash
git add src/xqdb/tools/knowledge.py tests/test_tools_knowledge.py
git commit -m "feat: add entity and timeline tools"
```

---

### Task 4: 个人层工具（笔记与灵感种子）

**Files:**
- Create: `src/xqdb/tools/personal.py`
- Test: `tests/test_tools_personal.py`

**Interfaces:**
- Consumes: `ToolContext`
- Produces: `note_add(ctx, target_type: str, target_id: str, body: str) -> dict`；`note_search(ctx, query: str | None = None, target_id: str | None = None, limit: int = 20) -> list[dict]`；`seed_add(ctx, title: str, premise: str, passage_ids: tuple[str, ...] = ()) -> dict`；`seed_list(ctx, status: str | None = None, limit: int = 20) -> list[dict]`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_tools_personal.py
from xqdb.tools.personal import note_add, note_search, seed_add, seed_list


def test_note_roundtrip(ctx):
    created = note_add(ctx, "passage", "p:z:1:001", "郑伯克段的叙事很紧")
    assert created["id"] > 0
    rows = note_search(ctx, query="叙事")
    assert rows[0]["target_id"] == "p:z:1:001"


def test_seed_links_passages(ctx):
    created = seed_add(ctx, "兄弟相残", "共叔段与郑庄公", ("p:z:1:001",))
    assert created["id"] > 0
    rows = seed_list(ctx)
    assert rows[0]["title"] == "兄弟相残"
    assert rows[0]["passages"] == ["p:z:1:001"]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_tools_personal.py -v`
Expected: FAIL

- [ ] **Step 3: 实现**

`note_add` 写 `note`，`created_at` 用 `datetime.now(UTC).isoformat()`。`note_search` 按 `body LIKE` 和/或 `target_id` 过滤，按 `created_at DESC`。

`seed_add` 写 `story_seed`，再逐条写 `seed_passage`；非法 passage_id 触发 `IntegrityError` 时返回 `{"error": "invalid passage_id", "passage_id": ...}` 并回滚该次插入（用 `with conn:`）。`seed_list` 左连接统计 `passages` 列表。

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_tools_personal.py -v`
Expected: 2 passed

- [ ] **Step 5: 提交**

```bash
git add src/xqdb/tools/personal.py tests/test_tools_personal.py
git commit -m "feat: add note and story seed tools"
```

---

### Task 5: 工具注册表

**Files:**
- Create: `src/xqdb/tools/registry.py`, `src/xqdb/tools/admin.py`
- Modify: `src/xqdb/tools/__init__.py`
- Test: `tests/test_tool_registry.py`

**Interfaces:**
- Consumes: 前面所有工具函数
- Produces: `@dataclass ToolSpec(name, func, description, admin=False)`；`TOOL_SPECS: dict[str, ToolSpec]`；`TOOL_NAMES: tuple[str, ...]`；`ingest_run(ctx, source: str) -> dict`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_tool_registry.py
from xqdb.tools.registry import TOOL_NAMES, TOOL_SPECS

def test_registry_covers_spec_tools():
    expected = {
        "search_keyword", "search_semantic", "search_hybrid",
        "get_passage", "get_work", "list_works",
        "entity_lookup", "timeline", "corpus_stats",
        "note_add", "note_search", "seed_add", "seed_list",
    }
    assert expected <= set(TOOL_NAMES)

def test_admin_tool_flagged():
    assert TOOL_SPECS["ingest_run"].admin is True

def test_every_spec_has_description():
    assert all(spec.description for spec in TOOL_SPECS.values())
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_tool_registry.py -v`
Expected: FAIL

- [ ] **Step 3: 实现**

`TOOL_SPECS` 显式列出每个工具，值为 `ToolSpec(name, func, description, admin)`。`ingest_run` 调用 `fetch_repo`/`enumerate_corpus`，返回 `{"source": ..., "files": n}`，标记 `admin=True`。

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_tool_registry.py -v`
Expected: 3 passed

- [ ] **Step 5: 提交**

```bash
git add src/xqdb/tools tests/test_tool_registry.py
git commit -m "feat: add tool registry with admin separation"
```

---

### Task 6: MCP Server

**Files:**
- Create: `src/xqdb/mcp_server/__init__.py`, `src/xqdb/mcp_server/server.py`
- Modify: `pyproject.toml`（增加可选依赖 `mcp`）
- Test: `tests/test_mcp_server.py`

**Interfaces:**
- Consumes: `TOOL_SPECS`、`tool_context`
- Produces: `create_server(ctx=None, *, allow_admin=False)`；`main(argv: list[str] | None = None) -> int`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_mcp_server.py
import pytest


def test_create_server_registers_non_admin_tools(ctx):
    pytest.importorskip("mcp")
    from xqdb.mcp_server.server import create_server
    server = create_server(ctx)
    names = {tool.name for tool in server._tool_manager.list_tools()}
    assert "search_keyword" in names
    assert "ingest_run" not in names


def test_admin_opt_in(ctx):
    pytest.importorskip("mcp")
    from xqdb.mcp_server.server import create_server
    server = create_server(ctx, allow_admin=True)
    names = {tool.name for tool in server._tool_manager.list_tools()}
    assert "ingest_run" in names
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_mcp_server.py -v`
Expected: FAIL（`mcp` 未安装时 skip 不算通过；先 `pip install -e ".[mcp]"`）

- [ ] **Step 3: 实现**

`pyproject.toml` 增加：

```toml
[project.optional-dependencies]
mcp = ["mcp>=1.0"]
```

`server.py` 用 `from mcp.server.fastmcp import FastMCP`；`create_server` 遍历 `TOOL_SPECS`，跳过 admin（除非 `allow_admin`），用闭包把 `ctx` 绑定到工具函数并 `mcp.add_tool(fn, name=spec.name, description=spec.description)`。`main` 解析 `--root`、`--allow-admin`，`tool_context` 打开后 `mcp.run()`。

若已安装 SDK 的 `add_tool` 签名不同，以实际 SDK 为准调整注册方式；测试只断言工具名集合。

- [ ] **Step 4: 运行测试确认通过**

Run: `pip install -e ".[mcp]" && pytest tests/test_mcp_server.py -v`
Expected: 2 passed（未安装 `mcp` 时为 2 skipped，且核心测试仍全绿）

- [ ] **Step 5: 提交**

```bash
git add src/xqdb/mcp_server pyproject.toml tests/test_mcp_server.py
git commit -m "feat: expose tools through an MCP server"
```

---

### Task 7: 角色加载与六个角色文件

**Files:**
- Create: `src/xqdb/harness/__init__.py`, `src/xqdb/harness/roles.py`
- Create: `agents/librarian.md`, `agents/curator.md`, `agents/reviewer.md`, `agents/annotator.md`, `agents/researcher.md`, `agents/muse.md`
- Create: `schemas/agents/*.schema.json`
- Create: `tests/fixtures/agents/*.md`（与真实角色同构，供只读测试使用）
- Test: `tests/test_roles.py`

**Interfaces:**
- Consumes: `TOOL_NAMES`
- Produces: `@dataclass AgentRole(name, description, tools, output_schema, max_tokens, max_tool_calls, max_cost_usd, fresh_context, prompt)`；`load_roles(agents_dir: Path, *, schemas_dir: Path | None = None) -> dict[str, AgentRole]`；`load_role(agents_dir: Path, name: str) -> AgentRole`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_roles.py
from pathlib import Path

import pytest

from xqdb.harness.roles import load_role, load_roles

AGENTS = Path(__file__).parent / "fixtures" / "agents"


def test_loads_all_six_roles():
    roles = load_roles(AGENTS)
    assert {"librarian", "curator", "reviewer",
            "annotator", "researcher", "muse"} <= set(roles)


def test_researcher_is_read_only():
    role = load_role(AGENTS, "researcher")
    assert "note_add" not in role.tools


def test_unknown_tool_rejected(tmp_path):
    (tmp_path / "agents").mkdir()
    (tmp_path / "agents" / "bad.md").write_text(
        "---\nrole: bad\ntools: [no_such_tool]\n"
        "output_schema: bad.schema.json\n"
        "budget: {max_tokens: 100, max_tool_calls: 1, max_cost_usd: 0.1}\n"
        "---\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_roles(tmp_path / "agents")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_roles.py -v`
Expected: FAIL，fixture 目录不存在且模块缺失

- [ ] **Step 3: 实现**

在 `tests/fixtures/agents/` 提供六个角色文件（与真实角色同构），测试直接指向该目录；`load_roles` 解析 `---` 之间的 YAML，校验：
- `role` 与文件名一致；
- `tools` 全部在 `TOOL_NAMES` 中；
- `budget` 三个字段均为正数；
- `output_schema` 文件存在（相对 `schemas/agents/`，测试中可指向 fixture）。

真实角色文件放仓库根 `agents/`，内容按 spec 8.2：`librarian`（采集，只读网络）、`curator`（编目）、`reviewer`（审核，独立上下文）、`annotator`（标注）、`researcher`（研究，只读检索）、`muse`（灵感，可写 seed）。每个角色正文用中文写职责、约束、输出要求；frontmatter 示例：

```yaml
---
role: researcher
description: 多轮检索并写出带引用的综述
tools: [search_keyword, search_hybrid, get_passage, get_work,
        entity_lookup, timeline, note_search]
output_schema: researcher.schema.json
budget:
  max_tokens: 40000
  max_tool_calls: 40
  max_cost_usd: 0.50
fresh_context: true
---
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_roles.py -v`
Expected: 3 passed

- [ ] **Step 5: 提交**

```bash
git add src/xqdb/harness agents schemas/agents tests/test_roles.py
git commit -m "feat: add agent role definitions and loader"
```

---

### Task 8: 预算与 LLM 客户端协议

**Files:**
- Create: `src/xqdb/harness/budget.py`, `src/xqdb/harness/client.py`
- Test: `tests/test_budget.py`

**Interfaces:**
- Consumes: 无
- Produces: `@dataclass Budget(max_tokens, max_tool_calls, max_cost_usd)`（含 `tokens`, `tool_calls`, `cost_usd`）；`BudgetExceeded`；`@dataclass ToolCall(name, arguments, id="")`；`@dataclass LLMResponse(text, tool_calls, input_tokens, output_tokens, cost_usd)`；`LLMClient` Protocol；`AnthropicClient(model, api_key=None)`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_budget.py
import pytest
from xqdb.harness.budget import Budget, BudgetExceeded

def test_charges_accumulate():
    b = Budget(max_tokens=100, max_tool_calls=2, max_cost_usd=1.0)
    b.charge_tokens(60); b.charge_tool(); b.charge_cost(0.4)
    assert b.tokens == 60 and b.tool_calls == 1

def test_limit_is_inclusive():
    b = Budget(max_tokens=10, max_tool_calls=1, max_cost_usd=0.01)
    b.charge_tokens(10)
    b.charge_tool()

def test_exceeding_any_limit_raises():
    b = Budget(max_tokens=1, max_tool_calls=1, max_cost_usd=0.01)
    with pytest.raises(BudgetExceeded):
        b.charge_tokens(2)
    with pytest.raises(BudgetExceeded):
        b.charge_tool(); b.charge_tool()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_budget.py -v`
Expected: FAIL

- [ ] **Step 3: 实现**

`Budget` 为可变 dataclass；`charge_*` 先累加再检查，超过上限抛 `BudgetExceeded(limit, used)`。`client.py` 定义 `LLMClient` Protocol 和 `AnthropicClient`：构造函数读取 `ANTHROPIC_API_KEY`，`complete` 调用 `anthropic.Anthropic().messages.create`，把 tool_use 块转成 `ToolCall`，按 usage 计算 `cost_usd`（价格表写在模块常量，可在配置覆盖）。测试不实例化 `AnthropicClient`。

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_budget.py -v`
Expected: 3 passed

- [ ] **Step 5: 提交**

```bash
git add src/xqdb/harness/budget.py src/xqdb/harness/client.py tests/test_budget.py
git commit -m "feat: add agent budget and LLM client protocol"
```

---

### Task 9: 运行器与运行日志

**Files:**
- Create: `src/xqdb/harness/runner.py`, `src/xqdb/harness/runlog.py`
- Test: `tests/test_runner.py`

**Interfaces:**
- Consumes: `AgentRole`、`Budget`、`LLMClient`、`LLMResponse`、`ToolCall`、`ToolContext`、`TOOL_SPECS`
- Produces: `@dataclass RunResult(status, output, citations, tool_calls, usage, log_path)`；`Runner(role, tool_specs, client, budget, run_dir).run(task: str) -> RunResult`；`RunLog(run_dir, run_id)` 写 `run.json`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_runner.py
import json
from pathlib import Path

from xqdb.harness.budget import Budget
from xqdb.harness.client import LLMResponse, ToolCall
from xqdb.harness.roles import AgentRole
from xqdb.harness.runner import Runner
from xqdb.tools.registry import TOOL_SPECS


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def complete(self, messages, *, tools):
        self.calls += 1
        return self.responses.pop(0)


def _role(tools=("search_keyword", "get_passage")):
    return AgentRole(
        name="researcher", description="t", tools=tools,
        output_schema=Path("none"), max_tokens=1000,
        max_tool_calls=5, max_cost_usd=1.0,
        fresh_context=True, prompt="p")


def test_runner_executes_tool_then_answers(ctx, tmp_path):
    client = FakeClient([
        LLMResponse("", [ToolCall("search_keyword",
                                  {"query": "郑伯克段"}, "t1")], 10, 5, 0.01),
        LLMResponse("结论 [p:z:1:001]", [], 20, 10, 0.02),
    ])
    result = Runner(_role(), TOOL_SPECS, client, Budget(1000, 5, 1.0),
                    tmp_path / "runs").run("查")
    assert result.status == "ok"
    assert result.citations == ["p:z:1:001"]
    log = json.loads((result.log_path / "run.json").read_text("utf-8"))
    assert log["status"] == "ok"
    assert log["tool_calls"][0]["name"] == "search_keyword"


def test_runner_rejects_unauthorized_tool(ctx, tmp_path):
    client = FakeClient([
        LLMResponse("", [ToolCall("get_work", {"work_id": "w:z"}, "t1")],
                    1, 1, 0.0),
        LLMResponse("done", [], 1, 1, 0.0),
    ])
    result = Runner(_role(("search_keyword",)), TOOL_SPECS, client,
                    Budget(1000, 5, 1.0), tmp_path / "runs").run("x")
    assert result.status == "error"
    assert "not allowed" in result.output


def test_runner_stops_on_budget(ctx, tmp_path):
    client = FakeClient([
        LLMResponse("", [ToolCall("search_keyword", {"query": "a"}, "t1")],
                    1, 1, 0.0),
        LLMResponse("", [ToolCall("search_keyword", {"query": "b"}, "t2")],
                    1, 1, 0.0),
    ])
    result = Runner(_role(), TOOL_SPECS, client, Budget(1000, 1, 1.0),
                    tmp_path / "runs").run("x")
    assert result.status == "budget_exceeded"
    assert (result.log_path / "run.json").exists()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_runner.py -v`
Expected: FAIL

- [ ] **Step 3: 实现**

`Runner.run` 流程：
1. 生成 `run_id`（UTC 时间戳 + 随机短串），建日志对象。
2. 组装 system prompt（角色正文 + 引用规则）与 user task。
3. 循环最多 `max_turns=8`：
   - `client.complete(messages, tools=role.tools)`；
   - 累计 token/cost；
   - 无 tool_calls → 输出文本，状态 `ok`；
   - 有 tool_calls → 逐个检查白名单；未授权立即 `error`；
   - 调用工具，结果转 JSON 追加为 `{"role":"tool","name":...,"content":...}`；
   - 从结果里收集 `passage_id` 到 `citations`；
   - 每次工具调用 `budget.charge_tool()`。
4. 任意 `BudgetExceeded` → 状态 `budget_exceeded`，保留已有输出。
5. 无论如何写 `run.json`，包含 role、task、messages、tool_calls、citations、usage、status。

`runlog.py` 负责建目录与原子写入（先写 `.tmp` 再 `replace`）。

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_runner.py -v`
Expected: 3 passed

- [ ] **Step 5: 提交**

```bash
git add src/xqdb/harness tests/test_runner.py
git commit -m "feat: add budgeted agent runner with run logs"
```

---

### Task 10: CLI 集成（tools / agent）

**Files:**
- Create: `src/xqdb/harness/config.py`
- Modify: `src/xqdb/cli.py`, `config/config.yaml`, `README.md`
- Test: `tests/test_cli_agent.py`

**Interfaces:**
- Consumes: `load_roles`、`Runner`、`Budget`、`TOOL_SPECS`、`load_agent_config`
- Produces: `AgentConfig(model, monthly_budget_usd, runs_dir, agents_dir, schemas_dir)`；`load_agent_config(root: Path) -> AgentConfig`；CLI 子命令 `tools`、`agent roles`、`agent run`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_cli_agent.py
import shutil
from pathlib import Path

from xqdb.cli import main

FIXTURES = Path(__file__).parent / "fixtures"


def _with_agents(tmp_path):
    shutil.copytree(FIXTURES / "agents", tmp_path / "agents")
    return tmp_path


def test_tools_list(tmp_path, capsys):
    assert main(["--root", str(tmp_path), "tools"]) == 0
    out = capsys.readouterr().out
    assert "search_keyword" in out and "ingest_run" not in out


def test_agent_roles(tmp_path, capsys):
    root = _with_agents(tmp_path)
    assert main(["--root", str(root), "agent", "roles"]) == 0
    out = capsys.readouterr().out
    assert "researcher" in out and "muse" in out


def test_agent_run_dry_run(tmp_path, capsys):
    root = _with_agents(tmp_path)
    assert main(["--root", str(root), "agent", "run", "--role", "researcher",
                 "--task", "查郑伯克段", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "budget" in out and "search_keyword" in out


def test_agent_run_without_key_reports_clearly(tmp_path, capsys):
    root = _with_agents(tmp_path)
    assert main(["--root", str(root), "agent", "run",
                 "--role", "researcher", "--task", "x"]) == 1
    assert "ANTHROPIC_API_KEY" in capsys.readouterr().out
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_cli_agent.py -v`
Expected: FAIL

- [ ] **Step 3: 实现**

`load_agent_config` 从 `config/config.yaml` 的 `agent:` 段读取 `model`、`monthly_budget_usd`、`runs_dir`、`agents_dir`、`schemas_dir`，缺省值分别为 `claude-sonnet-5-5`、`20.0`、`data/runs`、`agents`、`schemas/agents`。

CLI：
- `xqdb tools`：打印非 admin 工具名与描述。
- `xqdb agent roles`：打印角色名、工具数、预算。
- `xqdb agent run --role R --task T [--dry-run] [--max-tokens N] [--max-tool-calls N] [--max-cost F]`：dry-run 只解析角色并打印 JSON；真实运行构造 `AnthropicClient`，无 `ANTHROPIC_API_KEY` 时打印明确错误并返回 1。

README 增加 MCP 启动方式与 `agent` 用法，并说明 `mcp` 是可选依赖。

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_cli_agent.py -v`
Expected: 4 passed

- [ ] **Step 5: 提交**

```bash
git add src/xqdb/harness/config.py src/xqdb/cli.py config/config.yaml README.md tests/test_cli_agent.py
git commit -m "feat: add tools and agent CLI commands"
```

---

### Task 11: 端到端引用校验

**Files:**
- Modify: `tests/test_runner.py`
- Test: `tests/test_runner.py::test_answer_citations_exist_in_corpus`

**Interfaces:**
- Consumes: 全部
- Produces: 无新接口

- [ ] **Step 1: 写失败测试**

```python
def test_answer_citations_exist_in_corpus(ctx, tmp_path):
    from xqdb.tools.corpus import get_passage

    client = FakeClient([
        LLMResponse("", [ToolCall("search_keyword",
                                  {"query": "郑伯克段"}, "t1")], 5, 5, 0.0),
        LLMResponse("", [ToolCall("search_keyword",
                                  {"query": "郑伯克段"}, "t2")], 5, 5, 0.0),
        LLMResponse("见 [p:z:1:001]", [], 5, 5, 0.0),
    ])
    result = Runner(_role(), TOOL_SPECS, client, Budget(1000, 5, 1.0),
                    tmp_path / "runs").run("查")
    assert result.citations == ["p:z:1:001"]
    for passage_id in result.citations:
        assert get_passage(ctx, passage_id).get("error") is None
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_runner.py::test_answer_citations_exist_in_corpus -v`
Expected: FAIL（同一段落被两次检索命中时，`citations` 出现重复，断言 `["p:z:1:001"]` 失败）

- [ ] **Step 3: 实现**

运行器收集 `citations` 时去重并保持顺序；测试导入 `get_passage`。若发现引用 ID 不存在，运行器将 `status` 标为 `citation_error` 并在日志中列出无效 ID。

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_runner.py -v`
Expected: 4 passed

- [ ] **Step 5: 提交**

```bash
git add src/xqdb/harness/runner.py tests/test_runner.py
git commit -m "test: verify agent citations resolve to corpus passages"
```

---

## 自检

**1. Spec 覆盖**

| Spec 要求 | 对应任务 |
|---|---|
| 8.1 工具表（检索、取回、浏览、实体、时间线、统计、笔记、种子） | Task 1–5 |
| 8.1 `ingest_run` 管理权限 | Task 5、6 |
| 8.1 检索结果必须带引用 | Task 1、11 |
| 8.2 六个角色 | Task 7 |
| 8.2 角色 frontmatter（工具、schema、预算） | Task 7 |
| 8.3 运行日志与可复现 | Task 9 |
| 8.3 输出 Schema 校验 | Task 7、11（校验接入留待 P3 标注实现） |
| 8.4 上下文策略（摘要 + 展开） | Task 2（`get_passage` 上下文）、Task 1（limit） |
| 8.5 无头运行与预算上限 | Task 8–10 |
| §9 Reviewer 独立上下文 | Task 7 角色 frontmatter `fresh_context: true` |

**未覆盖（属于后续计划）**：真实向量检索、实体抽取质量、标注批处理、`review watch` 常驻进程、Web UI、真实 Anthropic 调用的集成测试。

**2. 步骤扫描**：每个任务均为“写测试 → 跑失败 → 实现 → 跑通过 → 提交”；无 TBD、无“适当处理”。

**3. 类型一致性**：`ToolSpec.func` 在 Task 5 定义、Task 6/9 消费；`LLMResponse/ToolCall` 在 Task 8 定义、Task 9 消费；`AgentRole.tools` 在 Task 7 定义、Task 9 白名单消费；`RunResult.log_path` 在 Task 9 产生、Task 10 CLI 消费。

**4. Review Focus 对应测试**：序列化 Task 1；缺失 ID Task 2；空检索 Task 1；预算边界 Task 8/9；越权 Task 9；日志完整性 Task 9；MCP 可选依赖 Task 6（`importorskip`）。

**5. 比例**：11 个任务，每个 5 步；代码块以测试和接口为主，实现正文只在算法不确定处给出。
