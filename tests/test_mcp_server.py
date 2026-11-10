import pytest


def test_create_server_registers_non_admin_tools(ctx):
    pytest.importorskip("mcp")
    from xqdb.mcp_server.server import create_server
    server = create_server(ctx)
    names = {tool.name for tool in server._tool_manager.list_tools()}
    assert "search_keyword" in names
    assert "ingest_run" not in names


def test_admin_opt_in(ctx):
    pytest.importorskip("mcp")
    from xqdb.mcp_server.server import create_server
    server = create_server(ctx, allow_admin=True)
    names = {tool.name for tool in server._tool_manager.list_tools()}
    assert "ingest_run" in names
