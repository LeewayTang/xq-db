from xqdb.normalize.pipeline import normalize_file
from xqdb.normalize.simplify import to_simplified


def test_writes_markdown_with_frontmatter(tmp_path):
    raw = tmp_path / "raw" / "春秋左传.txt"
    raw.parent.mkdir()
    raw.write_text("　　　　◇隐公元年\n　　【经】元年春王正月。\n", encoding="utf-8")
    out = normalize_file(
        raw, "儒藏/春秋/春秋左传.txt", "daizhige", tmp_path / "corpus")
    text = out.path.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    assert "source: daizhige" in text
    assert "## 隐公元年" in text
    assert out.char_count > 0 and out.work_id.startswith("w:")


def test_simplify():
    assert to_simplified("鄭伯克段") == "郑伯克段"


def test_no_marker_file_gets_single_section(tmp_path):
    raw = tmp_path / "raw" / "无名书.txt"
    raw.parent.mkdir()
    raw.write_text("　　只有正文。\n", encoding="utf-8")
    out = normalize_file(
        raw, "子藏/杂家/无名书.txt", "daizhige", tmp_path / "corpus")
    text = out.path.read_text(encoding="utf-8")
    assert "## 无名书" in text
    assert "只有正文。" in text


def test_result_is_deterministic_and_has_simhash(tmp_path):
    raw = tmp_path / "raw" / "论语.txt"
    raw.parent.mkdir()
    raw.write_text("　　◇学而\n　　子曰学而时习之。\n", encoding="utf-8")
    first = normalize_file(raw, "儒藏/四书/论语.txt", "daizhige", tmp_path / "corpus")
    second = normalize_file(raw, "儒藏/四书/论语.txt", "daizhige", tmp_path / "corpus")
    assert first.edition_id == second.edition_id
    assert len(first.simhash) == 16 and len(first.sha256) == 64


def test_same_title_different_paths_do_not_collide(tmp_path):
    first_raw = tmp_path / "a.txt"
    second_raw = tmp_path / "b.txt"
    first_raw.write_text("　　甲书正文。\n", encoding="utf-8")
    second_raw.write_text("　　乙书正文。\n", encoding="utf-8")
    first = normalize_file(
        first_raw, "子藏/甲/同名.txt", "daizhige", tmp_path / "corpus")
    second = normalize_file(
        second_raw, "子藏/乙/同名.txt", "daizhige", tmp_path / "corpus")
    assert first.path != second.path


def test_wikisource_source_uses_heading_parser(tmp_path):
    raw = tmp_path / "論語.txt"
    raw.write_text(
        "== 學而 ==\n子曰學而時習之。\n== 為政 ==\n子曰為政以德。\n",
        encoding="utf-8")
    result = normalize_file(
        raw, "論語.txt", "wikisource", tmp_path / "corpus")
    text = result.path.read_text(encoding="utf-8")
    assert "## 學而" in text and "## 為政" in text
