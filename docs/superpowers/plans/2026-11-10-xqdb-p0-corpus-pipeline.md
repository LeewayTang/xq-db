# 先秦文献库 P0/P1：语料流水线与全文检索 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立可运行的语料流水线：拉取殆知阁与维基文库先秦文本，规范化、审核分级、建立 SQLite 全文索引，并通过 `xqdb` CLI 检索。

**Architecture:** 原始层（`data/raw/`）只读保留；规范层（`data/corpus/`）一作品一 Markdown；索引层（`data/xq_index.db`）由规范层重建。每个阶段幂等，以 SHA256 判重，审核门禁按文件隔离。

**Tech Stack:** Python 3.11、SQLite 3.42（FTS5 trigram）、PyYAML、pypinyin、OpenCC、zstandard、httpx、pytest、ruff。

**Spec:** `docs/superpowers/specs/2026-11-10-xianqin-corpus-harness-design.md`

## Global Constraints

- Python 3.11；SQLite ≥ 3.42，必须支持 `fts5` 与 `tokenize='trigram'`。
- 数据目录（`data/`）永不提交；`.gitignore` 必须覆盖。
- 所有 `id` 一经生成不再更改；重新清洗产生新 `edition` 版本。
- 所有检索结果必须包含 `passage_id`、作品名、章节名、原文片段。
- 时间戳统一 ISO-8601 UTC（`datetime.now(timezone.utc).isoformat()`）。
- 测试不得访问网络；所有外部输入使用 fixture。
- 中文文本一律 UTF-8 存储；繁体保留，简体化只发生在 `text_norm`。
- 审核默认值：证据不足判 `C`，明确损坏才判 `Q`。
- 单批 Q 率 > 10% 时门禁阻塞。
- 每条 git commit message 末尾必须附：`Co-Authored-By: Claude Code <noreply@anthropic.com>`。

## Review Focus

- **GB18030 输入**：源文件不是 UTF-8 时必须正确转码，不得出现乱码或替换符。
- **无 `◇` 章节标记的文件**：仍须生成一个合法的单章节作品，而不是空作品。
- **1–2 字查询**：FTS5 trigram 对短查询无结果，必须回退到 `LIKE`。
- **繁体查询 / 简体索引**：查询“鄭伯克段”必须命中索引中的“郑伯克段”。
- **同书多版本**：检索结果按 `work` 去重，默认只显示质量最高的可见版本。
- **空文件 / 仅目录文件**：必须判为 C 或 Q，且不使整批崩溃。

---

## 文件结构

```
pyproject.toml
Makefile
config/config.yaml
schemas/schema.sql
catalog/sources.yaml
src/xqdb/
  __init__.py            # 版本号
  config.py              # 路径与配置加载
  cli.py                 # argparse 入口
  store/db.py            # 连接、建表、事务
  store/models.py        # dataclass
  normalize/ids.py       # 稳定 ID
  normalize/encoding.py  # 编码检测与转码
  normalize/parse.py     # 文本解析、分章
  normalize/pipeline.py  # raw -> corpus
  normalize/simplify.py  # 繁简归一（索引用）
  ingest/daizhige.py     # 殆知阁采集
  ingest/wikisource.py   # 维基文库采集
  review/rules.py        # 规则审核 + simhash
  review/pipeline.py     # 批次审核与门禁
  index/fts.py           # FTS 重建与检索
  catalog/build.py       # works.index.jsonl 导出
  release.py             # Release 打包
tests/
  fixtures/              # 小型语料样本
  test_*.py
```

---

### Task 1: 项目骨架、配置与 CLI 入口

**Files:**
- Create: `pyproject.toml`, `Makefile`, `config/config.yaml`, `.gitignore`
- Create: `src/xqdb/__init__.py`, `src/xqdb/config.py`, `src/xqdb/cli.py`
- Test: `tests/test_config.py`, `tests/test_cli.py`

**Interfaces:**
- Consumes: 无
- Produces: `Config`（字段 `root, data_dir, raw_dir, corpus_dir, knowledge_dir, db_path, config_path`）；`load_config(root: Path | None = None) -> Config`；`main(argv: list[str] | None = None) -> int`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_config.py
from pathlib import Path
from xqdb.config import load_config

def test_load_config_defaults(tmp_path: Path):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "config.yaml").write_text("", encoding="utf-8")
    cfg = load_config(tmp_path)
    assert cfg.data_dir == tmp_path / "data"
    assert cfg.db_path == tmp_path / "data" / "xq_index.db"
    assert cfg.corpus_dir == tmp_path / "data" / "corpus"

def test_load_config_overrides(tmp_path: Path):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "config.yaml").write_text(
        "db_path: custom/index.db\n", encoding="utf-8")
    cfg = load_config(tmp_path)
    assert cfg.db_path == tmp_path / "custom" / "index.db"
```

```python
# tests/test_cli.py
from xqdb.cli import main

