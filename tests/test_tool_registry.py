from xqdb.tools.registry import TOOL_NAMES, TOOL_SPECS, tool_schema


def test_registry_covers_spec_tools():
    expected = {
        "search_keyword", "search_semantic", "search_hybrid",
        "get_passage", "get_work", "list_works",
        "entity_lookup", "timeline", "corpus_stats",
        "note_add", "note_search", "seed_add", "seed_list",
    }
    assert expected <= set(TOOL_NAMES)


def test_admin_tool_flagged():
    assert TOOL_SPECS["ingest_run"].admin is True


def test_every_spec_has_description():
    assert all(spec.description for spec in TOOL_SPECS.values())


def test_tool_schema_exposes_parameters():
    schema = tool_schema(TOOL_SPECS["search_keyword"].func)
    assert schema["properties"]["query"]["type"] == "string"
    assert "query" in schema["required"]
    assert schema["properties"]["limit"]["type"] == "integer"
    assert "ctx" not in schema["properties"]


def test_tool_schema_handles_optional_union():
    schema = tool_schema(TOOL_SPECS["get_work"].func)
    assert schema["properties"]["work_id"]["type"] == "string"
    assert "include_text" in schema["properties"]
