from pathlib import Path

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
    assert any("桓公" in line for line in w.front_matter)


def test_no_marker_single_section():
    w = parse_daizhige_text("　　只有正文。", "无名")
    assert len(w.sections) == 1 and w.sections[0].title == "无名"
    assert w.sections[0].lines == ["只有正文。"]


def test_blank_lines_collapsed():
    w = parse_daizhige_text("◇甲\n　　一\n　　\n　　\n　　二\n", "书")
    assert w.sections[0].lines == ["一", "", "二"]


def test_fixture_loads():
    path = Path("tests/fixtures/daizhige/儒藏/春秋/春秋左传.txt")
    w = parse_daizhige_text(path.read_text(encoding="utf-8"), "春秋左传")
    assert w.sections and w.sections[0].title
