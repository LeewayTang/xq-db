import hashlib
import re

from pypinyin import lazy_pinyin, load_phrases_dict

# 古籍标题里的多音字按传统读法固定，保证 ID 稳定。
_PHRASES = {
    "左氏传": [["zuǒ"], ["shì"], ["zhuàn"]],
}
load_phrases_dict(_PHRASES)


def slugify_title(title: str) -> str:
    raw = "-".join(lazy_pinyin(title)).lower()
    slug = re.sub(r"[^a-z0-9]+", "-", raw).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)
    if not slug:
        slug = "u-" + hashlib.sha1(title.encode("utf-8")).hexdigest()[:8]
    return slug


def work_id(title: str) -> str:
    return "w:" + slugify_title(title)


def edition_id(wid: str, source: str, version: int = 1) -> str:
    return f"e:{wid}:{source}:v{version}"


def section_id(eid: str, path: tuple[int, ...]) -> str:
    suffix = "-".join(f"{i:02d}" for i in path)
    return f"s:{eid}:{suffix}"


def passage_id(sid: str, idx: int) -> str:
    return f"{sid}:{idx:03d}"
