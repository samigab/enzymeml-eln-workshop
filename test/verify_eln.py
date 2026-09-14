#!/usr/bin/env python3
"""Structural check for a produced ``.eln`` package.

Verifies the invariants eLabFTW's importer and the ELN File Format spec rely on:

* exactly one root folder, with ``ro-crate-metadata.json`` directly inside it
* a ``./`` root Dataset described by the metadata descriptor
* every ``File`` node in the graph has a matching payload in the ZIP
* every ``{"@id": …}`` reference resolves to a node in the graph
* every payload in the ZIP is declared in the graph

Usage:
    python verify_eln.py out.eln [more.eln …]
"""

from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path


def _rel(crate_id: str) -> str:
    """Crate-relative path for a node ``@id``, ignoring a leading ``./``.

    Both spellings occur in the wild: ro-crate-py normalises to ``m0/data.csv``,
    eLabFTW's exporter writes ``./m0/data.csv``, and they denote the same file.
    Comparing without the prefix keeps this check about whether the payload is
    there, not about which spelling produced it.
    """
    return crate_id[2:] if crate_id.startswith("./") else crate_id


def _refs(node: dict):
    for key, value in node.items():
        if key == "@id":
            continue
        for item in (value if isinstance(value, list) else [value]):
            if isinstance(item, dict) and set(item) == {"@id"}:
                yield key, item["@id"]


def verify(path: Path) -> list[str]:
    problems: list[str] = []
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
        roots = {n.split("/")[0] for n in names}
        if len(roots) != 1:
            return [f"expected a single root folder, found {sorted(roots)}"]
        root = roots.pop()

        meta = [n for n in names if n == f"{root}/ro-crate-metadata.json"]
        if not meta:
            return [f"no {root}/ro-crate-metadata.json"]
        crate = json.loads(zf.read(meta[0]))

    graph = crate.get("@graph") or []
    ids = {n.get("@id") for n in graph}
    declared = {_rel(i) for i in ids if isinstance(i, str)}
    payloads = {n[len(root) + 1:] for n in names if n != meta[0]}

    if "./" not in ids:
        problems.append("no './' root Dataset node")
    descriptor = next((n for n in graph if n.get("@id") == "ro-crate-metadata.json"), None)
    if descriptor is None:
        problems.append("no metadata descriptor node")
    elif (descriptor.get("about") or {}).get("@id") != "./":
        problems.append("metadata descriptor does not describe './'")

    for node in graph:
        types = node.get("@type")
        types = types if isinstance(types, list) else [types]
        if "File" in types and _rel(node["@id"]) not in payloads:
            problems.append(f"File node without payload in ZIP: {node['@id']}")
        for key, ref in _refs(node):
            if ref not in ids and not ref.startswith("http"):
                problems.append(f"dangling {key} -> {ref} (from {node.get('@id')})")

    for payload in sorted(payloads):
        if payload not in declared:
            problems.append(f"payload in ZIP not declared in graph: {payload}")

    return problems


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    failed = False
    for arg in argv:
        path = Path(arg)
        problems = verify(path)
        print(f"{path.name}: {'OK' if not problems else str(len(problems)) + ' problem(s)'}")
        for p in problems:
            failed = True
            print(f"  - {p}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
