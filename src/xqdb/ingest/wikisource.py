import json
import re
from dataclasses import dataclass
from pathlib import Path

from .daizhige import enumerate_corpus

API = "https://zh.wikisource.org/w/api.php"
BATCH = 50
USER_AGENT = "xqdb/0.1 (https://github.com/LeewayTang/xq-db)"

CORE_TITLES = [
    "春秋左氏傳",
    "國語",
    "戰國策",
    "論語",
    "孟子",
    "莊子",
    "荀子",
    "韓非子",
    "墨子",
    "詩經",
    "楚辭",
    "山海經",
    "老子 (帛書本)",
    "古本竹書紀年輯校",
    "竹書紀年 (四庫全書本)",
    "今本竹書紀年疏證",
    "清華大學藏戰國竹簡",
    "郭店楚墓竹簡",
    "睡虎地秦簡",
]


@dataclass(frozen=True)
class WikiPage:
    title: str
    wikitext: str


def parse_response(data: dict) -> list[WikiPage]:
    pages = data.get("query", {}).get("pages", {})
    items = pages.values() if isinstance(pages, dict) else pages

    result: list[WikiPage] = []
    for page in items:
        if page.get("missing") is not None or "missing" in page:
            continue
        revisions = page.get("revisions") or []
        if not revisions:
            continue
        revision = revisions[0]
        slots = revision.get("slots") or {}
        main = slots.get("main") or {}
        text = main.get("*") or main.get("content")
        if text is None:
            text = revision.get("*", "")
        result.append(WikiPage(title=page.get("title", ""), wikitext=text))
    return result


def strip_wikitext(text: str) -> str:
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    previous = None
    while previous != text:
        previous = text
        text = re.sub(r"\{\{[^{}]*\}\}", "", text, flags=re.DOTALL)
    text = re.sub(r"\[\[[^\]|]*\|([^\]]*)\]\]", r"\1", text)
    text = re.sub(r"\[\[([^\]]*)\]\]", r"\1", text)
    text = text.replace("'''", "").replace("''", "")
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def fetch_pages(titles: list[str], client) -> list[WikiPage]:
    pages: list[WikiPage] = []
    for start in range(0, len(titles), BATCH):
        chunk = titles[start:start + BATCH]
        response = client.get(API, params={
            "action": "query",
            "prop": "revisions",
            "rvprop": "content",
            "rvslots": "main",
            "format": "json",
            "formatversion": "2",
            "redirects": "1",
            "titles": "|".join(chunk),
        }, headers={"User-Agent": USER_AGENT})
        response.raise_for_status()
        pages.extend(parse_response(response.json()))
    return pages


def list_subpages(title: str, client) -> list[str]:
    response = client.get(API, params={
        "action": "query",
        "list": "allpages",
        "apprefix": f"{title}/",
        "aplimit": "max",
        "format": "json",
        "formatversion": "2",
    }, headers={"User-Agent": USER_AGENT})
    response.raise_for_status()
    return [
        page["title"]
        for page in response.json().get("query", {}).get("allpages", [])
    ]


def fetch_documents(titles: list[str], client) -> list[WikiPage]:
    documents: list[WikiPage] = []
    for title in titles:
        top = fetch_pages([title], client)
        if not top:
            continue
        page = top[0]
        subpages = list_subpages(page.title, client)
        if not subpages:
            documents.append(page)
            continue

        parts = []
        for subpage in fetch_pages(subpages, client):
            label = subpage.title.split("/", 1)[-1]
            parts.append(f"== {label} ==\n{subpage.wikitext}")
        documents.append(WikiPage(page.title, "\n\n".join(parts)))
    return documents


def safe_filename(title: str) -> str:
    return title.replace("/", "_").replace("\\", "_")


def write_pages(pages: list[WikiPage], raw_dir: Path,
                source: str = "wikisource"):
    source_dir = Path(raw_dir) / source
    source_dir.mkdir(parents=True, exist_ok=True)

    for page in pages:
        text = strip_wikitext(page.wikitext)
        (source_dir / f"{safe_filename(page.title)}.txt").write_text(
            text, encoding="utf-8")

    files = enumerate_corpus(source_dir)
    manifest = source_dir / "manifest.jsonl"
    with manifest.open("w", encoding="utf-8") as handle:
        for item in files:
            handle.write(json.dumps({
                "rel_path": item.rel_path,
                "raw_path": str(item.path),
                "sha256": item.sha256,
                "size": item.size,
            }, ensure_ascii=False) + "\n")
    return files