def test_version(capsys):
    assert main(["version"]) == 0
    assert "xqdb" in capsys.readouterr().out
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_config.py tests/test_cli.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'xqdb'`

- [ ] **Step 3: 实现骨架**

`pyproject.toml` 使用 setuptools，`src` 布局，依赖与 `[project.scripts] xqdb = "xqdb.cli:main"` 按 Tech Stack 填写。`config.py` 用 `pathlib` + `yaml.safe_load`，相对路径一律相对 `root` 解析。`cli.py` 用 `argparse`，先只实现 `version` 子命令，返回 0。

`.gitignore` 必须包含：

```
data/
*.db
*.db-wal
*.db-shm
__pycache__/
.pytest_cache/
.ruff_cache/
*.egg-info/
dist/
.venv/
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pip install -e ".[dev]" && pytest tests/test_config.py tests/test_cli.py -v`
Expected: 3 passed

- [ ] **Step 5: 提交**

```bash
git add pyproject.toml Makefile config .gitignore src tests
git commit -m "chore: scaffold xqdb package with config and CLI"
```

---

### Task 2: SQLite 模式与连接层

**Files:**
- Create: `schemas/schema.sql`, `src/xqdb/store/__init__.py`, `src/xqdb/store/db.py`, `src/xqdb/store/models.py`
- Test: `tests/test_db.py`

**Interfaces:**
- Consumes: `Config.db_path`
- Produces: `connect(path: Path) -> sqlite3.Connection`；`init_db(conn: sqlite3.Connection) -> None`；`SCHEMA_VERSION: str`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_db.py
import sqlite3
import pytest
from xqdb.store.db import connect, init_db, SCHEMA_VERSION

def test_init_creates_core_tables(tmp_path):
    conn = connect(tmp_path / "x.db")
    init_db(conn)
    names = {r[0] for r in conn.execute(
        "select name from sqlite_master where type='table'")}
    assert {"source", "work", "edition", "section", "passage",
            "review_finding", "index_meta"} <= names
    assert conn.execute(
        "select value from index_meta where key='schema_version'").fetchone()[0] == SCHEMA_VERSION

def test_init_is_idempotent(tmp_path):
    conn = connect(tmp_path / "x.db")
    init_db(conn); init_db(conn)
    assert conn.execute("select count(*) from index_meta").fetchone()[0] == 1

def test_foreign_keys_enforced(tmp_path):
    conn = connect(tmp_path / "x.db"); init_db(conn)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("insert into edition(id, work_id, source_id) values('e:x','w:none','s:none')")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_db.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'xqdb.store'`

- [ ] **Step 3: 写 schema 与实现**

`schemas/schema.sql` 按设计文档 7.5 建表，全部 `CREATE TABLE IF NOT EXISTS`，并加：

```sql
CREATE TABLE index_meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE VIRTUAL TABLE IF NOT EXISTS passage_fts
  USING fts5(passage_id UNINDEXED, text_norm, tokenize='trigram');
```

`edition` 增补 `batch_id TEXT`、`simhash TEXT`。`work.title_alt` 用 JSON 字符串。

`connect()` 设置 `foreign_keys=ON`、`journal_mode=WAL`、`row_factory=sqlite3.Row`。`init_db()` 执行 schema，并把 `SCHEMA_VERSION = "1"` 写入 `index_meta`（`INSERT OR IGNORE`）。

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_db.py -v`
Expected: 3 passed

- [ ] **Step 5: 提交**

```bash
git add schemas src/xqdb/store tests/test_db.py
git commit -m "feat: add SQLite schema and connection layer"
```

---

### Task 3: 稳定 ID 生成

**Files:**
- Create: `src/xqdb/normalize/__init__.py`, `src/xqdb/normalize/ids.py`
- Test: `tests/test_ids.py`

**Interfaces:**
- Consumes: 无
- Produces: `slugify_title(title: str) -> str`；`work_id(title: str) -> str`；`edition_id(wid: str, source: str, version: int = 1) -> str`；`section_id(eid: str, path: tuple[int, ...]) -> str`；`passage_id(sid: str, idx: int) -> str`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_ids.py
from xqdb.normalize.ids import *

def test_chinese_slug():
    assert work_id("春秋左氏传") == "w:chun-qiu-zuo-shi-zhuan"

def test_edition_and_children():
    eid = edition_id("w:lunyu", "daizhige")
    assert eid == "e:w:lunyu:daizhige:v1"
    sid = section_id(eid, (2, 3))
    assert passage_id(sid, 7) == sid + ":007"

def test_deterministic_and_collision_free():
    assert work_id("论语") == work_id("论语")
    assert work_id("论语") != work_id("孟子")

def test_fallback_for_punctuation_only():
    assert work_id("《》") .startswith("w:u-")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_ids.py -v`
Expected: FAIL，`ModuleNotFoundError`

- [ ] **Step 3: 实现**

