"""An append-only log of edits, and the entities it replays into.

The notebooks that use this never mutate a document. They append a `Step`, and
the document is rebuilt from the whole log every time. That is what makes the
two features a workshop actually needs — *undo* and *show me the model as it
stood after step 3* — one expression each rather than a feature:

    replay(log[:-1])        # undo
    replay(log[:3])         # step 3

It is also what keeps the notebook honest under marimo's reactive execution. A
cell that mutates a document accumulates its edits every time it re-runs; a
cell that folds a list does not, no matter how often it runs.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Iterable, Mapping, Sequence


@dataclass(frozen=True)
class Step:
    """One edit. The unit of history, and of undo.

    `key` is the handle the log uses to talk about an entity across steps: an
    `update` finds its target by it, a `remove` deletes it. It is not the
    entity's own identifier — that lives in `props` and the participant is free
    to change it, which is exactly why the log cannot use it as a handle.
    """

    op: str  # "add" | "update" | "remove"
    kind: str  # entity type, e.g. "Protein"
    key: str
    props: Mapping[str, Any] = field(default_factory=dict)
    note: str = ""

    def describe(self) -> str:
        if self.note:
            return self.note
        verb = {"add": "added", "update": "edited", "remove": "removed"}
        return f"{verb.get(self.op, self.op)} {self.kind} `{self.key}`"


@dataclass(frozen=True)
class Entity:
    """A record in the replayed state: a kind, a handle, and a bag of values.

    Deliberately not a pydantic model. This is the *input* to constructing one,
    and it has to survive being half-filled — a participant who has typed a
    protein's name but not yet its sequence still wants to see the node appear.
    """

    kind: str
    key: str
    props: Mapping[str, Any] = field(default_factory=dict)

    def get(self, name: str, default: Any = None) -> Any:
        value = self.props.get(name, default)
        return default if value is None or value == "" else value

    def text(self, name: str, default: str = "") -> str:
        value = self.props.get(name)
        return str(value).strip() if value not in (None, "") else default

    def number(self, name: str, default: float | None = None) -> float | None:
        try:
            return float(str(self.props.get(name)).strip())
        except (TypeError, ValueError):
            return default

    def flag(self, name: str, default: bool = False) -> bool:
        value = self.props.get(name)
        if isinstance(value, bool):
            return value
        if value in (None, ""):
            return default
        return str(value).strip().lower() in ("true", "yes", "y", "1")


@dataclass(frozen=True)
class FormField:
    """How to ask for one property.

    Lives here, next to `Entity`, rather than in a domain module, because both
    `toy.py` and `enzymeml.py` declare their forms with it and neither should
    have to import the other. `forms.py` turns these into marimo inputs; the
    builders read the same declarations back.

    `choices_from` is the interesting one: it says *this field points at
    another entity*, and the notebook turns it into a dropdown of what has
    actually been declared. A reference you can only pick, not mistype, is a
    reference that cannot dangle — and the participant still sees the dashed
    edge appear and learns what it means.
    """

    name: str
    label: str
    kind: str = "text"  # text | area | number | switch | select
    default: Any = ""
    choices: tuple[str, ...] = ()
    choices_from: str = ""
    placeholder: str = ""
    hint: str = ""
    required: bool = False
    #: What has to exist before this dropdown has anything in it, in words.
    #: Shown under an empty reference field — the commonest confusion in the
    #: guided flow is a required field that offers nothing.
    needs: str = ""


def replay(steps: Sequence[Step]) -> dict[str, Entity]:
    """Fold the log into the entities it describes, in insertion order."""
    state: dict[str, Entity] = {}
    for step in steps:
        if step.op == "add":
            state[step.key] = Entity(step.kind, step.key, dict(step.props))
        elif step.op == "update":
            current = state.get(step.key)
            if current is not None:
                state[step.key] = replace(
                    current, props={**current.props, **step.props}
                )
        elif step.op == "remove":
            state.pop(step.key, None)
            # A container going away takes its contents with it: an employee
            # whose department was removed is not a free-floating employee.
            for key, entity in list(state.items()):
                if step.key in entity.props.values():
                    state.pop(key, None)
    return state


def of_kind(entities: Mapping[str, Entity], *kinds: str) -> list[Entity]:
    return [e for e in entities.values() if e.kind in kinds]


def children_of(
    entities: Mapping[str, Entity], parent_key: str, *, via: str, kind: str | None = None
) -> list[Entity]:
    """Entities that name `parent_key` in their `via` property.

    The log is flat and the model is nested, so somewhere the nesting has to be
    reconstructed. It happens here, once, rather than in every builder.
    """
    return [
        e
        for e in entities.values()
        if e.props.get(via) == parent_key and (kind is None or e.kind == kind)
    ]


def next_key(steps: Iterable[Step], kind: str) -> str:
    """A handle no earlier step has used.

    Counted over the whole log rather than over the live entities, so a key
    freed by a `remove` is never handed out again. Reusing one would make an
    undo resurrect the wrong object.
    """
    used = sum(1 for s in steps if s.op == "add" and s.kind == kind)
    return f"{kind.lower()}_{used + 1}"
