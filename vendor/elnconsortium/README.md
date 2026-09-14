# Vendored: The ELN Consortium's own conformance checks

| | |
|---|---|
| Source | <https://github.com/TheELNConsortium/TheELNFileFormat> |
| Commit | `401e7aa53da81446811a70e4902f69dae8a1d818` (2026-08-20) |
| Files | `tests/checks.py` → `checks.py`, `tests/schema.json` → `schema.json` |
| Licence | MIT, see `LICENSE` |

These files are **not ours and are not edited**. They are the same code that the
consortium's CI and its web checker (<https://tools.elnconsortium.org>) run, and
the point of copying them in is precisely that they are foreign: an export that
only satisfies our own `verify_eln.py` has been graded by the person who wrote
the exam.

The consortium publishes no pip package, so a copy at a pinned commit is the
only way to depend on this code. To update, re-download both files at a newer
commit and change the row above — do not patch them locally. If a check starts
failing after an update, that is a finding about our export, not a merge
conflict to resolve.

Run them with:

```bash
uv sync
uv run test/conformance.py some.eln
```

The fifth check, `checkValidator`, needs `roc-validator` and downloads SHACL
profiles on first run. Without it installed, `conformance.py` reports that check
as skipped rather than as passed — an unrun check is not a verdict.
