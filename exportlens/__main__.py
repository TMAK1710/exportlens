"""python -m exportlens compare source.json target.json --output report/"""
import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .compare import SnapshotError, compare
from .report import write_report


def _read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Compare Blender source and Unity imported FBX snapshots locally.")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)
    command = sub.add_parser("compare", help="Write offline JSON and HTML reports")
    command.add_argument("source", help="Blender .source.json snapshot")
    command.add_argument("target", help="Unity .unity.json snapshot")
    command.add_argument("--output", required=True, help="Report directory")
    command.add_argument("--config", help="Optional tolerance and mesh_map JSON")
    args = parser.parse_args(argv)
    try:
        result = compare(_read(args.source), _read(args.target), _read(args.config) if args.config else None)
        write_report(result, args.output)
    except (OSError, UnicodeError, ValueError, RecursionError) as error:
        print(f"ExportLens: {error}", file=sys.stderr)
        return 2
    print(f"{result['status'].upper()}: {result['summary']['errors']} errors, {result['summary']['warnings']} warnings, {result['summary']['info']} notes")
    print(f"Report: {Path(args.output).resolve() / 'report.html'}")
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
