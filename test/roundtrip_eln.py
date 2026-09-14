#!/usr/bin/env python3
"""Round-trip check: does a document survive the conversion to an ELN entry?

Exports a source document to ``.eln``, reads it back and diffs the result
against the original — once per reconstruction route:

``source``   reads ``source.document.json`` from the crate root. Must be
             identical; if it is not, the export corrupted the payload.
``entries``  rebuilds the document by merging the per-entry payloads. This is
             the honest test of the mapping: whatever the grain split apart has
             to fit back together. Divergences here are the interesting ones —
             they are exactly what a foreign ELN would fail to give back.

Usage:
    python roundtrip_eln.py examples/enzymeml_v2.example.json [--grain document]
    python roundtrip_eln.py fairfluids.json --strict
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from eln import pick, roundtrip
from eln.diff import report


def check(path: Path, *, strict: bool, grain: str, limit: int) -> bool:
    print(f"\n=== {path.name} ===")
    ok_all = True
    for route in ("source", "entries"):
        try:
            original, _, deltas = roundtrip(path, route=route, grain=grain,
                                            plots=False, csv=False)
        except ValueError as exc:
            print(f"  {route:8} error: {exc}")
            ok_all = False
            continue

        # Losses the schema module declares as structurally unavoidable are
        # reported as such, so that a *new* loss still fails the check.
        expected = set(getattr(pick(original), "EXPECTED_LOSS", ()))
        deltas = [d for d in deltas if d.path not in expected]

        text, ok = report(deltas, strict=strict, limit=limit)
        head, *rest = text.split("\n")
        print(f"  {route:8} {head}")
        for line in rest:
            print(f"           {line}")
        if expected and route == "entries":
            print(f"           ({len(expected)} declared in "
                  f"{pick(original).SCHEMA}.EXPECTED_LOSS, not counted)")
        ok_all = ok_all and ok
    return ok_all


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="roundtrip_eln.py",
                                description=__doc__.split("\n\n")[0])
    p.add_argument("inputs", nargs="+", type=Path, help="source document(s)")
    p.add_argument("--grain", default="auto",
                   choices=["auto", "fluid", "measurement", "document"])
    p.add_argument("--strict", action="store_true",
                   help="also fail on added null/empty filler")
    p.add_argument("--limit", type=int, default=15,
                   help="max differences to list per route (default: 15)")
    args = p.parse_args(argv)

    ok = all([check(path, strict=args.strict, grain=args.grain, limit=args.limit)
              for path in args.inputs])
    print()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