`slugify_title` 用 `pypinyin.lazy_pinyin(title)` 拼接，转小写、非字母数字转 `-`、压缩连续 `-`；结果为空时用 `u-` + `sha1(title).hexdigest()[:8]`。`section_id` 用 `-` 连接补零两位的层级序号。

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_ids.py -v`
Expected: 4 passed

- [ ] **Step 5: 提交**

```bash
git add src/xqdb/normalize tests/test_ids.py
git commit -m "feat: add stable pinyin-based corpus IDs"
```

---

### Task 4: 语料源清单

**Files:**
- Create: `catalog/sources.yaml`, `src/xqdb/catalog/__init__.py`, `src/xqdb/catalog/sources.py`
- Test: `tests/test_sources.py`

**Interfaces:**
- Consumes: `Config.root`
- Produces: `@dataclass Source(id, name, url, license, trust, notes)`；`load_sources(path: Path) -> dict[str, Source]`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_sources.py
from pathlib import Path
import pytest
from xqdb.catalog.sources import load_sources

def test_load_and_validate(tmp_path):
    p = tmp_path / "sources.yaml"
    p.write_text("""
daizhige:
  name: 殆知阁
  url: https://github.com/garychowcmu/daizhigev20
  license: unknown
  trust: tertiary
""", encoding="utf-8")
    src = load_sources(p)["daizhige"]
    assert src.trust == "tertiary"

def test_rejects_bad_trust(tmp_path):
    p = tmp_path / "sources.yaml"
    p.write_text("x: {name: x, url: x, license: x, trust: nope}\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_sources(p)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_sources.py -v`
Expected: FAIL

- [ ] **Step 3: 实现并写入真实清单**

`catalog/sources.yaml` 至少包含 `daizhige`（`trust: tertiary`，`license: unknown`）与 `wikisource`（`trust: secondary`，`license: CC-BY-SA-4.0`）。

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_sources.py -v`
Expected: 2 passed

- [ ] **Step 5: 提交**

```bash
git add catalog src/xqdb/catalog tests/test_sources.py
git commit -m "feat: add validated corpus source manifest"
```

---

### Task 5: 殆知阁采集

**Files:**
- Create: `src/xqdb/ingest/__init__.py`, `src/xqdb/ingest/daizhige.py`
- Test: `tests/test_ingest_daizhige.py`

**Interfaces:**
- Consumes: `Config.raw_dir`、`Source`
- Produces: `@dataclass RawFile(path, rel_path, sha256, size)`；`enumerate_corpus(root: Path) -> list[RawFile]`；`fetch_repo(dest: Path, url: str) -> Path`（`subprocess` 调 `git clone --depth 1`，已存在则跳过）

- [ ] **Step 1: 写失败测试**

```python
# tests/test_ingest_daizhige.py
from pathlib import Path
from xqdb.ingest.daizhige import enumerate_corpus

def test_enumerates_txt_only(tmp_path):
    (tmp_path / "儒藏" / "春秋").mkdir(parents=True)
    (tmp_path / "儒藏" / "春秋" / "左传.txt").write_text("◇隐公元年\n正文", encoding="utf-8")
    (tmp_path / "README.md").write_text("x", encoding="utf-8")
    files = enumerate_corpus(tmp_path)
    assert [f.rel_path for f in files] == ["儒藏/春秋/左传.txt"]
    assert len(files[0].sha256) == 64

def test_skips_empty_files(tmp_path):
    (tmp_path / "a.txt").write_bytes(b"")
    assert enumerate_corpus(tmp_path) == []
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_ingest_daizhige.py -v`
Expected: FAIL

- [ ] **Step 3: 实现**

遍历 `root.rglob("*.txt")`，跳过空文件，计算流式 SHA256，`rel_path` 用 POSIX 分隔符。`fetch_repo` 在目标存在时直接返回。

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_ingest_daizhige.py -v`
Expected: 2 passed

- [ ] **Step 5: 提交**

```bash
git add src/xqdb/ingest tests/test_ingest_daizhige.py
git commit -m "feat: enumerate daizhige corpus files"
```

---

### Task 6: 编码检测与转码

**Files:**
- Create: `src/xqdb/normalize/encoding.py`
- Test: `tests/test_encoding.py`

**Interfaces:**
- Consumes: 无
- Produces: `@dataclass Decoded(text, encoding, replacement_ratio, had_bom)`；`decode_bytes(data: bytes) -> Decoded`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_encoding.py
from xqdb.normalize.encoding import decode_bytes

def test_utf8():
    d = decode_bytes("左传".encode())
    assert d.text == "左传" and d.encoding == "utf-8" and d.replacement_ratio == 0

def test_utf8_bom():
    d = decode_bytes(b"\xef\xbb\xbf" + "论语".encode())
    assert d.text == "论语" and d.had_bom

def test_gb18030():
    d = decode_bytes("春秋".encode("gb18030"))
    assert d.text == "春秋" and d.encoding == "gb18030"

def test_invalid_bytes_reported():
    d = decode_bytes(b"\xff\xfe\xfa\xfb")
    assert d.replacement_ratio > 0
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_encoding.py -v`
Expected: FAIL

- [ ] **Step 3: 实现**

依次尝试 `utf-8`、`gb18030`、`big5`（`strict`）。解码前先检查并剥离 UTF-8 BOM（`\xef\xbb\xbf`），剥离后仍报 `encoding="utf-8"`。全部失败则用 `utf-8` 加 `errors="replace"`。`replacement_ratio = text.count("�") / max(len(text), 1)`。

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_encoding.py -v`
Expected: 4 passed

- [ ] **Step 5: 提交**

```bash
git add src/xqdb/normalize/encoding.py tests/test_encoding.py
git commit -m "feat: add robust Chinese encoding detection"
```

---

### Task 7: 文本解析与分章

**Files:**
- Create: `src/xqdb/normalize/parse.py`
- Test: `tests/test_parse.py`, `tests/fixtures/daizhige/儒藏/春秋/春秋左传.txt`

