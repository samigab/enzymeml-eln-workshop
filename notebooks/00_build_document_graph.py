import marimo

__generated_with = "0.24.0"
app = marimo.App(
    width="full",
    app_title="Step 0 (graph) — build an EnzymeML document, one entity at a time",
)


@app.cell(hide_code=True)
def _():
    import marimo as mo

    return (mo,)


@app.cell(hide_code=True)
def _():
    import json

    from modelgraph import Step, forms, layout, next_key, replay
    from modelgraph.enzymeml import (
        FIELDS,
        MODELS,
        SINGLETONS,
        STEPS,
        build_document,
        choices,
        graph_of,
        label_for,
        node_keys,
        starter_log,
    )

    return (
        FIELDS,
        MODELS,
        SINGLETONS,
        STEPS,
        Step,
        build_document,
        choices,
        forms,
        graph_of,
        json,
        label_for,
        layout,
        next_key,
        node_keys,
        replay,
        starter_log,
    )


@app.cell(hide_code=True)
def _():
    from modelgraph import GraphWidget

    return (GraphWidget,)


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        """
        # Step 0 (graph) — one entity at a time

        An alternative to [notebook 0](00_build_document.py). That one starts
        from three CSV files and asks what the numbers do not say. This one
        starts from nothing and asks a different question: **what is a
        scientific data model actually made of?**

        The answer the graph gives, over and over, is *entities and the links
        between them*. Not a form, not a spreadsheet, not a file — a set of
        things that point at each other. Every record you add appears as a
        node; every reference you make appears as an edge you can follow.

        Read the three kinds of line in the picture:

        | line | means | example |
        |---|---|---|
        | solid, grey | **contains** — a field holds an object | `EnzymeMLDocument` → `Protein` |
        | dashed, amber | **references** — a field holds another object's `id` | `SmallMolecule.vessel_id` → `Vessel` |
        | dotted, faint | **is a** — an instance and its type | *Lipase* → `Protein` |

        The amber ones are the point. Nothing in the JSON's nesting shows them:
        they exist only because two strings match, and they are what turns the
        document from a tree into a graph.
        """
    )
    return


@app.cell(hide_code=True)
def _(Step, mo):
    # An empty document, so there is a root to grow from. `Document` is an
    # entity like any other, which is why its title is editable in step 1
    # rather than being a special case.
    INITIAL = [
        Step(
            "add",
            "Document",
            "doc",
            {"name": "Untitled experiment"},
            "Empty **EnzymeMLDocument** created",
        )
    ]
    get_log, set_log = mo.state(INITIAL)
    return INITIAL, get_log, set_log


@app.cell(hide_code=True)
def _(GraphWidget, mo):
    # No dependencies on purpose: the cell runs once, so the view stays mounted
    # for the session. Pan and zoom survive an edit, and a new node animates in
    # rather than the whole picture being rebuilt. Updates arrive by writing to
    # `gview.widget.graph` from the cell below.
    gview = mo.ui.anywidget(GraphWidget(height=520))
    return (gview,)


@app.cell(hide_code=True)
def _(get_log, mo):
    log = get_log()
    cursor = mo.ui.slider(
        0,
        len(log),
        value=len(log),
        full_width=True,
        show_value=True,
        label="**Step history** — drag back to replay how the document got here",
    )
    return cursor, log


@app.cell(hide_code=True)
def _(build_document, cursor, log, replay):
    # The entire state of the notebook, as one fold over the log. The document
    # is never mutated: it is rebuilt from step 1 every time anything changes,
    # which is what makes undo and history-replay the same operation.
    shown = log[: cursor.value]
    entities = replay(shown)
    doc, problems = build_document(entities)
    return doc, entities, problems, shown


@app.cell(hide_code=True)
def _(doc, graph_of, gview, layout, shown):
    graph = graph_of(doc)
    gview.widget.graph = layout(graph)
    gview.widget.caption = (
        f"step {len(shown)} · "
        + " · ".join(f"{count} × {name}" for name, count in graph.counts().items())
    )
    return (graph,)


