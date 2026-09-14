import marimo

__generated_with = "0.24.0"
app = marimo.App(
    width="full",
    app_title="Step 0 (toy) — watch a data model grow",
)


@app.cell(hide_code=True)
def _():
    import marimo as mo

    return (mo,)


@app.cell(hide_code=True)
def _():
    from modelgraph import (
        GraphWidget,
        Step,
        build_graph,
        forms,
        layout,
        next_key,
        replay,
    )
    from modelgraph.toy import (
        FIELDS,
        MODELS,
        SINGLETONS,
        STEPS,
        build_firma,
        choices,
        example_log,
        label_for,
        node_keys,
    )

    return (
        FIELDS,
        GraphWidget,
        MODELS,
        SINGLETONS,
        STEPS,
        Step,
        build_firma,
        build_graph,
        choices,
        example_log,
        forms,
        label_for,
        layout,
        next_key,
        node_keys,
        replay,
    )


@app.cell(hide_code=True)
def _(mo):
    mo.md(
        """
        # Step 0 (toy) — watch a data model grow

        Before EnzymeML, a model small enough to hold in your head: a company,
        its departments, the people in them, and what they cost. Every
        mechanism the [EnzymeML version](00_build_document_graph.py) uses is
        already here, and here you can see all of it at once.

        Three things are worth watching as you add records:

        1. **A type is not an instance.** `Angestellter` is a dashed node and
           there is exactly one of it. *Anna Müller* is a solid node, and so is
           *Peter Schmidt*, and adding a third employee adds a third node.
           Nothing merges.
        2. **The edges are labelled with the real field names.** `angestellte`,
           `leiter`, `geld` — the same keys you will find in the JSON below.
           Nothing here is invented for the picture.
        3. **The picture is derived, not maintained.** The graph is read off
           the pydantic object every time it changes. There is no second copy
           of your data anywhere in this notebook.
        """
    )
    return


@app.cell(hide_code=True)
def _(Step, mo):
    # A company with no departments — one node, so there is something to grow
    # *from*. Everything else the participant adds.
    INITIAL = [
        Step(
            "add",
            "Firma",
            "firma",
            {"id": "example_university", "name": "Example University"},
            "Firma **Example University** created",
        )
    ]
    get_log, set_log = mo.state(INITIAL)
    return INITIAL, get_log, set_log


@app.cell(hide_code=True)
def _(GraphWidget, mo):
    # Deliberately depends on nothing. The cell runs once per session, so the
    # view stays mounted for the whole workshop: pan and zoom survive an edit,
    # and a new node can animate in instead of the picture being rebuilt.
    # Everything downstream updates it by writing to `gview.widget.graph`.
    gview = mo.ui.anywidget(GraphWidget(height=470))
    return (gview,)


@app.cell(hide_code=True)
def _(get_log, mo):
    log = get_log()
    cursor = mo.ui.slider(
        0,
        len(log),
        value=len(log),
        full_width=True,
        label="**Step history** — drag back to replay how the model got here",
        show_value=True,
    )
    return cursor, log


@app.cell(hide_code=True)
def _(build_firma, cursor, log, replay):
    # The whole state of the application, as one fold over the log. Nothing is
    # mutated, which is why "undo" and "show me step 3" are the same operation.
    shown = log[: cursor.value]
    entities = replay(shown)
    firma = build_firma(entities)
    return entities, firma, shown


@app.cell(hide_code=True)
def _(build_graph, firma, gview, layout, shown):
    graph = build_graph(firma)
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
            the history, it can be undone, and the model — and therefore the
            JSON and the graph — is rebuilt from the log rather than patched
            in place.
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
            mo.vstack([forms.inspect_node(graph, _selected, MODELS), _panel]),
        ],
        widths=[2, 1],
        gap=1.5,
        align="start",
    )
    return edit_form, edit_submit


@app.cell(hide_code=True)
def _(STEPS, mo):
    # One step at a time, rather than five tabs. Partly because a guided flow
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

    mo.vstack([mo.md("## Add to the model"), picker])
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
    picker,
    set_log,
):
    def _build(kind: str):
        # There is only ever one company, so its tab edits the one that exists
        # instead of offering to make a second.
        single = SINGLETONS.get(kind)
        form = forms.form_for(
            FIELDS[kind],
            entity=entities.get(single) if single else None,
            option_source=lambda source: choices(entities, source),
            label_source=lambda key: label_for(entities, key),
        )

        def add(_click, kind=kind, form=form, single=single):
            props = forms.cleaned(form.value)
            name = props.get("name") or props.get("id") or kind
            step = (
                Step("update", kind, single, props, f"{kind} **{name}** edited")
                if single
                else Step(
                    "add", kind, next_key(log, kind), props,
                    f"{kind} **{name}** added",
                )
            )
            # Appending at the cursor rather than at the end: if you have
            # dragged the history slider back and then add something, you meant
            # to continue from there, the way an editor's undo stack behaves.
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
def _(INITIAL, cursor, example_log, log, mo, set_log, shown):
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
        on_click=lambda _: set_log(example_log()),
    )

    mo.vstack(
        [
            mo.md("## History"),
            mo.hstack([b_undo, b_reset, b_example], justify="start", gap=0.5),
            mo.md(
                "\n".join(
                    f"{i}. {'' if i <= len(shown) else '~~'}{step.describe()}"
                    f"{'' if i <= len(shown) else '~~'}"
                    + (" ← *you are here*" if i == len(shown) else "")
                    for i, step in enumerate(log, 1)
                )
            ),
        ]
    )
    return


@app.cell(hide_code=True)
def _(firma, mo):
    _payload = firma.model_dump_json(indent=2, exclude_none=True)

    mo.vstack(
        [
            mo.md("## The document"),
            mo.md(
                "*Generated from the same object the graph was drawn from. "
                "There is no step in between where the two could disagree.*"
            ),
            mo.ui.tabs(
                {
                    "Tree": mo.json(_payload),
                    "Raw JSON": mo.md(f"```json\n{_payload}\n```"),
                }
            ),
            mo.download(
                data=(_payload + "\n").encode(),
                filename="firma.json",
                mimetype="application/json",
                label="⬇ firma.json",
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

        Everything above works on any pydantic model. Take it to a real one:
        **[00_build_document_graph.py](00_build_document_graph.py)** builds an
        EnzymeML v2 document the same way, with the same graph, the same
        history slider and the same JSON panel — the only things that change
        are the field declarations and the twenty lines that nest them.
        """
    )
    return


if __name__ == "__main__":
    app.run()
