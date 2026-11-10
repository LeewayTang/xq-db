# 先秦文献库 P3：语料标注与 LLM 复核 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把规范层文本切成可复现的标注单元，用 annotator 角色抽取实体、关系、事件、时间、地名与主题，幂等写入知识层并可导出；同时提供独立的 LLM 复核路径，补充质量与性质判定。

**Architecture:** `xqdb.annotate` 负责切块、Schema 校验、落库、批量驱动与导出；`xqdb.review.llm` 复用 `Runner` 与 `reviewer` 角色做独立上下文复核。LLM 只产出结构化 JSON，落库前必须通过 Schema 与 `passage_id` 归属校验；每个 chunk 一个事务，失败不留下半条标注。标注状态写入 `annotation_state`，用于断点续跑。

**Tech Stack:** Python 3.11、SQLite（现有）、`jsonschema`、现有 `xqdb.harness`（Runner/Budget/roles）、pytest、ruff。

**Spec:** `docs/superpowers/specs/2026-11-10-xianqin-corpus-harness-design.md` 第 7.5–7.8、8、9 节

## Global Constraints

- 数据目录（`data/`）永不提交；知识层导出写 `data/knowledge/`，运行日志写 `data/runs/`。
- 标注单元必须可复现：同一库、同一 `max_chars` 产生相同 `chunk_id` 与相同顺序。
- 每条实体、关系、事件、时间、地名、主题都必须带 `passage_id` 与 `evidence`；缺失即拒绝该条。
- LLM 输出必须先通过 JSON Schema 校验；解析失败重试上限可配，超过则记录 `status='error'` 并继续下一块。
- 每个 chunk 的落库在**单个事务**内完成；任一条失败则整块回滚。
- 重复标注必须幂等：同一 chunk 重跑不产生重复 mention / passage_time / passage_place / passage_tag。
- LLM 复核不得把规则判定的 `Q` 升级；`provenance_class` 只接受 `contemporary / retrospective / pseudepigraphic / unknown`。
- 复核器每个 edition 使用**独立 Runner 与独立上下文**，不复用消息。
- 测试不得访问网络、不得调用真实 LLM；使用 `FakeLLMClient` / fixture。
- 中文文本 UTF-8；时间戳 ISO-8601 UTC；年份为带符号整数（`-770` = 公元前 770 年）。
- 每条 git commit message 末尾必须附：`Co-Authored-By: Claude Code <noreply@anthropic.com>`。

## Review Focus

- **Markdown 包裹的 JSON**：模型返回 ```json 代码块或前后带解释时必须能提取；失败不得污染数据库。
- **越界 passage_id**：payload 引用了本 chunk 之外的段落时必须拒绝该条，不得触发外键崩溃。
- **重复标注**：同一 chunk 跑两次，mention / passage_time / passage_place / passage_tag 计数不变。
- **规则 Q 保护**：规则判定为 Q 的 edition，LLM 复核不能改成 A/B/C。
- **预算中断**：批次中途超预算时，已完成的 chunk 保留，未完成的可续跑。
- **空章节 / 无段落**：不得产生空 chunk，也不得报错。
- **空输入**：没有待标注 chunk 时批量驱动返回 `processed=0`，不构造 LLM 调用。

---

## 文件结构

```
src/xqdb/
  annotate/
    __init__.py
    chunk.py            # Chunk、iter_chunks
    schema.py           # load/validate annotation JSON
    entities.py         # 实体、提及、关系落库
    events.py           # 事件、时间、地名、主题落库
    persist.py          # persist_annotation（事务 + 幂等）
    batch.py            # annotate_batch、BatchResult
    export.py           # export_knowledge
  review/
    llm.py              # review_llm_batch、LLMReviewReport
schemas/
  schema.sql            # + annotation_state（两份同步）
  agents/annotator.schema.json   # 扩展 relations/events/places/tags
  agents/reviewer.schema.json    # 保持
