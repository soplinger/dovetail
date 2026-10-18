"""Command-line front end for dovetail."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import core

DESCRIPTION = (
    "Offline joinery layout planner: dovetail, box joint and tenon cut marks "
    "from plain-text joint files."
)


def _print_problems(source, problems, stream=None):
    for problem in problems:
        print(f"{source}:{problem.line}: {problem.level}: {problem.message}", file=stream)


def _print_layout(layout, units, diagram):
    print(f'{layout.kind} "{layout.name}" (line {layout.line}), span {core.fmt_length(layout.span, units)}')
    for measure in layout.measures:
        print(f"  {measure.label:<28}{core.format_measure(measure, units)}")
    if layout.segments:
        print("  cut marks:")
        for seg in layout.segments:
            start = core.fmt_length(seg.start, units)
            end = core.fmt_length(seg.end, units)
            print(f"    {seg.label:<10}{start:>12} -> {end}")
        if diagram:
            for row in core.diagram(layout):
                print(f"    {row}")
    for note in layout.notes:
        print(f"  note: {note}")
    print()


def _read(path):
    try:
        return Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        print(f"dovetail: cannot read {path}: {exc}", file=sys.stderr)
        return None


def cmd_check(args) -> int:
    text = _read(args.file)
    if text is None:
        return 2
    joints, problems = core.parse_text(text)
    _print_problems(args.file, problems)
    errors = sum(p.is_error for p in problems)
    warnings = len(problems) - errors
    print(f"{args.file}: {len(joints)} joint(s) ok, {errors} error(s), {warnings} warning(s)")
    return 1 if errors or (args.strict and warnings) else 0


def cmd_layout(args) -> int:
    text = _read(args.file)
    if text is None:
        return 2
    layouts, problems = core.analyze(text)
    _print_problems(args.file, problems)
    if args.name:
        layouts = [layout for layout in layouts if layout.name == args.name]
        if not layouts:
            print(f"no usable joint named {args.name!r}")
            return 1
    for layout in layouts:
        _print_layout(layout, args.units, args.diagram)
    return 1 if any(p.is_error for p in problems) else 0


def cmd_export(args) -> int:
    text = _read(args.file)
    if text is None:
        return 2
    layouts, problems = core.analyze(text)
    _print_problems(args.file, problems, stream=sys.stderr)
    payload = {"file": args.file, "joints": [core.layout_to_dict(layout) for layout in layouts]}
    print(json.dumps(payload, indent=2))
    return 1 if any(p.is_error for p in problems) else 0


def cmd_calc(args) -> int:
    text = f"{args.kind} calc {' '.join(args.pairs)}"
    layouts, problems = core.analyze(text, args.input_units)
    _print_problems("calc", problems)
    for layout in layouts:
        _print_layout(layout, args.units, args.diagram)
    return 1 if any(p.is_error for p in problems) else 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="dovetail", description=DESCRIPTION)
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="lint a joint file; exit 1 on errors")
    check.add_argument("file")
    check.add_argument("--strict", action="store_true", help="fail on warnings too")
    check.set_defaults(handler=cmd_check)

    layout = sub.add_parser("layout", help="print cut marks for each joint in a file")
    layout.add_argument("file")
    layout.add_argument("--name", help="only show the joint with this name")
    layout.add_argument("--units", choices=["mm", "in"], default="mm")
    layout.add_argument("--diagram", action="store_true", help="draw an ASCII board")
    layout.set_defaults(handler=cmd_layout)

    export = sub.add_parser("export", help="write every layout as JSON to stdout")
    export.add_argument("file")
    export.set_defaults(handler=cmd_export)

    calc = sub.add_parser("calc", help="lay out one joint given on the command line")
    calc.add_argument("kind", choices=sorted(core.KINDS))
    calc.add_argument("pairs", nargs="+", metavar="key=value")
    calc.add_argument("--input-units", choices=["mm", "in"], default="mm")
    calc.add_argument("--units", choices=["mm", "in"], default="mm")
    calc.add_argument("--diagram", action="store_true", help="draw an ASCII board")
    calc.set_defaults(handler=cmd_calc)

    args = parser.parse_args(argv)
    return args.handler(args)