**Interfaces:**
- Consumes: `Decoded.text`
- Produces: `@dataclass ParsedSection(title, level, lines)`；`@dataclass ParsedWork(title, front_matter, sections)`；`strip_indent(line: str) -> str`；`parse_daizhige_text(text: str, fallback_title: str) -> ParsedWork`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_parse.py
from xqdb.normalize.parse import parse_daizhige_text, strip_indent

SAMPLE = """隐公（元年～十一年）
　　桓公（元年～十八年）
　　◇隐公元年
　　【经】元年春王正月。
　　【传】惠公元妃孟子。
　　◇隐公二年
　　【经】二年春，公会戎于潜。
"""

def test_strip_indent():
    assert strip_indent("　　正文") == "正文"

def test_sections_split_on_marker():
    w = parse_daizhige_text(SAMPLE, "春秋左传")
    assert [s.title for s in w.sections] == ["隐公元年", "隐公二年"]
    assert w.sections[0].lines[0] == "【经】元年春王正月。"

def test_front_matter_kept():
    w = parse_daizhige_text(SAMPLE, "春秋左传")
    assert "桓公" in w.front_matter[0]

def test_no_marker_single_section():
    w = parse_daizhige_text("　　只有正文。", "无名")
    assert len(w.sections) == 1 and w.sections[0].title == "无名"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_parse.py -v`
Expected: FAIL

- [ ] **Step 3: 实现**

逐行 `strip_indent`（去掉行首全部 `　` 与空格）。以 `◇` 开头的行开新章节。首个 `◇` 之前的非空行进 `front_matter`。无标记时整篇为单章节。连续空行折叠为一行。

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_parse.py -v`
Expected: 4 passed

- [ ] **Step 5: 提交**

```bash
git add src/xqdb/normalize/parse.py tests/test_parse.py tests/fixtures
git commit -m "feat: parse daizhige text into sections"
```

---

### Task 8: 规范化流水线（raw → corpus）

**Files:**
- Create: `src/xqdb/normalize/pipeline.py`, `src/xqdb/normalize/simplify.py`
- Test: `tests/test_normalize.py`

**Interfaces:**
- Consumes: `decode_bytes`、`parse_daizhige_text`、ID 函数、`Config.corpus_dir`
- Produces: `@dataclass NormalizeResult(edition_id, work_id, path, char_count, sha256, simhash)`；`normalize_file(raw: Path, rel_path: str, source: str, corpus_dir: Path) -> NormalizeResult`；`to_simplified(text: str) -> str`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_normalize.py
from pathlib import Path
from xqdb.normalize.pipeline import normalize_file

def test_writes_markdown_with_frontmatter(tmp_path):
    raw = tmp_path / "raw" / "春秋左传.txt"
    raw.parent.mkdir()
    raw.write_text("　　　　◇隐公元年\n　　【经】元年春王正月。\n", encoding="utf-8")
    out = normalize_file(raw, "儒藏/春秋/春秋左传.txt", "daizhige", tmp_path / "corpus")
    text = out.path.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    assert "source: daizhige" in text
    assert "## 隐公元年" in text
    assert out.char_count > 0 and out.work_id.startswith("w:")

def test_simplify():
    from xqdb.normalize.simplify import to_simplified
    assert to_simplified("鄭伯克段") == "郑伯克段"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_normalize.py -v`
Expected: FAIL

- [ ] **Step 3: 实现**

文件头用 YAML `safe_dump(allow_unicode=True, sort_keys=False)`，字段与设计文档 7.2 对齐；正文用 `## 章节名` + 段落。`to_simplified` 用 OpenCC `t2s`，模块级缓存实例。`simhash` 用 64 位 simhash（分词按字符二元组）。

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_normalize.py -v`
Expected: 2 passed

- [ ] **Step 5: 提交**

```bash
git add src/xqdb/normalize tests/test_normalize.py
git commit -m "feat: normalize raw texts into versioned Markdown"
```

---

### Task 9: 规则审核与质量分级

**Files:**
- Create: `src/xqdb/review/__init__.py`, `src/xqdb/review/rules.py`
- Test: `tests/test_review_rules.py`

**Interfaces:**
- Consumes: 规范化文本
- Produces: `@dataclass Finding(kind, severity, evidence)`；`simhash64(text: str) -> str`；`hamming(a: str, b: str) -> int`；`check_text(text: str, *, known_hashes: dict[str, str] | None = None) -> list[Finding]`；`grade(findings: list[Finding], text: str) -> str`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_review_rules.py
from xqdb.review.rules import check_text, grade, simhash64, hamming

def test_encoding_finding():
    f = check_text("正常" * 100 + "�" * 5)
    assert any(x.kind == "encoding_corrupt" for x in f)
    assert grade(f, "正常" * 100) == "Q"

def test_empty_or_toc_is_c():
    assert grade([], "目录") == "C"

def test_varied_text_is_a():
    text = "".join(chr(0x4E00 + i) for i in range(300))
    assert grade([], text) == "A"

def test_near_duplicate_detected():
    a = "左传隐公元年郑伯克段于鄢" * 20
    b = a[:-1] + "也"
    assert hamming(simhash64(a), simhash64(b)) <= 4
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_review_rules.py -v`
Expected: FAIL