tests/
  test_annotate_chunk.py
  test_annotate_schema.py
  test_annotate_entities.py
  test_annotate_events.py
  test_annotate_persist.py
  test_annotate_batch.py
  test_annotate_export.py
  test_review_llm.py
  test_cli_annotate.py
  fixtures/annotations/*.json
```

---

### Task 1: 标注状态表与包骨架

**Files:**
- Modify: `schemas/schema.sql`, `src/xqdb/schema.sql`
- Create: `src/xqdb/annotate/__init__.py`
- Test: `tests/test_annotate_schema.py`（本任务先加状态表测试）

**Interfaces:**
- Consumes: `init_db`
- Produces: 表 `annotation_state(chunk_id, section_id, status, attempts, error, model, updated_at)`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_annotate_schema.py
import sqlite3

import pytest

from xqdb.store.db import connect, init_db


def test_annotation_state_table_exists(tmp_path):
    conn = connect(tmp_path / "x.db")
    init_db(conn)
    columns = {row[1] for row in conn.execute(
        "pragma table_info(annotation_state)")}
    assert {"chunk_id", "section_id", "status", "attempts",
            "error", "model", "updated_at"} <= columns


def test_annotation_state_status_is_constrained(tmp_path):
    conn = connect(tmp_path / "x.db")
    init_db(conn)
    conn.execute("insert into source(id,name,url,license,trust) "
                 "values('s','s','u','x','secondary')")
    conn.execute("insert into work(id,title) values('w','书')")
    conn.execute("insert into edition(id,work_id,source_id,char_count,quality_grade) "
                 "values('e','w','s',10,'A')")
    conn.execute("insert into section(id,edition_id,idx,title,level) "
                 "values('s1','e',1,'章',1)")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "insert into annotation_state(chunk_id,section_id,status,updated_at) "
            "values('c1','s1','bogus','now')")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_annotate_schema.py -v`
Expected: FAIL，`no such table: annotation_state`

- [ ] **Step 3: 实现 schema**

在两份 `schema.sql` 中同步加入：

```sql
CREATE TABLE IF NOT EXISTS annotation_state (
    chunk_id    TEXT PRIMARY KEY,
    section_id  TEXT NOT NULL REFERENCES section(id) ON DELETE CASCADE,
    status      TEXT NOT NULL CHECK (status IN ('ok', 'error')),
    attempts    INTEGER NOT NULL DEFAULT 0,
    error       TEXT,
    model       TEXT,
    updated_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_annotation_state_section
    ON annotation_state(section_id, status);
```

`tests/test_db.py::test_packaged_schema_matches_source` 会保证两份一致。

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_annotate_schema.py tests/test_db.py -v`
Expected: 通过

- [ ] **Step 5: 提交**

```bash
git add schemas/schema.sql src/xqdb/schema.sql src/xqdb/annotate tests/test_annotate_schema.py
git commit -m "feat: add annotation state table"
```

---

### Task 2: 确定性切块

**Files:**
- Create: `src/xqdb/annotate/chunk.py`
- Test: `tests/test_annotate_chunk.py`

**Interfaces:**
- Consumes: `passage`、`section`、`annotation_state`
- Produces: `@dataclass Chunk(chunk_id, section_id, passage_ids, text, char_count)`；`iter_chunks(conn, *, max_chars=4000, only_unannotated=False, force=False) -> Iterator[Chunk]`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_annotate_chunk.py
from xqdb.annotate.chunk import iter_chunks


def _seed(conn):
    conn.execute("insert or ignore into source(id,name,url,license,trust) "
                 "values('s','s','u','x','secondary')")
    conn.execute("insert or ignore into work(id,title) values('w','书')")
    conn.execute("insert or ignore into edition"
                 "(id,work_id,source_id,char_count,quality_grade) "
                 "values('e','w','s',100,'A')")
    for i in (1, 2):
        conn.execute("insert or ignore into section(id,edition_id,idx,title,level) "
                     "values(?,?,?,?,1)", (f"s{i}", "e", i, f"章{i}"))
    rows = [
        ("p:1:001", "s1", 1, "甲" * 10),
        ("p:1:002", "s1", 2, "乙" * 10),
        ("p:2:001", "s2", 1, "丙" * 10),
    ]
    for pid, sid, idx, text in rows:
        conn.execute("insert or ignore into passage"
                     "(id,section_id,idx,text,text_norm,char_count) "
                     "values(?,?,?,?,?,?)", (pid, sid, idx, text, text, len(text)))
    conn.commit()


def test_chunks_are_deterministic_and_bounded(ctx):
    _seed(ctx.conn)
    first = list(iter_chunks(ctx.conn, max_chars=15))
    second = list(iter_chunks(ctx.conn, max_chars=15))
    assert [c.chunk_id for c in first] == [c.chunk_id for c in second]
    assert all(c.char_count <= 15 or len(c.passage_ids) == 1 for c in first)
    assert first[0].chunk_id == "s1#001"


def test_only_unannotated_skips_ok_sections(ctx):
    _seed(ctx.conn)
    ctx.conn.execute("insert into annotation_state"
                     "(chunk_id,section_id,status,updated_at) "
                     "values('s1#001','s1','ok','now')")
    ctx.conn.commit()
    assert all(c.section_id != "s1" for c in iter_chunks(
        ctx.conn, only_unannotated=True))


def test_empty_sections_produce_no_chunks(ctx):
    ctx.conn.execute("delete from passage")
    ctx.conn.commit()
    assert list(iter_chunks(ctx.conn)) == []
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_annotate_chunk.py -v`
Expected: FAIL，`ModuleNotFoundError`

- [ ] **Step 3: 实现**

按 `section_id, idx` 顺序流式读取段落，逐段累加；超过 `max_chars` 且当前块非空时开新块。`chunk_id = f"{section_id}#{ordinal:03d}"`，序号从 1 开始。`only_unannotated=True` 时跳过已有 `status='ok'` 记录的 section（`force=True` 忽略该过滤）。空 section 不产出 chunk。

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_annotate_chunk.py -v`
Expected: 3 passed

- [ ] **Step 5: 提交**

```bash
git add src/xqdb/annotate/chunk.py tests/test_annotate_chunk.py
git commit -m "feat: add deterministic annotation chunking"
```

---

### Task 3: 标注 Schema 与校验

**Files:**
- Modify: `schemas/agents/annotator.schema.json`, `pyproject.toml`
- Create: `src/xqdb/annotate/schema.py`
- Test: `tests/test_annotate_schema.py`（追加）
- Create: `tests/fixtures/annotations/zuozhuan.json`

**Interfaces:**
- Consumes: `jsonschema`
- Produces: `AnnotationInvalid(ValueError)`；`validate_annotation(payload: dict, schema_path: Path) -> None`；`parse_annotation(text: str) -> dict`（剥离代码块并解析 JSON）

- [ ] **Step 1: 写失败测试**

```python
# tests/fixtures/annotations/zuozhuan.json
{
  "entities": [
    {"passage_id": "p:z:1:001", "type": "person", "name": "郑庄公",
     "evidence": "郑伯", "confidence": 0.9},
    {"passage_id": "p:z:1:001", "type": "person", "name": "共叔段",
     "evidence": "段", "confidence": 0.9}
  ],
  "relations": [
    {"src_name": "郑庄公", "dst_name": "共叔段", "kind": "兄弟",
     "passage_id": "p:z:1:001", "evidence": "郑伯克段", "confidence": 0.8}
  ],
  "events": [
    {"name": "郑伯克段于鄢", "passage_id": "p:z:1:001",
     "date_text": "隐公元年", "year_start": -722, "year_end": -722,
     "confidence": "medium", "basis": "王年表", "place_name": "鄢",
     "participants": ["郑庄公", "共叔段"]}
  ],
  "places": [
    {"passage_id": "p:z:1:001", "name": "鄢", "role": "battle",
     "modern_name": "河南鄢陵", "lat": 34.1, "lon": 114.2,
     "confidence": 0.6}
  ],
  "tags": [
    {"passage_id": "p:z:1:001", "name": "兄弟相残",
     "category": "母题", "confidence": 0.9}
  ]
}
```

```python
# 追加到 tests/test_annotate_schema.py
import json
from pathlib import Path
import pytest

from xqdb.annotate.schema import AnnotationInvalid, parse_annotation, validate_annotation

SCHEMA = Path("schemas/agents/annotator.schema.json")
FIXTURE = Path("tests/fixtures/annotations/zuozhuan.json")


def test_fixture_passes_schema():
    validate_annotation(json.loads(FIXTURE.read_text("utf-8")), SCHEMA)


def test_missing_passage_id_rejected():
    with pytest.raises(AnnotationInvalid):
        validate_annotation({"entities": [{"type": "person", "name": "郑庄公"}]}, SCHEMA)


def test_parse_strips_markdown_fence():
    payload = parse_annotation("```json\n{\"entities\": []}\n```")
    assert payload == {"entities": []}


def test_parse_rejects_non_json():
    with pytest.raises(AnnotationInvalid):
        parse_annotation("不是 JSON")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_annotate_schema.py -v`
Expected: FAIL，`ModuleNotFoundError: xqdb.annotate.schema`

- [ ] **Step 3: 实现**

`annotator.schema.json` 在保留 `entities` 必填的基础上增加可选数组：

```json
"relations": [{"src_name", "dst_name", "kind", "passage_id", "evidence", "confidence"}],
"events": [{"name", "passage_id", "date_text", "year_start", "year_end",
            "confidence", "basis", "place_name", "participants"}],
"places": [{"passage_id", "name", "role", "modern_name", "lat", "lon", "confidence"}],
"tags": [{"passage_id", "name", "category", "confidence"}]
```

每个数组项的 `passage_id`、`evidence` 必填（`tags` 的 `evidence` 可省略）。`validate_annotation` 用 `jsonschema.Draft202012Validator` 校验并把错误合并成 `AnnotationInvalid`。`parse_annotation` 去掉首尾空白与 ```json 围栏后 `json.loads`。`pyproject.toml` 的 `dependencies` 增加 `jsonschema>=4.20`。

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_annotate_schema.py -v`
Expected: 6 passed

- [ ] **Step 5: 提交**

```bash
git add schemas/agents/annotator.schema.json src/xqdb/annotate/schema.py tests/test_annotate_schema.py tests/fixtures/annotations
git commit -m "feat: validate annotation payloads against a JSON schema"
```

---

### Task 4: 实体、提及与关系落库

**Files:**
- Create: `src/xqdb/annotate/entities.py`
- Test: `tests/test_annotate_entities.py`

**Interfaces:**
- Consumes: `slugify_title`
- Produces: `entity_id(type: str, name: str) -> str`；`upsert_entity(conn, item: dict) -> str`；`persist_entities(conn, chunk, payload) -> dict[str, int]`；`persist_relations(conn, chunk, payload) -> int`；`resolve_or_create(conn, name: str, type: str = "unknown") -> str`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_annotate_entities.py
from xqdb.annotate.chunk import Chunk
from xqdb.annotate.entities import persist_entities, persist_relations


def _chunk():
    return Chunk("s:z:1#001", "s:z:1", ("p:z:1:001",), "郑伯克段于鄢", 6)


def test_entities_and_mentions_written(ctx):
    counts = persist_entities(ctx.conn, _chunk(), {"entities": [
        {"passage_id": "p:z:1:001", "type": "person", "name": "郑庄公",
         "name_alt": ["寤生"], "evidence": "郑伯", "confidence": 0.9}]})
    assert counts["entities"] == 1 and counts["mentions"] == 1
    row = ctx.conn.execute("select id, name_alt from entity").fetchone()
    assert row["id"] == "ent:person:zheng-zhuang-gong"


def test_relations_link_existing_entities(ctx):
    persist_entities(ctx.conn, _chunk(), {"entities": [
        {"passage_id": "p:z:1:001", "type": "person", "name": "郑庄公"},
        {"passage_id": "p:z:1:001", "type": "person", "name": "共叔段"}]})
    n = persist_relations(ctx.conn, _chunk(), {"relations": [
        {"src_name": "郑庄公", "dst_name": "共叔段", "kind": "兄弟",
         "passage_id": "p:z:1:001", "evidence": "郑伯克段", "confidence": 0.8}]})
    assert n == 1
    row = ctx.conn.execute(
        "select src_entity, dst_entity, kind from relation").fetchone()
    assert row["kind"] == "兄弟"


def test_relation_to_unknown_name_creates_stub(ctx):
    n = persist_relations(ctx.conn, _chunk(), {"relations": [
        {"src_name": "甲", "dst_name": "乙", "kind": "x",
         "passage_id": "p:z:1:001", "evidence": "e"}]})
    assert n == 1
    assert ctx.conn.execute("select count(*) from entity").fetchone()[0] == 2
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_annotate_entities.py -v`
Expected: FAIL

- [ ] **Step 3: 实现**

`entity_id = f"ent:{type}:{slugify_title(name)}"`。`upsert_entity` 用 `insert ... on conflict(id) do update set name_alt=coalesce(...)`，`name_alt` 存 JSON。`persist_entities` 先删除本 chunk 段落上的旧 `mention`，再逐条写入；`passage_id` 不在 `chunk.passage_ids` 中时跳过并计入 `rejected`。`persist_relations` 用 `resolve_or_create` 找端点（先按 name，再按 `name_alt LIKE '%"name"%'`），找不到则建 `ent:unknown:<slug>`；写入前删本 chunk 段落上的旧关系。

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_annotate_entities.py -v`
Expected: 3 passed

- [ ] **Step 5: 提交**

```bash
git add src/xqdb/annotate/entities.py tests/test_annotate_entities.py
git commit -m "feat: persist annotated entities and relations"
```

---

### Task 5: 事件、时间、地名与主题落库

**Files:**
- Create: `src/xqdb/annotate/events.py`
- Test: `tests/test_annotate_events.py`

**Interfaces:**
- Consumes: `space.place.upsert_place / add_name / add_location`
- Produces: `persist_events(conn, chunk, payload) -> int`；`persist_places(conn, chunk, payload) -> int`；`persist_tags(conn, chunk, payload) -> int`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_annotate_events.py
from xqdb.annotate.chunk import Chunk
from xqdb.annotate.events import persist_events, persist_places, persist_tags


def _chunk():
    return Chunk("s:z:1#001", "s:z:1", ("p:z:1:001",), "郑伯克段于鄢", 6)


def test_event_time_and_participants(ctx):
    assert persist_events(ctx.conn, _chunk(), {"events": [{
        "name": "郑伯克段于鄢", "passage_id": "p:z:1:001",
        "date_text": "隐公元年", "year_start": -722, "year_end": -722,
        "confidence": "medium", "basis": "王年表", "place_name": "鄢",
        "participants": ["郑庄公", "共叔段"]}]}) == 1
    assert ctx.conn.execute("select count(*) from event").fetchone()[0] == 1
    assert ctx.conn.execute("select count(*) from passage_time").fetchone()[0] == 1
    assert ctx.conn.execute(
        "select count(*) from event_participant").fetchone()[0] == 2


def test_place_with_coordinates(ctx):
    assert persist_places(ctx.conn, _chunk(), {"places": [{
        "passage_id": "p:z:1:001", "name": "鄢", "role": "battle",
        "modern_name": "河南鄢陵", "lat": 34.1, "lon": 114.2,
        "confidence": 0.6}]}) == 1
    assert ctx.conn.execute("select count(*) from place").fetchone()[0] == 1
    assert ctx.conn.execute(
        "select count(*) from place_location").fetchone()[0] == 1
    assert ctx.conn.execute(
        "select count(*) from passage_place").fetchone()[0] == 1


def test_tags_are_upserted(ctx):
    assert persist_tags(ctx.conn, _chunk(), {"tags": [{
        "passage_id": "p:z:1:001", "name": "兄弟相残",
        "category": "母题", "confidence": 0.9}]}) == 1
    assert ctx.conn.execute("select count(*) from tag").fetchone()[0] == 1
    assert ctx.conn.execute(
        "select count(*) from passage_tag").fetchone()[0] == 1
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_annotate_events.py -v`
Expected: FAIL

- [ ] **Step 3: 实现**

事件 ID：`evt:<slug(name)>:<sha1(name+passage_id)[:6]>`；写 `event`、`event_participant`（参与者按 name 解析或建 stub）、`passage_time`（仅当 `year_start`/`year_end` 同时存在），以及可选 `place_name` → `passage_place`。地名：`pl:<slug(name)>`，调用 `upsert_place/add_name/add_location`，写 `passage_place`。标签：`tag:<slug(category or '主题')>:<slug(name)>`，`insert or ignore into tag`，再写 `passage_tag`。三者在写入前都删除本 chunk 段落上的旧记录。

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_annotate_events.py -v`
Expected: 3 passed

- [ ] **Step 5: 提交**

```bash
git add src/xqdb/annotate/events.py tests/test_annotate_events.py
git commit -m "feat: persist events, times, places, and tags"
```

---

### Task 6: 幂等持久化入口

**Files:**
- Create: `src/xqdb/annotate/persist.py`
- Test: `tests/test_annotate_persist.py`

**Interfaces:**
- Consumes: `persist_entities / persist_relations / persist_events / persist_places / persist_tags`
- Produces: `persist_annotation(conn, chunk, payload, *, model: str = "unknown") -> dict[str, int]`；`record_state(conn, chunk_id, section_id, status, *, attempts=0, error=None, model=None) -> None`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_annotate_persist.py
import json
from pathlib import Path
from xqdb.annotate.chunk import Chunk
from xqdb.annotate.persist import persist_annotation, record_state

FIXTURE = Path("tests/fixtures/annotations/zuozhuan.json")


def test_persist_is_idempotent(ctx):
    chunk = Chunk("s:z:1#001", "s:z:1", ("p:z:1:001",), "郑伯克段于鄢", 6)
    payload = json.loads(FIXTURE.read_text("utf-8"))
    first = persist_annotation(ctx.conn, chunk, payload, model="fake")
    second = persist_annotation(ctx.conn, chunk, payload, model="fake")
    assert first == second
    for table in ("mention", "passage_time", "passage_place", "passage_tag"):
        assert ctx.conn.execute(f"select count(*) from {table}").fetchone()[0] > 0


def test_out_of_chunk_passage_is_rejected(ctx):
    chunk = Chunk("s:z:1#001", "s:z:1", ("p:z:1:001",), "郑伯克段于鄢", 6)
    payload = {"entities": [{"passage_id": "p:other", "type": "person",
                             "name": "某人", "evidence": "x"}]}
    counts = persist_annotation(ctx.conn, chunk, payload)
    assert counts["rejected"] == 1
    assert ctx.conn.execute("select count(*) from mention").fetchone()[0] == 0


def test_record_state_upserts(ctx):
    record_state(ctx.conn, "s:z:1#001", "s:z:1", "ok", model="fake")
    record_state(ctx.conn, "s:z:1#001", "s:z:1", "error", attempts=2, error="bad")
    row = ctx.conn.execute("select status, attempts from annotation_state").fetchone()
    assert row["status"] == "error" and row["attempts"] == 2
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_annotate_persist.py -v`
Expected: FAIL

- [ ] **Step 3: 实现**

`persist_annotation` 在一个 `with conn:` 事务中依次调用五个子模块，汇总计数并加 `rejected`。子模块只处理 `passage_id in chunk.passage_ids` 的条目。`record_state` 用 `insert ... on conflict(chunk_id) do update`，`updated_at` 用 UTC ISO。

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_annotate_persist.py -v`
Expected: 3 passed

- [ ] **Step 5: 提交**

```bash
git add src/xqdb/annotate/persist.py tests/test_annotate_persist.py
git commit -m "feat: persist annotations transactionally and idempotently"
```

---

### Task 7: 批量标注驱动

**Files:**
- Create: `src/xqdb/annotate/batch.py`
- Test: `tests/test_annotate_batch.py`

**Interfaces:**
- Consumes: `iter_chunks`、`parse_annotation`、`validate_annotation`、`persist_annotation`、`record_state`、`Runner`、`Budget`
- Produces: `@dataclass BatchResult(processed, ok, failed, rejected, stopped_reason)`；`annotate_batch(conn, role, client, budget, runs_dir, ctx, *, limit=20, max_chars=4000, dry_run=False, force=False, max_retries=1) -> BatchResult`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_annotate_batch.py
import json
from pathlib import Path
from xqdb.annotate.batch import annotate_batch
from xqdb.harness.budget import Budget
from xqdb.harness.client import LLMResponse
from xqdb.harness.roles import AgentRole
from xqdb.tools.registry import TOOL_SPECS

FIXTURE = Path("tests/fixtures/annotations/zuozhuan.json")


class FakeClient:
    def __init__(self, texts):
        self.texts = list(texts)
        self.calls = 0

    def complete(self, messages, *, tools, system=""):
        self.calls += 1
        return LLMResponse(self.texts.pop(0), [], 10, 10, 0.0)


def _role():
    return AgentRole("annotator", "t", ("get_passage",), Path("none"),
                     1000, 10, 1.0, True, "p")


def test_batch_annotates_and_records_state(ctx):
    payload = FIXTURE.read_text("utf-8")
    result = annotate_batch(
        ctx.conn, _role(), FakeClient([payload]), Budget(1000, 10, 1.0),
        ctx.cfg.data_dir / "runs", ctx)
    assert result.processed == 1 and result.ok == 1
    assert ctx.conn.execute("select count(*) from mention").fetchone()[0] > 0
    assert ctx.conn.execute("select status from annotation_state").fetchone()[0] == "ok"


def test_batch_retries_bad_json_then_records_error(ctx):
    client = FakeClient(["not json", "still not json"])
    result = annotate_batch(
        ctx.conn, _role(), client, Budget(1000, 10, 1.0),
        ctx.cfg.data_dir / "runs", ctx, max_retries=1)
    assert result.failed == 1
    assert ctx.conn.execute("select status from annotation_state").fetchone()[0] == "error"


def test_dry_run_makes_no_client_call(ctx):
    client = FakeClient([])
    result = annotate_batch(
        ctx.conn, _role(), client, Budget(1000, 10, 1.0),
        ctx.cfg.data_dir / "runs", ctx, dry_run=True)
    assert result.processed == 1 and client.calls == 0


def test_batch_resumes_past_ok_chunks(ctx):
    payload = FIXTURE.read_text("utf-8")
    annotate_batch(ctx.conn, _role(), FakeClient([payload]),
                   Budget(1000, 10, 1.0), ctx.cfg.data_dir / "runs", ctx)
    result = annotate_batch(ctx.conn, _role(), FakeClient([]),
                            Budget(1000, 10, 1.0), ctx.cfg.data_dir / "runs", ctx)
    assert result.processed == 0


def test_budget_stop_is_resumable(ctx):
    payload = FIXTURE.read_text("utf-8")
    result = annotate_batch(
        ctx.conn, _role(), FakeClient([payload]), Budget(1, 10, 1.0),
        ctx.cfg.data_dir / "runs", ctx)
    assert result.stopped_reason == "budget_exceeded"
    assert ctx.conn.execute(
        "select count(*) from annotation_state").fetchone()[0] == 0
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_annotate_batch.py -v`
Expected: FAIL

- [ ] **Step 3: 实现**

遍历 `iter_chunks(only_unannotated=True, force=force)`，最多 `limit` 块。每块构造中文任务：章节标题 + 段落 `passage_id` 与正文，要求“只输出 JSON”。`dry_run` 只打印块信息并计数，不调用 client。非 dry-run 用 `Runner(role, TOOL_SPECS, client, budget, runs_dir, ctx=ctx)` 跑一次；从 `RunResult.output` 解析并校验；成功则 `persist_annotation` + `record_state('ok')`，失败按 `max_retries` 重试，最终 `record_state('error', error=...)` 并继续。`BudgetExceeded` 时 `stopped_reason='budget_exceeded'` 并停止。

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_annotate_batch.py -v`
Expected: 5 passed

- [ ] **Step 5: 提交**

```bash
git add src/xqdb/annotate/batch.py tests/test_annotate_batch.py
git commit -m "feat: add resumable annotation batch driver"
```

---

### Task 8: 知识层导出

**Files:**
- Create: `src/xqdb/annotate/export.py`
- Test: `tests/test_annotate_export.py`

**Interfaces:**
- Consumes: 知识层表
- Produces: `export_knowledge(conn, out_dir: Path) -> dict[str, int]`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_annotate_export.py
import json
from xqdb.annotate.export import export_knowledge


def test_export_writes_jsonl(ctx, tmp_path):
    ctx.conn.execute("insert into entity(id,type,name) values('ent:person:a','person','甲')")
    ctx.conn.execute("insert into mention(passage_id,entity_id,surface) "
                     "values('p:z:1:001','ent:person:a','甲')")
    ctx.conn.commit()
    counts = export_knowledge(ctx.conn, tmp_path / "knowledge")
    assert counts["entities"] == 1 and counts["mentions"] == 1
    lines = (tmp_path / "knowledge" / "entities.jsonl").read_text("utf-8").splitlines()
    assert json.loads(lines[0])["id"] == "ent:person:a"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_annotate_export.py -v`
Expected: FAIL

- [ ] **Step 3: 实现**

导出 `entities / mentions / relations / events / event_participants / passage_times / passage_places / tags / passage_tags` 九个文件；每行一个对象，`ensure_ascii=False`，按主键排序。返回各表行数。目录不存在则创建。

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_annotate_export.py -v`
Expected: 1 passed

- [ ] **Step 5: 提交**

```bash
git add src/xqdb/annotate/export.py tests/test_annotate_export.py
git commit -m "feat: export the knowledge layer as jsonl"
```

---

### Task 9: LLM 复核路径

**Files:**
- Create: `src/xqdb/review/llm.py`
- Test: `tests/test_review_llm.py`

**Interfaces:**
- Consumes: `Runner`、`reviewer` 角色、`validate_annotation` 同风格校验
- Produces: `@dataclass LLMReviewReport(checked, updated, findings_written, stopped_reason)`；`review_llm_batch(conn, role, client_factory, budget, runs_dir, ctx, *, limit=10, apply=True) -> LLMReviewReport`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_review_llm.py
from pathlib import Path
from xqdb.harness.budget import Budget
from xqdb.harness.client import LLMResponse
from xqdb.harness.roles import AgentRole
from xqdb.review.llm import review_llm_batch


class Factory:
    def __init__(self, text):
        self.text = text
        self.created = 0

    def __call__(self):
        self.created += 1
        text = self.text

        class Client:
            def complete(self, messages, *, tools, system=""):
                return LLMResponse(text, [], 10, 10, 0.0)

        return Client()


def _role():
    return AgentRole("reviewer", "t", ("get_passage",), Path("none"),
                     1000, 5, 1.0, True, "p")


def test_llm_review_updates_grade_and_provenance(ctx):
    payload = ('{"findings": [{"edition_id": "e:z", "kind": "late_composition",'
               ' "severity": "warn", "evidence": "x", "quality_grade": "B",'
               ' "provenance_class": "retrospective"}]}')
    factory = Factory(payload)
    report = review_llm_batch(ctx.conn, _role(), factory, Budget(1000, 10, 1.0),
                              ctx.cfg.data_dir / "runs", ctx, limit=1)
    assert report.updated == 1 and report.findings_written == 1
    row = ctx.conn.execute(
        "select quality_grade, provenance_class from edition where id='e:z'").fetchone()
    assert row["quality_grade"] == "B"
    assert row["provenance_class"] == "retrospective"
    assert factory.created == 1


def test_rule_q_is_protected(ctx):
    ctx.conn.execute("update edition set quality_grade='Q' where id='e:z'")
    ctx.conn.commit()
    payload = ('{"findings": [{"edition_id": "e:z", "kind": "late_composition",'
               ' "severity": "warn", "evidence": "x", "quality_grade": "A"}]}')
    review_llm_batch(ctx.conn, _role(), Factory(payload), Budget(1000, 10, 1.0),
                     ctx.cfg.data_dir / "runs", ctx, limit=1)
    assert ctx.conn.execute(
        "select quality_grade from edition where id='e:z'").fetchone()[0] == "Q"


def test_invalid_json_records_no_findings(ctx):
    report = review_llm_batch(ctx.conn, _role(), Factory("not json"),
                              Budget(1000, 10, 1.0),
                              ctx.cfg.data_dir / "runs", ctx, limit=1)
    assert report.findings_written == 0
    assert ctx.conn.execute(
        "select count(*) from review_finding").fetchone()[0] == 0
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_review_llm.py -v`
Expected: FAIL

- [ ] **Step 3: 实现**

按 `edition.id` 顺序取 `limit` 个 edition（优先 `review_status='reviewed'`）。每个 edition 新建 `Runner` 与 `client_factory()`，任务文本包含作品名、长度、前 2000 字与要求输出的 JSON 结构。解析并校验 `findings`：只接受 `edition_id` 与当前 edition 相同的条目；写 `review_finding`（`reviewer='llm'`）。`apply=True` 时：`provenance_class` 只在白名单内更新；`quality_grade` 只在当前不是 `Q` 且新值在 `A/B/C` 时更新。解析失败不写任何记录。复核 payload 用 `schemas/agents/reviewer.schema.json` 经 `jsonschema` 校验。

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_review_llm.py -v`
Expected: 3 passed

- [ ] **Step 5: 提交**

```bash
git add src/xqdb/review/llm.py tests/test_review_llm.py
git commit -m "feat: add independent LLM review pass"
```

---

### Task 10: CLI 集成与端到端验证

**Files:**
- Modify: `src/xqdb/cli.py`, `README.md`
- Test: `tests/test_cli_annotate.py`

**Interfaces:**
- Consumes: `annotate_batch`、`export_knowledge`、`review_llm_batch`、`load_agent_config`、`load_roles`
- Produces: 子命令 `annotate run`、`annotate export`；`review --llm`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_cli_annotate.py
import shutil
from pathlib import Path

from xqdb.cli import main

ROOT = Path(__file__).resolve().parents[1]


def _with_agents(tmp_path):
    shutil.copytree(ROOT / "agents", tmp_path / "agents")
    shutil.copytree(ROOT / "schemas" / "agents", tmp_path / "schemas" / "agents")
    return tmp_path


def test_annotate_dry_run(tmp_path, capsys):
    root = _with_agents(tmp_path)
    assert main(["--root", str(root), "annotate", "run",
                 "--role", "annotator", "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "chunk" in out


def test_annotate_export_without_data(tmp_path, capsys):
    assert main(["--root", str(tmp_path), "annotate", "export"]) == 0
    assert (tmp_path / "data" / "knowledge" / "entities.jsonl").exists()


def test_review_llm_dry_run(tmp_path, capsys):
    assert main(["--root", str(tmp_path), "review", "--llm", "--dry-run"]) == 0
    assert "would review" in capsys.readouterr().out
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_cli_annotate.py -v`
Expected: FAIL，`invalid choice: 'annotate'`

- [ ] **Step 3: 实现**

`annotate` 子命令含 `run`（`--role`、`--limit`、`--chunk-size`、`--dry-run`、`--force`）与 `export`（`--out`）。`run` 需要 `ANTHROPIC_API_KEY`（dry-run 除外），构造 `Budget`、`AnthropicClient`、`Runner`，打印 `processed/ok/failed/rejected`。`export` 调 `export_knowledge` 并打印计数。`review` 增加 `--llm`、`--limit`、`--dry-run`；`--llm --dry-run` 只统计待复核 edition 并打印 `would review N`。README 增加 P3 用法。

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_cli_annotate.py -v`
Expected: 3 passed

- [ ] **Step 5: 提交**

```bash
git add src/xqdb/cli.py README.md config/config.yaml tests/test_cli_annotate.py
git commit -m "feat: add annotate and LLM review CLI commands"
```

---

## 自检

**1. Spec 覆盖**

| Spec 要求 | 对应任务 |
|---|---|
| 7.5 实体/提及/关系/事件/时间/地名/标签表落库 | Task 4、5 |
| 7.6 LLM 产出导出 JSONL、个人层不发布 | Task 8 |
| 7.7 区间时间、置信度、原文纪年 | Task 5 |
| 7.8 地名分层、坐标多假设、passage_place | Task 5 |
| 8.2 annotator 输出 Schema | Task 3 |
| 8.3 结构化输出校验、失败重试、抽样审计 | Task 3、7 |
| 8.5 批量执行、预算、断点续跑 | Task 7、10 |
| 9.2/9.3 质量与性质正交、LLM 只补充不覆盖 Q | Task 9 |
| 9.6 Reviewer 独立上下文 | Task 9（每个 edition 新建 Runner） |

**未覆盖（属于后续计划）**：向量检索、标注质量的人工抽样工具、`review watch` 常驻进程、Web UI。

**2. 步骤扫描**：每个任务均为“写测试 → 跑失败 → 实现 → 跑通过 → 提交”；无 TBD，无“适当处理”。

**3. 类型一致性**：`Chunk` 在 Task 2 定义并被 Task 4–7 消费；`persist_annotation` 在 Task 6 定义并被 Task 7 消费；`BatchResult` 在 Task 7 定义并被 Task 10 消费；`LLMReviewReport` 在 Task 9 定义并被 Task 10 消费。

**4. Review Focus 对应测试**：Markdown 围栏 → Task 3；越界 passage_id → Task 6；重复标注 → Task 6；规则 Q 保护 → Task 9；预算中断 → Task 7（`stopped_reason`）；空章节 → Task 2；空输入 → Task 7。

**5. 比例**：10 个任务，每个 5 步；代码块只含测试与关键接口，不含完整实现正文。
