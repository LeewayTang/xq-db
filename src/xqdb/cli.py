import argparse
from collections.abc import Sequence

from . import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="xqdb")
    parser.add_argument("--root", default=None, help="仓库根目录，默认当前目录")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("version", help="打印版本")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "version":
        print(f"xqdb {__version__}")
        return 0
    return 1