- [ ] **Step 3: 实现**

规则：`encoding_corrupt`（替换符比例）、`truncated`（末行无标点且长度异常）、`fragmentary`（有效字符 < 200）、`high_duplication`（与已知 simhash 汉明距离 ≤ 3，且 text 长度相近）、`low_information`（去重字符 < 50 或单行重复率 > 0.8）。

分级：
- 有 `encoding_corrupt` 且比例 > 1% → `Q`
- 有效字符 < 200 或 `low_information` → `C`
- 有其他 warn → `B`
- 否则 `A`

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_review_rules.py -v`
Expected: 3 passed

- [ ] **Step 5: 提交**

```bash
git add src/xqdb/review tests/test_review_rules.py
git commit -m "feat: add rule-based quality grading"
```

---

### Task 10: 批次审核流水线与门禁

**Files:**
- Create: `src/xqdb/review/pipeline.py`
- Test: `tests/test_review_pipeline.py`

**Interfaces:**
- Consumes: `connect`、`init_db`、`check_text`、`grade`
- Produces: `@dataclass ReviewResult(edition_id, quality_grade, findings)`；`@dataclass BatchReport(total, q_count, q_rate, blocked, results)`；`review_batch(conn, batch_id: str, corpus_dir: Path) -> BatchReport`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_review_pipeline.py
from pathlib import Path
import pytest
from xqdb.store.db import connect, init_db
from xqdb.review.pipeline import review_batch

def _seed(conn, n, bad=0):
    conn.execute("insert into source(id,name,url,license,trust) values('s','s','u','x','tertiary')")
    for i in range(n):
        conn.execute("insert into work(id,title) values(?,?)", (f"w:{i}", f"书{i}"))
        conn.execute("""insert into edition(id,work_id,source_id,path,char_count,batch_id)
                        values(?,?, 's', ?, ?, 'b1')""",
                     (f"e:{i}", f"w:{i}", f"{i}.md", 100))
    conn.commit()

def test_gate_blocks_high_q_rate(tmp_path):
    conn = connect(tmp_path/"x.db"); init_db(conn); _seed(conn, 10)
    (tmp_path/"corpus").mkdir()
    for i in range(10):
        (tmp_path/"corpus"/f"{i}.md").write_text("正常"*50, encoding="utf-8")
    (tmp_path/"corpus"/"0.md").write_text("�"*100, encoding="utf-8")
    rep = review_batch(conn, "b1", tmp_path/"corpus")
    assert rep.q_rate >= 0.1 and rep.blocked is True

def test_gate_allows_low_q_rate(tmp_path):
    conn = connect(tmp_path/"x.db"); init_db(conn); _seed(conn, 20)
    (tmp_path/"corpus").mkdir()
    for i in range(20):
        (tmp_path/"corpus"/f"{i}.md").write_text("正常"*100, encoding="utf-8")
    (tmp_path/"corpus"/"0.md").write_text("�"*100, encoding="utf-8")
    rep = review_batch(conn, "b1", tmp_path/"corpus")
    assert rep.q_rate == 0.05 and rep.blocked is False
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_review_pipeline.py -v`
Expected: FAIL

- [ ] **Step 3: 实现**

遍历批次内 `edition`，读取 `corpus_dir / path`，跑 `check_text`，写 `review_finding`（先删该 edition 旧记录再插入），更新 `quality_grade`、`review_status='reviewed'`；`provenance_class` 在 P0 阶段无法自动判定，统一写 `unknown`，留给后续 LLM Reviewer 覆盖。`q_rate = q_count / total`，`blocked = q_rate > 0.10`。

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_review_pipeline.py -v`
Expected: 2 passed

- [ ] **Step 5: 提交**

```bash
git add src/xqdb/review/pipeline.py tests/test_review_pipeline.py
git commit -m "feat: add batch review with quarantine gate"
```

---

### Task 11: FTS 索引与检索

**Files:**
- Create: `src/xqdb/index/__init__.py`, `src/xqdb/index/fts.py`
- Test: `tests/test_fts.py`

**Interfaces:**
- Consumes: `connect`、`to_simplified`
- Produces: `@dataclass Hit(passage_id, work, section, text, score)`；`rebuild_fts(conn) -> int`；`search(conn, query: str, *, limit: int = 20, grades: tuple[str, ...] = ("A", "B")) -> list[Hit]`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_fts.py
from xqdb.store.db import connect, init_db
from xqdb.index.fts import rebuild_fts, search

def _seed(conn):
    conn.execute("insert into source(id,name,url,license,trust) values('s','s','u','x','secondary')")
    conn.execute("insert into work(id,title) values('w:z','春秋左传')")
    conn.execute("insert into edition(id,work_id,source_id,char_count,quality_grade) values('e:z','w:z','s',10,'A')")
    conn.execute("insert into section(id,edition_id,idx,title,level) values('s:z:1','e:z',1,'隐公元年',1)")
    conn.execute("""insert into passage(id,section_id,idx,text,text_norm,char_count)
                    values('p:z:1:001','s:z:1',1,'郑伯克段于鄢','郑伯克段于鄢',7)""")
    conn.commit()

def test_rebuild_and_search(tmp_path):
    conn = connect(tmp_path/"x.db"); init_db(conn); _seed(conn)
    assert rebuild_fts(conn) == 1
    hits = search(conn, "郑伯克段")
    assert hits[0].passage_id == "p:z:1:001" and hits[0].work == "春秋左传"

def test_traditional_query_matches_simplified(tmp_path):
    conn = connect(tmp_path/"x.db"); init_db(conn); _seed(conn); rebuild_fts(conn)
    assert search(conn, "鄭伯克段")[0].passage_id == "p:z:1:001"

def test_short_query_falls_back_to_like(tmp_path):
    conn = connect(tmp_path/"x.db"); init_db(conn); _seed(conn); rebuild_fts(conn)
    assert search(conn, "郑伯")[0].passage_id == "p:z:1:001"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_fts.py -v`