@app.cell(hide_code=True)
def _(
    FIELDS,
    MODELS,
    Step,
    choices,
    cursor,
    entities,
    forms,
    graph,
    gview,
    label_for,
    mo,
    node_keys,
    problems,
    set_log,
):
    _selected = gview.value.get("selected", "")
    _key = node_keys(entities).get(_selected)
    _entity = entities.get(_key) if _key else None

    # Plain globals rather than a collection: `mo.ui.dictionary` clones what it
    # holds, and a cloned button arrives without its `on_click`.
    edit_form = None
    edit_submit = None

    if _entity is not None and _entity.kind in FIELDS:
        edit_form = forms.form_for(
            FIELDS[_entity.kind],
            entity=_entity,
            option_source=lambda source: choices(entities, source),
            label_source=lambda key: label_for(entities, key),
        )

        def _apply(_click, form=edit_form, key=_entity.key, kind=_entity.kind):
            """Change a property of the clicked node, and watch it propagate.

            The edit becomes an `update` step like any other, so it lands in
            the history, it can be undone, and the document — and therefore
            the JSON and the graph — is rebuilt from the log rather than
            patched in place.
            """
            props = forms.cleaned(form.value)
            set_log(
                lambda current: current[: cursor.value]
                + [
                    Step(
                        "update",
                        kind,
                        key,
                        props,
                        f"{kind} **{props.get('name') or key}** edited",
                    )
                ]
            )

        edit_submit = mo.ui.button(
            label="✓ Apply change", kind="success", on_click=_apply
        )
        _panel = mo.vstack(
            [
                mo.md("#### Edit this record"),
                forms.render(edit_form, FIELDS[_entity.kind], columns=1),
                edit_submit,
            ],
            gap=0.6,
        )
    else:
        _panel = mo.md("")

    mo.hstack(
        [
            mo.vstack([gview, cursor]),
            mo.vstack(
                [
                    forms.inspect_node(graph, _selected, MODELS),
                    _panel,
                    mo.callout(
                        mo.md(
                            "**The document would not build cleanly:**\n\n"
                            + "\n".join(f"- {p}" for p in problems)
                        ),
                        kind="warn",
                    )
                    if problems
                    else mo.md(""),
                    mo.callout(
                        mo.md(
                            "**References that point at nothing:**\n\n"
                            + "\n".join(
                                f"- `{source}` · `{relation}` = `{identifier}`"
                                for source, relation, identifier in graph.dangling
                            )
                            + "\n\nA document like this is still valid JSON. It "
                            "simply means nothing — which is exactly why the "
                            "edge is not drawn."
                        ),
                        kind="warn",
                    )
                    if graph.dangling
                    else mo.md(""),
                ]
            ),
        ],
        widths=[2, 1],
        gap=1.5,
        align="start",
    )
    return edit_form, edit_submit


@app.cell(hide_code=True)
def _(STEPS, mo):
    # One step at a time, rather than nine tabs. Partly because a guided flow
    # is the point, and partly because marimo only synchronises UI elements
    # bound to a global name: with a picker there is exactly one form and one
    # button on screen, and both can be plain globals. Elements generated in a
    # loop and hidden inside a collection are cloned, and a cloned button
    # loses its `on_click`.
    picker = mo.ui.radio(
        options={f"{n}. {title}": kind for n, (kind, title, _b) in enumerate(STEPS, 1)},
        value=f"1. {STEPS[0][1]}",
        inline=True,
        label="**What would you like to add?**",
    )

    mo.vstack(
        [
            mo.md(
                """
                ## Build the document

                The steps are in the order the model wants them: a species has
                to exist before a reaction can name it, and a measurement has
                to exist before its numbers can hang off it. You are free to
                skip around — the graph will just show you a reference that
                points at nothing until you fill the gap.
                """
            ),
            picker,
        ]
    )
    return (picker,)


@app.cell(hide_code=True)
def _(
    FIELDS,
    SINGLETONS,
    STEPS,
    Step,
    choices,
    cursor,
    entities,
    forms,
    label_for,
    log,
    mo,
    next_key,
    parse_series,
    picker,
    set_log,
    t_series,
):
    def _build(kind: str):
        # There is only ever one document, so its tab edits the one that exists
        # instead of offering to make a second. The form is seeded from it,
        # which is also what makes the tab usable as "change the title later".
        single = SINGLETONS.get(kind)
        form = forms.form_for(
            FIELDS[kind],
            entity=entities.get(single) if single else None,
            option_source=lambda source: choices(entities, source),
            label_source=lambda key: label_for(entities, key),
        )

        def add(_click, kind=kind, form=form, single=single):
            props = forms.cleaned(form.value)
            if kind == "SpeciesData":
                # Read at click time rather than taken as a dependency, so that
                # typing in the paste box does not empty the forms above.
                times, values, error = parse_series(t_series.value)
                if not error and times:
                    props |= {"time": times, "data": values}
            name = props.get("name") or props.get("species_id") or props.get("id")
            step = (
                Step("update", kind, single, props, f"{kind} **{name}** edited")
                if single
                else Step(
                    "add",
                    kind,
                    next_key(log, kind),
                    props,
                    f"{kind} **{name or kind}** added",
                )
            )
            # Appended at the cursor, not at the end: having dragged the slider
            # back and then added something, you meant to continue from there.
            set_log(lambda current: current[: cursor.value] + [step])

        return form, mo.ui.button(
            label=f"✓ Update {kind}" if single else f"＋ Add {kind}",
            kind="success",
            on_click=add,
        )

    # Both plain globals, so marimo synchronises them. The cell is not re-run
    # by its own elements changing, so typing in a field does not rebuild the
    # form under your cursor.
    entry, submit = _build(picker.value)
    _blurb = next(b for k, _t, b in STEPS if k == picker.value)

    mo.vstack(
        [mo.md(_blurb), forms.render(entry, FIELDS[picker.value]), submit],
        gap=0.8,
    )
    return entry, submit


