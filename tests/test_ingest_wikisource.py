import json
from pathlib import Path

from xqdb.ingest.wikisource import (
    CORE_TITLES,
    USER_AGENT,
    WikiPage,
    fetch_documents,
    fetch_pages,
    parse_response,
    strip_wikitext,
    write_pages,
)


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


def test_write_pages_creates_manifest(tmp_path):
    files = write_pages(
        [WikiPage("论语", "子曰：[[学而]]{{注}}时习之。")], tmp_path)
    assert len(files) == 1
    assert (tmp_path / "wikisource" / "论语.txt").read_text(
        encoding="utf-8") == "子曰：学而时习之。"
    manifest = tmp_path / "wikisource" / "manifest.jsonl"
    assert "\"rel_path\": \"论语.txt\"" in manifest.read_text(encoding="utf-8")


def test_write_pages_sanitises_slashes(tmp_path):
    write_pages([WikiPage("甲/乙", "正文")], tmp_path)
    assert (tmp_path / "wikisource" / "甲_乙.txt").exists()


def test_fetch_pages_sets_ua_and_follows_redirects():
    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"query": {"pages": []}}

    class Client:
        def __init__(self):
            self.kwargs = {}

        def get(self, url, **kwargs):
            self.kwargs = kwargs
            return Response()

    client = Client()
    fetch_pages(["论语"], client)
    assert client.kwargs["params"]["redirects"] == "1"
    assert USER_AGENT in client.kwargs["headers"]["User-Agent"]


def test_fetch_documents_concatenates_subpages():
    class Response:
        def __init__(self, data):
            self.data = data

        def raise_for_status(self):
            pass

        def json(self):
            return self.data

    class Client:
        def get(self, url, params=None, headers=None):
            if params.get("list") == "allpages":
                return Response({"query": {"allpages": [
                    {"title": "論語/學而"}, {"title": "論語/為政"}]}})
            titles = params["titles"].split("|")
            pages = []
            for title in titles:
                text = "总目录" if title == "论语" else f"正文-{title}"
                pages.append({"title": title if title != "论语" else "論語",
                              "revisions": [{"slots": {"main": {"*": text}}}]})
            return Response({"query": {"pages": pages}})

    documents = fetch_documents(["论语"], Client())
    assert len(documents) == 1
    assert "== 學而 ==" in documents[0].wikitext
    assert "正文-論語/學而" in documents[0].wikitext