Expected: FAIL

- [ ] **Step 3: 实现**

`rebuild_fts` 清空 `passage_fts`，插入 `(passage_id, text_norm)`，返回条数。`search` 对查询做 `to_simplified`；`len(query) < 3` 用 `LIKE '%q%'`，否则 `passage_fts MATCH ?` 并对短词加引号。结果 join `passage → section → edition → work`，过滤 `quality_grade`，按 `work` 去重保留 `quality_grade` 排序最前的版本。

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_fts.py -v`
Expected: 3 passed

- [ ] **Step 5: 提交**

```bash
git add src/xqdb/index tests/test_fts.py
git commit -m "feat: add trigram FTS index with short-query fallback"
```

---

### Task 12: CLI 子命令与目录导出

**Files:**
- Modify: `src/xqdb/cli.py`
- Create: `src/xqdb/catalog/build.py`
- Test: `tests/test_cli_commands.py`

**Interfaces:**
- Consumes: 前面所有模块
- Produces: `build_index_jsonl(conn, out: Path) -> int`；CLI 子命令 `init / ingest / normalize / review / index / search / stats`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_cli_commands.py
from pathlib import Path
from xqdb.cli import main

def test_init_creates_db(tmp_path, monkeypatch):
    (tmp_path/"config").mkdir()
    (tmp_path/"config"/"config.yaml").write_text("", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    assert main(["init"]) == 0
    assert (tmp_path/"data"/"xq_index.db").exists()

def test_search_returns_citation(tmp_path, capsys):
    (tmp_path/"config").mkdir()
    (tmp_path/"config"/"config.yaml").write_text("", encoding="utf-8")
    (tmp_path/"data").mkdir()
    from xqdb.store.db import connect, init_db
    from xqdb.index.fts import rebuild_fts
    conn = connect(tmp_path/"data"/"xq_index.db"); init_db(conn)
    conn.execute("insert into source(id,name,url,license,trust) values('s','s','u','x','secondary')")
    conn.execute("insert into work(id,title) values('w:z','春秋左传')")
    conn.execute("insert into edition(id,work_id,source_id,char_count,quality_grade) values('e:z','w:z','s',10,'A')")
    conn.execute("insert into section(id,edition_id,idx,title,level) values('s:z:1','e:z',1,'隐公元年',1)")
    conn.execute("""insert into passage(id,section_id,idx,text,text_norm,char_count)
                    values('p:z:1:001','s:z:1',1,'郑伯克段于鄢','郑伯克段于鄢',7)""")
    conn.commit(); rebuild_fts(conn); conn.close()
    assert main(["search", "郑伯克段", "--root", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "[p:z:1:001]" in out and "春秋左传" in out
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_cli_commands.py -v`
Expected: FAIL

- [ ] **Step 3: 实现**

用 `argparse` 子解析器；`--root` 全局参数默认当前目录。`search` 输出格式固定为：

```
[p:z:1:001] 春秋左传 · 隐公元年
  郑伯克段于鄢
```

`stats` 输出作品数、版本数、段落数、各质量等级计数。`build_index_jsonl` 每行一个作品元数据。

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_cli_commands.py -v`
Expected: 2 passed

- [ ] **Step 5: 提交**

```bash
git add src/xqdb/cli.py src/xqdb/catalog tests/test_cli_commands.py
git commit -m "feat: add CLI commands and catalog export"
```

---

### Task 13: 维基文库采集

**Files:**
- Create: `src/xqdb/ingest/wikisource.py`, `tests/fixtures/wikisource/论语.json`
- Test: `tests/test_ingest_wikisource.py`

**Interfaces:**
- Consumes: `httpx`（注入 client，测试用 fixture）
- Produces: `@dataclass WikiPage(title, wikitext)`；`fetch_pages(titles: list[str], client) -> list[WikiPage]`；`parse_response(data: dict) -> list[WikiPage]`；`strip_wikitext(text: str) -> str`；`CORE_TITLES: list[str]`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_ingest_wikisource.py
import json
from pathlib import Path
from xqdb.ingest.wikisource import strip_wikitext, parse_response

def test_strip_wikitext_removes_templates_and_links():
    assert strip_wikitext("[[左传]]{{note|x}}正文") == "左传正文"

def test_parse_fixture():
    data = json.loads(Path("tests/fixtures/wikisource/论语.json").read_text("utf-8"))
    pages = parse_response(data)
    assert pages[0].title == "论语"
    assert "子曰" in strip_wikitext(pages[0].wikitext)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_ingest_wikisource.py -v`