@app.cell(hide_code=True)
def _():
    def parse_series(text: str) -> tuple[list[float], list[float], str | None]:
        """Numbers out of whatever the participant pasted.

        Two shapes are common and both are accepted: a column of `time value`
        pairs copied out of a spreadsheet, and two comma-separated lines copied
        out of a script. Guessing between them is cheaper than making somebody
        reformat data during a workshop.
        """
        lines = [line for line in (text or "").strip().splitlines() if line.strip()]
        try:
            if len(lines) == 2 and ("," in lines[0] or len(lines[0].split()) > 2):
                rows = [
                    [float(v) for v in line.replace(",", " ").split()]
                    for line in lines
                ]
                return rows[0], rows[1], None
            times, values = [], []
            for line in lines:
                parts = line.replace(",", " ").split()
                if len(parts) >= 2:
                    times.append(float(parts[0]))
                    values.append(float(parts[1]))
            return times, values, None
        except ValueError as exc:
            return [], [], str(exc)

    return (parse_series,)


@app.cell(hide_code=True)
def _(mo):
    # Deliberately its own cell, and read only inside the Add callback. If the
    # tab panels depended on the parsed numbers, every keystroke here would
    # rebuild the forms above and empty them.
    t_series = mo.ui.text_area(
        label="**Time and values** — two columns, one pair per line "
        "(`0 2.0`), or two lines of comma-separated numbers",
        rows=4,
        full_width=True,
        placeholder="0, 2, 4, 6, 8, 10\n2.0, 1.73, 1.5, 1.3, 1.12, 0.97",
    )
    return (t_series,)


@app.cell(hide_code=True)
def _(mo, parse_series, t_series):
    _times, _values, _error = parse_series(t_series.value)

    mo.vstack(
        [
            mo.md(
                """
                ### The numbers

                Paste a time series here and it is attached to the next
                **SpeciesData** you add. Leave it empty and that entry records
                only an initial concentration — which is still data: you
                pipetted it, you just did not follow it.
                """
            ),
            t_series,
            mo.callout(
                mo.md(f"**Could not read the numbers**\n\n> `{_error}`"), kind="warn"
            )
            if _error
            else mo.md(
                f"✅ &nbsp;**{len(_times)} point(s)** ready to attach."
                if _times
                else "*Empty — the next SpeciesData will carry an initial value only.*"
            ),
        ]
    )
    return


@app.cell(hide_code=True)
def _(INITIAL, log, mo, set_log, shown, starter_log):
    b_undo = mo.ui.button(
        label="↶ Undo last step",
        on_click=lambda _: set_log(lambda c: c[:-1] if len(c) > 1 else c),
        disabled=len(log) < 2,
    )
    b_reset = mo.ui.button(
        label="⟲ Start over", on_click=lambda _: set_log(list(INITIAL))
    )
    b_example = mo.ui.button(
        label="⏵ Load the worked example",
        on_click=lambda _: set_log(starter_log()),
    )

    mo.vstack(
        [
            mo.md("## History"),
            mo.md(
                "*Sixteen steps of somebody else's experiment, replayed with "
                "the slider, is the fastest way to see what the graph is for.*"
            ),
            mo.hstack([b_undo, b_reset, b_example], justify="start", gap=0.5),
            mo.md(
                "\n".join(
                    f"{i}. "
                    + (step.describe() if i <= len(shown) else f"~~{step.describe()}~~")
                    + (" ← *you are here*" if i == len(shown) else "")
                    for i, step in enumerate(log, 1)
                )
            ),
        ]
    )
    return


@app.cell(hide_code=True)
def _(doc, json, mo):
    _document = json.loads(doc.model_dump_json(exclude_none=True))
    _payload = (json.dumps(_document, indent=2, ensure_ascii=False) + "\n").encode()

    mo.vstack(
        [
            mo.md(
                f"""
                ## The file

                **{len(_payload):,} bytes**, generated from the same object the
                graph was drawn from. There is no step in between where the
                picture and the file could disagree — and this is a real
                `pyenzyme.EnzymeMLDocument`, so
                [step 1](01_export_eln.py) will read it without knowing where
                it came from.
                """
            ),
            mo.ui.tabs(
                {
                    "Tree": mo.json(_document),
                    "Raw JSON": mo.md(
                        "```json\n"
                        + json.dumps(_document, indent=2, ensure_ascii=False)
                        + "\n```"
                    ),
                }
            ),
            mo.download(
                data=_payload,
                filename="kinetics.json",
                mimetype="application/json",
                label=f"⬇ kinetics.json ({max(1, len(_payload) // 1024)} KB)",
            ),
        ]
    )
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        """
        ---
        ### Next

        Download `kinetics.json` and take it to
        **[step 1](01_export_eln.py)**, which turns any such document into a
        lab notebook entry. Nothing there knows this one exists.

        **If you came here from [notebook 0](00_build_document.py)**, the two
        are worth comparing. That one shows what a measurement leaves behind
        and what has to be added to it; this one shows what the thing you are
        adding it *to* is actually shaped like. Same document, same library,
        two different questions.
        """
    )
    return


if __name__ == "__main__":
    app.run()
