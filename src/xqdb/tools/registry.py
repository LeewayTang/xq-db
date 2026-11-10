import inspect
import types
import typing
from collections.abc import Callable
from dataclasses import dataclass

from .admin import ingest_run
from .corpus import corpus_stats, get_passage, get_work, list_works
from .knowledge import entity_lookup, timeline
from .personal import note_add, note_search, seed_add, seed_list
from .search import search_hybrid, search_keyword, search_semantic


def _json_type(annotation) -> dict:
    if annotation is inspect.Parameter.empty:
        return {}
    origin = typing.get_origin(annotation)
    if origin in (types.UnionType, typing.Union):
        args = [arg for arg in typing.get_args(annotation)
                if arg is not type(None)]
        return _json_type(args[0]) if args else {}
    if annotation is str:
        return {"type": "string"}
    if annotation is int:
        return {"type": "integer"}
    if annotation is float:
        return {"type": "number"}
    if annotation is bool:
        return {"type": "boolean"}
    if origin in (tuple, list, set):
        args = typing.get_args(annotation)
        return {"type": "array", "items": _json_type(args[0]) if args else {}}
    if annotation is dict:
        return {"type": "object"}
    return {}


def tool_schema(func: Callable) -> dict:
    properties: dict[str, dict] = {}
    required: list[str] = []
    for name, parameter in inspect.signature(func).parameters.items():
        if name in ("ctx", "self"):
            continue
        if parameter.kind in (parameter.VAR_KEYWORD, parameter.VAR_POSITIONAL):
            continue
        schema = _json_type(parameter.annotation)
        if parameter.default is not inspect.Parameter.empty:
            schema = dict(schema, default=parameter.default)
        else:
            required.append(name)
        properties[name] = schema
    result: dict = {"type": "object", "properties": properties}
    if required:
        result["required"] = required
    return result


@dataclass(frozen=True)
class ToolSpec:
    name: str
    func: Callable
    description: str
    admin: bool = False


TOOL_SPECS: dict[str, ToolSpec] = {
    "search_keyword": ToolSpec(
        "search_keyword", search_keyword,
        "Full-text keyword search; returns passage-level citations."),
    "search_semantic": ToolSpec(
        "search_semantic", search_semantic,
        "Semantic search when an embedder is configured; explicit otherwise."),
    "search_hybrid": ToolSpec(
        "search_hybrid", search_hybrid,
        "Hybrid retrieval; falls back to keyword search without an embedder."),
    "get_passage": ToolSpec(
        "get_passage", get_passage,
        "Fetch one passage with surrounding context and citation fields."),
    "get_work": ToolSpec(
        "get_work", get_work,
        "Fetch a work, its editions and sections, optionally with text."),
    "list_works": ToolSpec(
        "list_works", list_works,
        "List works filtered by era, genre, or relevance."),
    "entity_lookup": ToolSpec(
        "entity_lookup", entity_lookup,
        "Look up an entity by name or alias, with mentions and relations."),
    "timeline": ToolSpec(
        "timeline", timeline,
        "Return passages whose time interval overlaps the requested range."),
    "corpus_stats": ToolSpec(
        "corpus_stats", corpus_stats,
        "Corpus size, quality-grade distribution, and schema version."),
    "note_add": ToolSpec(
        "note_add", note_add,
        "Add a personal note attached to any target."),
    "note_search": ToolSpec(
        "note_search", note_search,
        "Search personal notes by text or target id."),
    "seed_add": ToolSpec(
        "seed_add", seed_add,
        "Create a story seed linked to source passages."),
    "seed_list": ToolSpec(
        "seed_list", seed_list,
        "List story seeds, optionally filtered by status."),
    "ingest_run": ToolSpec(
        "ingest_run", ingest_run,
        "Admin: fetch and enumerate a corpus source.", admin=True),
}

TOOL_NAMES: tuple[str, ...] = tuple(TOOL_SPECS)