Expected: FAIL

- [ ] **Step 3: 实现**

`fetch_pages` 调用 `https://zh.wikisource.org/w/api.php`，`action=query&prop=revisions&rvprop=content&rvslots=main&format=json&titles=...`，批次 ≤ 50。`strip_wikitext` 移除模板、链接语法、HTML 注释，保留纯文本。`CORE_TITLES` 至少包含：左传、国语、战国策、论语、孟子、庄子、老子、荀子、韩非子、墨子、诗经、楚辞、山海经、竹书纪年。

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_ingest_wikisource.py -v`
Expected: 2 passed

- [ ] **Step 5: 提交**

```bash
git add src/xqdb/ingest/wikisource.py tests
git commit -m "feat: add Wikisource ingest for core pre-Qin texts"
```

---

### Task 14: Release 打包

**Files:**
- Create: `src/xqdb/release.py`
- Test: `tests/test_release.py`

**Interfaces:**
- Consumes: `Config`
- Produces: `build_release(root: Path, tag: str) -> Path`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_release.py
import json, tarfile
from pathlib import Path
from xqdb.release import build_release

def test_release_manifest_and_archives(tmp_path):
    for d in ("data/raw", "data/corpus", "data/knowledge"):
        (tmp_path/d).mkdir(parents=True)
    (tmp_path/"data/corpus/a.md").write_text("正文", encoding="utf-8")
    out = build_release(tmp_path, "data-v0.0.1")
    manifest = json.loads((out/"MANIFEST.json").read_text("utf-8"))
    assert manifest["tag"] == "data-v0.0.1"
    assert any(a["name"].startswith("normalized-") for a in manifest["assets"])
    assert (out/"MANIFEST.json").exists()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_release.py -v`
Expected: FAIL

- [ ] **Step 3: 实现**

用 `tarfile` 打包 `raw/`、`corpus/`、`knowledge/`（存在才打），`zstandard` 压缩为 `.tar.zst`，写入 `dist/<tag>/`，生成 `MANIFEST.json`（tag、时间、各资产名、SHA256、条目数）。个人目录 `data/personal/` 永不打包。

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_release.py -v`
Expected: 1 passed

- [ ] **Step 5: 提交**

```bash
git add src/xqdb/release.py tests/test_release.py
git commit -m "feat: add versioned release packaging"
```

---

### Task 15: 仓库初始化与 GitHub 托管

**Files:**
- Create: `README.md`, `LICENSE`, `Makefile`（补全目标）
- Modify: `.gitignore`

**Interfaces:**
- Consumes: 全部
- Produces: 可 push 的 `main` 分支；`xq-db`（公开）与 `xq-corpus`（私有）两个远程仓库

- [ ] **Step 1: 写 README**

包含：项目目标、目录结构、`pip install -e ".[dev]"`、`xqdb init`、`make ingest-daizhige`、`make index`、`make search Q="郑伯克段"`、数据不公开的说明。

- [ ] **Step 2: 补 Makefile**

```makefile
init:        ; xqdb init
ingest:      ; xqdb ingest daizhige
normalize:   ; xqdb normalize
review:      ; xqdb review
index:       ; xqdb index
search:      ; xqdb search "$(Q)"
release:     ; xqdb release --tag $(TAG)
test:        ; pytest -q
```

- [ ] **Step 3: 验证全流程（fixture 级）**

Run: `pytest -q`
Expected: 全部通过

- [ ] **Step 4: 初始化 git 并提交**

```bash
git init -b main
git add .
git commit -m "chore: initialize xq-db corpus pipeline"
```

- [ ] **Step 5: 创建远程仓库并推送**

```bash
gh repo create LeewayTang/xq-db --public --source=. --remote=origin --push
gh repo create LeewayTang/xq-corpus --private
```

Expected: 两条命令成功；`git remote -v` 显示 `origin`。

---

### Task 16: 时空标注基础与查询

**Files:**
- Modify: `schemas/schema.sql`
- Create: `src/xqdb/space/__init__.py`, `src/xqdb/space/place.py`, `src/xqdb/space/query.py`
- Modify: `src/xqdb/cli.py`
- Test: `tests/test_space.py`

**Interfaces:**
- Consumes: `Hit`、`connect`
- Produces: `@dataclass PlaceMatch(place_id, canonical_name, matched_name, name_type, lat, lon, precision_m, modern_name, confidence)`；`resolve_place(conn, name) -> list[PlaceMatch]`；`upsert_place(conn, place_id, canonical_name, type=None)`；`add_name(conn, place_id, name, name_type, period=None, is_preferred=False)`；`add_location(conn, place_id, lat, lon, *, precision_m=5000, modern_province=None, modern_city=None, modern_county=None, hypothesis=None, confidence=0.5, is_primary=False)`；`haversine_km(a_lat, a_lon, b_lat, b_lon) -> float`；`passages_in_time(conn, start, end, limit=20) -> list[Hit]`；`passages_near(conn, lat, lon, radius_km, limit=20) -> list[Hit]`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_space.py
from xqdb.space.place import (add_location, add_name, haversine_km,
                              resolve_place, upsert_place)
from xqdb.space.query import passages_in_time, passages_near
from xqdb.store.db import connect, init_db

def _place(conn):
    upsert_place(conn, "pl:xinzheng", "新郑", "邑")
    add_name(conn, "pl:xinzheng", "郑", "ancient", period="春秋", is_preferred=True)
    add_name(conn, "pl:xinzheng", "新郑市", "modern", is_preferred=True)
    add_location(conn, "pl:xinzheng", 34.39, 113.74, precision_m=5000,
                 modern_province="河南", modern_city="郑州",
                 modern_county="新郑", is_primary=True)
    upsert_place(conn, "pl:mingtiao", "鸣条", "战场")
    add_name(conn, "pl:mingtiao", "鸣条", "ancient", is_preferred=True)
    add_location(conn, "pl:mingtiao", 35.03, 111.22,
                 hypothesis="安邑说", confidence=0.4)
    add_location(conn, "pl:mingtiao", 35.14, 111.22,
                 hypothesis="夏县说", confidence=0.3)
    conn.commit()

def test_resolve_by_ancient_and_modern_name(tmp_path):
    conn = connect(tmp_path/"x.db"); init_db(conn); _place(conn)
    assert resolve_place(conn, "郑")[0].place_id == "pl:xinzheng"
    assert resolve_place(conn, "新郑市")[0].place_id == "pl:xinzheng"

def test_multiple_location_hypotheses_preserved(tmp_path):
    conn = connect(tmp_path/"x.db"); init_db(conn); _place(conn)
    matches = [m for m in resolve_place(conn, "鸣条") if m.lat is not None]
    assert len(matches) == 2

def test_haversine():
    d = haversine_km(39.90, 116.40, 31.23, 121.47)
    assert 1000 < d < 1200

def test_time_overlap(tmp_path):
    conn = connect(tmp_path/"x.db"); init_db(conn); _seed_passage(conn, -770, -750)
    assert passages_in_time(conn, -760, -755)[0].passage_id == "p:t:1:001"
    assert passages_in_time(conn, -700, -690) == []

def test_near_radius(tmp_path):
    conn = connect(tmp_path/"x.db"); init_db(conn); _place(conn); _seed_passage(conn, -770, -750, place="pl:xinzheng")
    assert passages_near(conn, 34.40, 113.75, 50)[0].passage_id == "p:t:1:001"
    assert passages_near(conn, 31.23, 121.47, 50) == []
```

