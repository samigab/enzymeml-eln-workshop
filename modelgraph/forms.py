"""Marimo inputs generated from a list of `FormField`s.

The one module in the package that imports marimo. It exists so the notebooks
can stay about the workshop rather than about widget plumbing: a step in the
guided flow is `form_for("Protein", entities)` and a button, not forty lines of
`mo.ui.text(label=...)`.

Generating the inputs from the same declaration the builder reads also removes
a class of bug the workshop cannot afford — a form that asks for a field the
document does not have, or quietly fails to ask for one it does.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping, Sequence

import marimo as mo

from .graph import describe_class
from .store import Entity, FormField


def input_for(
    spec: FormField,
    *,
    value: Any = None,
    options: Sequence[str] = (),
    labels: Callable[[str], str] | None = None,
) -> Any:
    """One `FormField` as one marimo input."""
    label = f"**{spec.label}**" + (" *" if spec.required else "")
    current = spec.default if value is None else value

    if spec.kind == "switch":
        return mo.ui.switch(value=bool(current), label=label)
    if spec.kind == "number":
        return mo.ui.number(
            value=None if current in ("", None) else float(current), label=label
        )
    if spec.kind == "area":
        return mo.ui.text_area(
            value=str(current or ""), label=label, rows=3, full_width=True,
            placeholder=spec.placeholder,
        )
    if spec.kind == "select":
        # A dropdown of what exists beats a text field that can hold a typo:
        # the participant still creates the reference, but cannot create a
        # broken one. `None` stays selectable so a field can be left open.
        choices = list(options) if spec.choices_from else list(spec.choices)
        if labels is not None:
            pairs = {labels(c): c for c in choices}
        else:
            pairs = {c: c for c in choices}
        chosen = current if current in choices else (choices[0] if choices else None)
        selected = next((k for k, v in pairs.items() if v == chosen), None)
        return mo.ui.dropdown(
            options=pairs,
            value=selected,
            label=label,
            # A required field would normally forbid the empty choice, but at
            # the start of the workshop there is nothing to choose from yet —
            # there are no vessels until somebody adds one. Insisting on a
            # value that cannot exist raises rather than guiding.
            allow_select_none=selected is None or not spec.required,
        )
    return mo.ui.text(
        value=str(current or ""), label=label, full_width=True,
        placeholder=spec.placeholder,
    )


def form_for(
    fields: Sequence[FormField],
    *,
    entity: Entity | None = None,
    option_source: Callable[[str], Sequence[str]] | None = None,
    label_source: Callable[[str], str] | None = None,
) -> mo.ui.dictionary:
    """A whole form as one reactive object.

    `mo.ui.dictionary` rather than several loose elements: its `.value` is the
    dict the store wants, so appending a step is `Step("add", kind, key,
    form.value)` and nothing has to know the field names twice.
    """
    elements = {}
    for spec in fields:
        options = (
            option_source(spec.choices_from)
            if spec.choices_from and option_source
            else ()
        )
        elements[spec.name] = input_for(
            spec,
            value=entity.props.get(spec.name) if entity else None,
            options=options,
            labels=label_source if spec.choices_from else None,
        )
    return mo.ui.dictionary(elements)


def render(form: mo.ui.dictionary, fields: Sequence[FormField], *, columns: int = 2):
    """The form laid out, with each field's hint under it."""
    cells = []
    for spec in fields:
        element = form.elements[spec.name]
        # An empty reference dropdown is the commonest confusion in the guided
        # flow: the field is there, it is marked required, and it offers
        # nothing. Say what is missing instead of leaving them to guess.
        empty = spec.choices_from and not getattr(element, "options", None)
        note = (
            f"nothing to point at yet — add a **{spec.needs or spec.choices_from}** "
            "first"
            if empty
            else spec.hint
        )
        cells.append(
            mo.vstack(
                [element] + ([mo.md(f"<small>{note}</small>")] if note else []),
                gap=0.1,
            )
        )
    rows = [
        mo.hstack(cells[i : i + columns], widths="equal", gap=1, align="start")
        for i in range(0, len(cells), columns)
    ]
    return mo.vstack(rows, gap=0.6)


def inspect_node(graph, node_id: str, models: Mapping[str, Any]):
    """What the panel beside the graph shows for the clicked node.

    A class node and an instance node answer different questions. Click
    `Angestellter` and you are asking *what can this kind of thing hold?*,
    which the pydantic model answers. Click `Anna Müller` and you are asking
    *what does this one actually hold?*, which the document answers. Showing
    the same panel for both would blur the distinction the graph exists to
    make.
    """
    node = graph.node(node_id) if node_id else None
    if node is None:
        types = graph.counts()
        return mo.vstack([
            mo.md("### Nothing selected\n\n*Click a node in the graph.*"),
            mo.md(
                "| type | instances |\n|---|--:|\n"
                + "\n".join(f"| `{name}` | {count} |" for name, count in types.items())
            ) if types else mo.md(""),
        ])

    if node.kind == "class":
        model = models.get(node.type)
        rows = describe_class(model) if model is not None else {}
        instances = [
            e.source for e in graph.edges
            if e.kind == "instanceOf" and e.target == node.id
        ]
        return mo.vstack([
            mo.md(f"### `{node.type}`\n\n*a type — not one of your records*"),
            mo.md(
                "**JSON-LD type:** " + ", ".join(f"`{t}`" for t in node.ld_type)
            ) if node.ld_type else mo.md(""),
            mo.md(f"**{len(instances)} instance(s)** in this document."),
            mo.md(
                "**Fields this type can hold**\n\n| field | type |\n|---|---|\n"
                + "\n".join(f"| `{k}` | {v} |" for k, v in rows.items())
            ) if rows else mo.md(""),
        ])

    links = [
        (e.relation, e.target)
        for e in graph.edges
        if e.source == node.id and e.kind == "reference"
    ]
    return mo.vstack([
        mo.md(f"### {node.label}\n\n`{node.type}` &nbsp;·&nbsp; `{node.path}`"),
        mo.md(
            "| property | value |\n|---|---|\n"
            + "\n".join(f"| `{k}` | {v} |" for k, v in node.properties.items())
        ) if node.properties else mo.callout(
            mo.md("**No properties set yet.**"), kind="neutral"),
        mo.md(
            "**Points at**\n\n"
            + "\n".join(f"- `{rel}` → `{target}`" for rel, target in links)
        ) if links else mo.md(""),
        mo.md(
            "**JSON-LD type:** " + ", ".join(f"`{t}`" for t in node.ld_type)
        ) if node.ld_type else mo.md(""),
    ])


def cleaned(values: Mapping[str, Any]) -> dict[str, Any]:
    """Form values with the blanks dropped.

    A field the participant never touched should not end up in the document as
    an empty string. `""` and *absent* mean different things in a FAIR record,
    and only one of them is honest.
    """
    return {
        key: value
        for key, value in values.items()
        if value not in (None, "") or isinstance(value, bool)
    }
