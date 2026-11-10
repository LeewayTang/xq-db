from xqdb.normalize.ids import (
    edition_id,
    passage_id,
    section_id,
    slugify_title,
    work_id,
)


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
    assert work_id("《》").startswith("w:u-")


def test_slugify_is_ascii():
    slug = slugify_title("《春秋》左氏传")
    assert slug.isascii() and " " not in slug
