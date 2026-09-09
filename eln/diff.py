"""Structural comparison of two JSON documents, for round-trip checking.

The point is not to prove equality but to *classify* the divergence, because
the three kinds mean very different things for a round-trip:

``lost``     the original carried information the round-trip does not. The only
             kind that is a real failure.
``changed``  both carry a value at this path and they differ. Corruption —
             usually a rendering that was not reversed (a number that came back
             as a string, a unit collapsed to its label).
``added``    the round-trip carries information the original did not. Normally
             harmless: a payload writes ``"description": null`` for a key the
             source omitted. Reported, not fatal, unless ``--strict``.
``moved``    an entity came back at a different position in an ID-keyed list.
             Not a loss: merging per-entry payloads unions the entities in
             first-reference order, which need not be the document's order, and
             both schemas address these entities by ID rather than by index.

Absent, ``null`` and empty (``[]``, ``{}``, ``""``) are treated as the same
state, since that is what they mean in both schemas. A key that goes from
absent to ``[]`` is therefore silent; one that goes from three items to ``[]``
is ``lost``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterator, Optional

LOST, CHANGED, ADDED, MOVED = "lost", "changed", "added", "moved"

#: kinds that do not mean information was lost
BENIGN = (ADDED, MOVED)


def _empty(value: Any) -> bool:
    return value is None or value == [] or value == {} or value == ""


@dataclass(frozen=True)
class Delta:
    path: str
    kind: str
    left: Any
    right: Any

    def __str__(self) -> str:
        if self.kind == LOST:
            return f"lost     {self.path} = {_show(self.left)}"
        if self.kind == ADDED:
            return f"added    {self.path} = {_show(self.right)}"
        if self.kind == MOVED:
            return f"moved    {self.path}: index {self.left} -> {self.right}"
        return f"changed  {self.path}: {_show(self.left)} -> {_show(self.right)}"


def _show(value: Any, limit: int = 72) -> str:
    if isinstance(value, (dict, list)):
        kind = "object" if isinstance(value, dict) else "list"
        return f"<{kind} of {len(value)}>"
    text = repr(value)
    return text if len(text) <= limit else text[:limit - 1] + "…"


def _identity_key(left: list, right: list) -> Optional[str]:
    """A key that identifies the dicts in both lists, or None.

    Entity lists in these schemas (``compound``, ``small_molecules``, ``vessels``
    …) are addressed by ID, so position carries no meaning and comparing them
    positionally reports a reordering as a wall of spurious ``changed``. Falls
    back to positional comparison whenever the premise does not hold: short
    lists (where position is the better guess), non-dict items, no shared
    uniquely-valued key, or no overlap at all between the two sides.
    """
    if len(left) < 2 or len(right) < 2:
        return None
    items = left + right
    if not all(isinstance(i, dict) for i in items):
        return None

    shared = set(left[0])
    for item in items[1:]:
        shared &= set(item)

    def usable(key: str) -> bool:
        lv, rv = [i[key] for i in left], [i[key] for i in right]
        if any(isinstance(v, bool) or not isinstance(v, (str, int)) for v in lv + rv):
            return False
        return (len(set(lv)) == len(lv) and len(set(rv)) == len(rv)
                and bool(set(lv) & set(rv)))

    def rank(key: str) -> tuple[int, str]:
        low = key.lower()
        return (0 if low == "id" else 1 if low.endswith("id") else 2, key)

    return min((k for k in shared if usable(k)), key=rank, default=None)


def _compare_by_id(left: list, right: list, key: str, path: str) -> Iterator[Delta]:
    """Match two entity lists by ``key`` instead of by position."""
    right_at = {item[key]: i for i, item in enumerate(right)}
    for i, item in enumerate(left):
        ident = item[key]
        where = f"{path}[{key}={ident}]"
        if ident not in right_at:
            yield Delta(where, LOST, item, None)
            continue
        j = right_at[ident]
        if i != j:
            yield Delta(where, MOVED, i, j)
        yield from compare(item, right[j], where)
    seen = {item[key] for item in left}
    for item in right:
        if item[key] not in seen:
            yield Delta(f"{path}[{key}={item[key]}]", ADDED, None, item)


def compare(left: Any, right: Any, path: str = "$") -> Iterator[Delta]:
    """Yield the differences between two decoded JSON documents."""
    if _empty(left) and _empty(right):
        return
    if _empty(left) != _empty(right):
        yield Delta(path, ADDED if _empty(left) else LOST, left, right)
        return

    if isinstance(left, dict) and isinstance(right, dict):
        for key in list(left) + [k for k in right if k not in left]:
            yield from compare(left.get(key), right.get(key), f"{path}.{key}")
        return

    if isinstance(left, list) and isinstance(right, list):
        key = _identity_key(left, right)
        if key is not None:
            yield from _compare_by_id(left, right, key, path)
            return
        if len(left) != len(right):
            yield Delta(f"{path}[]", CHANGED,
                        f"{len(left)} items", f"{len(right)} items")
        for i in range(min(len(left), len(right))):
            yield from compare(left[i], right[i], f"{path}[{i}]")
        for i in range(len(right), len(left)):
            yield Delta(f"{path}[{i}]", LOST, left[i], None)
        for i in range(len(left), len(right)):
            yield Delta(f"{path}[{i}]", ADDED, None, right[i])
        return

    # A JSON round-trip preserves numbers exactly, so any inequality here is
    # genuine — except int/float, which compare equal and should stay equal.
    if type(left) is not type(right) and not (
            isinstance(left, (int, float)) and isinstance(right, (int, float))
            and not isinstance(left, bool) and not isinstance(right, bool)):
        yield Delta(path, CHANGED, left, right)
    elif left != right:
        yield Delta(path, CHANGED, left, right)


def summarise(deltas: list[Delta]) -> dict[str, int]:
    counts = {LOST: 0, CHANGED: 0, ADDED: 0, MOVED: 0}
    for d in deltas:
        counts[d.kind] = counts.get(d.kind, 0) + 1
    return counts


def report(deltas: list[Delta], *, strict: bool = False, limit: int = 25) -> tuple[str, bool]:
    """Render a verdict. Returns (text, ok).

    ``ok`` means no information was lost. Reordering and null filler are
    reported but do not fail the check unless ``strict``.
    """
    if not deltas:
        return "identical", True
    counts = summarise(deltas)
    fatal = sum(n for kind, n in counts.items()
                if strict or kind not in BENIGN)

    # Losses first: with a long tail of benign moves they would scroll away.
    ordered = sorted(deltas, key=lambda d: d.kind in BENIGN)
    lines = [str(d) for d in ordered[:limit]]
    if len(deltas) > limit:
        lines.append(f"… and {len(deltas) - limit} more")
    lines.append(", ".join(f"{n} {kind}" for kind, n in counts.items() if n))
    if not fatal:
        lines.append("no information lost")
    return "\n".join(lines), fatal == 0
