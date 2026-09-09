#!/usr/bin/env python3
"""Show which metadata fields of the workshop document are still open.

JSON has no comments, so what belongs where is written down here instead. The
list is both the assignment and the progress bar:

    python workshop_todo.py examples/workshop/kinetics.skeleton.json

Deliberately *metadata* only. The data blocks (``time``/``data`` inside the
measurements) are given in full — nobody learns anything by typing out a time
series, and they are not what a lab notebook takes off your hands.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# (section, list in the document or None for the document itself,
#  [(field, hint)], only these IDs or None for all)
#
# NAD+ and NADH are deliberately annotated already: they show the target state,
# and their InChI strings are nothing anyone should retype. The work happens on
# ethanol and acetaldehyde.
TODO: list[tuple[str, str | None, list[tuple[str, str]], tuple[str, ...] | None]] = [
    ("Document", None, [
        ("name", "Title of the experiment — what you will search for in two "
                 "years. On the shared demo instance: append your initials, or "
                 "every entry will have the same name"),
        ("description", "One or two sentences: what was measured, and why"),
        ("creators", "Who measured: given_name, family_name, mail. CAREFUL on "
                     "the public demo: the entry is visible to everyone — use "
                     "a placeholder, not a private address"),
        ("references", "DOI or URL of the method/publication, as a list"),
    ], None),
    ("Vessel", "vessels", [
        ("name", "What it was measured in, e.g. 'quartz cuvette 1 cm'"),
        ("volume", "Reaction volume as a number (the unit is set: ml)"),
    ], None),
    ("Enzyme", "proteins", [
        ("name", "Common name of the enzyme"),
        ("ecnumber", "EC number — UniProt has it"),
        ("organism", "Scientific name of the source organism"),
        ("organism_tax_id", "NCBI taxonomy ID, as a string"),
        ("sequence", "Amino acid sequence in one-letter code"),
        ("references", "UniProt URL, as a list"),
    ], None),
    ("Compounds", "small_molecules", [
        ("name", "Name of the compound"),
        ("inchikey", "InChIKey — the identifier machines recognise the "
                     "compound by"),
        ("inchi", "Full InChI"),
        ("canonical_smiles", "SMILES"),
        ("synonymous_names", "Common synonyms, as a list"),
        ("references", "PubChem or ChEBI URL, as a list"),
    ], ("s_etoh", "s_acetald")),
    ("Measurements", "measurements", [
        ("name", "A name that says something, e.g. 'ethanol 8 mM'"),
        ("group_id", "The same ID for every measurement of one series — that "
                     "is how you tell later that they belong together"),
        ("ph", "pH of the buffer, as a number"),
        ("temperature", "Temperature, as a number (the unit is set: °C)"),
    ], None),
]


def _open(value) -> bool:
    """Counts as open: missing, null, empty string, empty list/object."""
    return value is None or value == "" or value == [] or value == {}


def _items(doc: dict, list_key: str | None,
           only: tuple[str, ...] | None) -> list[tuple[str, dict]]:
    if list_key is None:
        return [("", doc)]
    return [(str(item.get("id") or i), item)
            for i, item in enumerate(doc.get(list_key) or [])
            if only is None or item.get("id") in only]


def check(path: Path) -> int:
    doc = json.loads(path.read_text(encoding="utf-8"))
    print(f"\n=== {path.name} ===")
    total = done = 0

    for section, list_key, fields, only in TODO:
        items = _items(doc, list_key, only)
        # One line per field, with who is still missing it behind — otherwise
        # the same hint repeats once per measurement.
        rows = []
        for field, hint in fields:
            missing = [ident for ident, item in items if _open(item.get(field))]
            total += len(items)
            done += len(items) - len(missing)
            if missing:
                where = f"  [{', '.join(missing)}]" if any(missing) else ""
                rows.append((field, where, hint))
        if rows:
            print(f"\n{section}")
            for field, where, hint in rows:
                print(f"  open   {field:18}{where}")
                print(f"         {hint}")

    todo = total - done
    print(f"\n{done}/{total} metadata fields filled", end="")
    print(" — complete!" if not todo else f", {todo} still open")
    if not todo:
        print(f"\nNow export it:\n"
              f"  python -m eln {path} -o kinetics.eln --links\n"
              f"  python -m eln kinetics.eln -o back.json --from entries "
              f"--against {path}")
    return todo


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    todo = sum(check(Path(a)) for a in argv)
    print()
    return 0 if todo == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
