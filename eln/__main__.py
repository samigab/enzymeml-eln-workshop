"""CLI.

Export::  ``python -m eln <document.json> -o <out.eln>``
Import::  ``python -m eln <package.eln>   -o <back.json>``

The direction follows the input's suffix, so an ``.eln`` in means "read this
back". ``--against`` additionally diffs the result against the original
document, which is the round-trip check in one command.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import CONVERTERS, convert_file, import_file
from .diff import compare, report


def _export(args: argparse.Namespace) -> int:
    out = args.out or args.input.with_suffix(".eln")
    path, entries, resources = convert_file(
        args.input, out, schema=args.schema, grain=args.grain,
        links=args.links, plots=args.plots, csv=args.csv,
        category=args.category, license=args.license,
        embed_source=args.embed_source)

    n_files = sum(len(e.attachments) for e in entries)
    print(f"wrote {path}  ({len(entries)} entr{'y' if len(entries) == 1 else 'ies'}, "
          f"{len(resources)} resource item(s), {n_files} attachment(s))")
    return 0


def _import(args: argparse.Namespace) -> int:
    out = args.out or args.input.with_suffix(".json")
    doc, route, crate = import_file(args.input, out, schema=args.schema,
                                    route=args.route)
    print(f"wrote {out}  (from {len(crate.entries)} entr"
          f"{'y' if len(crate.entries) == 1 else 'ies'} via the {route!r} route)")

    if not args.against:
        return 0

    original = json.loads(Path(args.against).read_text(encoding="utf-8"))
    text, ok = report(list(compare(original, doc)), strict=args.strict)
    print(f"\nround-trip vs. {Path(args.against).name}: {text}")
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="python -m eln",
        description="Convert a FAIRFluids or EnzymeML v2 JSON document into an "
                    "ELN RO-Crate (.eln) for eLabFTW — or read one back.")
    p.add_argument("input", type=Path,
                   help="source document JSON, or an .eln package to import")
    p.add_argument("-o", "--out", type=Path,
                   help="output path (default: the input with the other suffix)")
    p.add_argument("--schema", choices=["auto", *CONVERTERS], default="auto",
                   help="source schema (default: auto-detect)")

    export = p.add_argument_group("export (JSON in)")
    export.add_argument("--grain", choices=["auto", "fluid", "measurement", "document"],
                        default="auto",
                        help="what becomes one eLabFTW entry (default: per fluid for "
                             "FAIRFluids, one entry for the whole document for "
                             "EnzymeML; use 'measurement' for aggregate documents)")
    export.add_argument("--links", action="store_true",
                        help="emit compounds/species as linked resource items")
    export.add_argument("--category", default="",
                        help="eLabFTW category name (default: the schema name)")
    export.add_argument("--license", default="",
                        help="licence URL or a sentence on reuse. RO-Crate "
                             "requires one and neither source schema has a field "
                             "for it, so without this the crate says that none "
                             "was stated rather than inventing one")
    export.add_argument("--no-plots", dest="plots", action="store_false",
                        help="do not attach auto-generated plots")
    export.add_argument("--no-csv", dest="csv", action="store_false",
                        help="do not attach flat CSV data tables")
    export.add_argument("--no-source", dest="embed_source", action="store_false",
                        help="do not attach the complete source document at the crate root")

    imp = p.add_argument_group("import (.eln in)")
    imp.add_argument("--from", dest="route", choices=["auto", "source", "entries"],
                     default="auto",
                     help="reconstruction route: the root source document, or a "
                          "merge of the per-entry payloads (default: auto)")
    imp.add_argument("--against", type=Path, metavar="ORIGINAL.json",
                     help="diff the reconstructed document against this file")
    imp.add_argument("--strict", action="store_true",
                     help="with --against, also fail on added null/empty filler")

    args = p.parse_args(argv)
    run = _import if args.input.suffix.lower() == ".eln" else _export
    try:
        return run(args)
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
