import json
from pathlib import Path

from xqdb.ingest.wikisource import CORE_TITLES, parse_response, strip_wikitext


def test_strip_wikitext_removes_templates_and_links():
    assert strip_wikitext("[[左传]]{{note|x}}正文") == "左传正文"


def test_strip_wikitext_handles_piped_links_and_comments():
    text = "[[春秋|春秋经]]<!--x-->'''正文'''"
    assert strip_wikitext(text) == "春秋经正文"


def test_parse_fixture():
    data = json.loads(
        Path("tests/fixtures/wikisource/论语.json").read_text("utf-8"))
    pages = parse_response(data)
    assert pages[0].title == "论语"
    assert "子曰" in strip_wikitext(pages[0].wikitext)


def test_core_titles():
    assert "左传" in CORE_TITLES and len(CORE_TITLES) >= 14
