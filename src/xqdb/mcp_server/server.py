import argparse
from functools import partial
from pathlib import Path

from ..tools.context import tool_context
from ..tools.registry import TOOL_SPECS


def create_server(ctx, *, allow_admin: bool = False):
    from mcp.server.fastmcp import FastMCP

    server = FastMCP("xqdb")
    for name, spec in TOOL_SPECS.items():
        if spec.admin and not allow_admin:
            continue
        bound = partial(spec.func, ctx)
        bound.__name__ = name
        bound.__doc__ = spec.description
        server.add_tool(bound, name=name, description=spec.description)
    return server


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="xqdb-mcp")
    parser.add_argument("--root", default=None)
    parser.add_argument("--allow-admin", action="store_true")
    args = parser.parse_args(argv)

    root = Path(args.root) if args.root else None
    with tool_context(root) as ctx:
        create_server(ctx, allow_admin=args.allow_admin).run()
    return 0