`_seed_passage` 是测试内的辅助函数，插入 source/work/edition/section/passage，并按需插入 `passage_time` 与 `passage_place`。

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_space.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'xqdb.space'`

- [ ] **Step 3: 实现 schema 与模块**

`schemas/schema.sql` 增加 `place / place_name / place_location / place_hierarchy / passage_place / passage_time / event_place`，字段与设计文档 7.8 一致。

`resolve_place`：按 `place_name.name` 精确匹配，返回该地点全部坐标假设；无坐标时返回一个 `lat=None` 的匹配。`passages_in_time` 用区间重叠 `year_start <= end AND year_end >= start`。`passages_near` 在 Python 中算 haversine，按距离排序。两者都只取 `quality_grade in ('A','B')` 并按 `work` 去重。

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/test_space.py -v`
Expected: 通过

- [ ] **Step 5: 提交**

```bash
git add schemas src/xqdb/space src/xqdb/cli.py tests/test_space.py
git commit -m "feat: add temporal and spatial annotation foundation"
```

---

## 自检

**1. Spec 覆盖**

| Spec 要求 | 对应任务 |
|---|---|
| 仓库骨架、配置 | Task 1 |
| SQLite 模式（含 review_finding / FTS） | Task 2 |
| 稳定 ID、版本不可变 | Task 3 |
| 来源清单与 trust | Task 4 |
| 殆知阁全量采集 | Task 5 |
| 编码混杂处理 | Task 6 |
| 分章与规范层格式 | Task 7、8 |
| 真伪/质量分级、A/B/C/Q | Task 9 |
| 批次门禁、Q 隔离、10% 阈值 | Task 10 |
| FTS trigram、短查询回退、繁简 | Task 11 |
| CLI 与目录导出 | Task 12 |
| 维基文库骨架 | Task 13 |
| 私有 Release 打包 | Task 14 |
| 公/私双仓 | Task 15 |

未覆盖（属于后续 Plan 2–4，不在本计划）：MCP Server、Agent 角色、实体/主题标注、向量检索、灵感工作流、`review watch` 常驻进程。

**2. 步骤扫描**：每个任务均为“写测试 → 跑失败 → 实现 → 跑通过 → 提交”，无 TBD、无“适当处理边界”。

**3. 类型一致性**：`NormalizeResult.simhash` 在 Task 8 产生、Task 9/10 消费；`Hit.passage_id` 在 Task 11 产生、Task 12 CLI 消费；`BatchReport.blocked` 在 Task 10 产生，CLI `review` 返回非零退出码当 `blocked`。

**4. Review Focus 对应测试**：GB18030 → Task 6；无标记文件 → Task 7；短查询 → Task 11；繁体查询 → Task 11；同书多版本去重 → Task 11；空/目录文件 → Task 9。

**5. 比例**：本计划 15 个任务，每个 5 步，代码块仅含测试与接口，不含实现正文。
