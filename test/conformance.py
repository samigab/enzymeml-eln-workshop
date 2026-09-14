#!/usr/bin/env python3
"""Grade an ``.eln`` file with the ELN Consortium's own checks, not with ours.

``verify_eln.py`` asks whether a package matches what *this* converter intended.
This script asks the harder question: whether it matches what the format's
maintainers accept. The checks in ``vendor/elnconsortium/checks.py`` are a
verbatim copy of the suite behind the consortium's CI and their web checker, so
a pass here means an independent implementation agrees.

    uv run --group checks conformance.py out/kinetics.eln

Exits non-zero if any check fails, so it can gate a release.
"""

from __future__ import annotations

import sys
import types
import warnings
from pathlib import Path

# The vendored file is kept verbatim, so its two invalid escape sequences stay
# in — silenced here rather than patched there. See vendor/elnconsortium/README.
warnings.filterwarnings("ignore", category=SyntaxWarning)

VENDOR = Path(__file__).resolve().parent.parent / "vendor" / "elnconsortium"

# Failures we have looked at and decided not to chase. Each entry is
# (check label, substring, reason); a check whose every complaint matches one of
# these is reported as a note instead of a failure. A check with even one
# unmatched complaint still fails, so this cannot quietly swallow a regression.
DECLARED = (
    (
        "Schema",
        "is not of type 'object'",
        "an entry with two authors emits `author` as a list of references. "
        "The consortium's schema.json types `author` as an object only, but "
        "RO-Crate is JSON-LD, where any property may carry multiple values, and "
        "schema.org places no cardinality limit on author. Dropping a co-author "
        "to satisfy the check would be the actual data loss.",
    ),
    (
        "Validator",
        "ro-crate-1.1_5.3",
        "we declare conformance to RO-Crate 1.2 while checks.py pins the SHACL "
        "validator to the 1.1 profile. Its own comment calls that a stop-gap "
        "'because the validator currently does not support the latest ro-crate "
        "version', and it rewrites 1.2 to 1.1 for a hard-coded list of "
        "publishers before validating. eLabFTW, whose importer this targets, "
        "declares 1.2 as well. Downgrading to be graded would misstate what we "
        "produce; being on that list is not something to arrange for ourselves.",
    ),
    ("Validator", "is not valid", "see the ro-crate-1.1_5.3 note above"),
)


def _declared(label: str, log: str):
    """Return the reason if every complaint in *log* is a declared deviation."""
    lines = [line for line in str(log).strip().splitlines() if line.strip()]
    if not lines:
        return None
    reasons = set()
    for line in lines:
        hit = next((r for lbl, sub, r in DECLARED if lbl == label and sub in line), None)
        if hit is None:
            return None
        reasons.add(hit)
    return " / ".join(sorted(reasons))


def _load_checks():
    """Import the vendored suite, tolerating a missing SHACL validator.

    ``checks.py`` imports ``rocrate_validator`` at module level, so without it
    nothing at all can run — including the four checks that do not need it. A
    placeholder module keeps the import working; ``checkValidator`` then fails
    on the placeholder and is reported as skipped rather than as a failure,
    which is honest: we did not run it, we do not know its verdict.
    """
    sys.path.insert(0, str(VENDOR))
    try:
        import rocrate_validator  # noqa: F401
        available = True
    except ImportError:
        stub = types.ModuleType("rocrate_validator")
        stub.services = stub.models = None
        sys.modules["rocrate_validator"] = stub
        available = False
    import checks
    return checks, available


def main(argv: list[str]) -> int:
    paths = [Path(a) for a in argv[1:]]
    if not paths:
        print(__doc__)
        return 2

    try:
        checks, shacl = _load_checks()
    except ImportError as exc:
        print(f"the vendored checks need their dependencies: {exc}")
        print("install them with:  uv sync --group checks")
        return 2

    failed = False
    for path in paths:
        print(f"\n=== {path.name}")
        for label, check in checks.ALL_CHECKS:
            if check is checks.checkValidator and not shacl:
                print(f"  SKIP  {label}  (needs roc-validator)")
                continue
            try:
                ok, log = check(path)
            except Exception as exc:  # a check that dies is a failure, not a crash
                ok, log = False, f"the check itself raised: {exc!r}"
            reason = None if ok else _declared(label, log)
            if reason:
                print(f"  note  {label}  (declared deviation)")
                print(f"        {reason}")
                continue
            print(f"  {'ok  ' if ok else 'FAIL'}  {label}")
            if not ok:
                failed = True
                for line in str(log).strip().splitlines():
                    print(f"        {line}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
