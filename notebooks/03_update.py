import marimo

__generated_with = "0.24.0"
app = marimo.App(width="medium", app_title="Step 3 — Write a correction back")


@app.cell(hide_code=True)
def _():
    import marimo as mo

    return (mo,)


@app.cell(hide_code=True)
def _():
    import copy
    import json

    from eln import pick, remote, remote_write
    from eln.diff import compare

    return compare, copy, json, pick, remote, remote_write


@app.cell(hide_code=True)
def _(mo):
    def task(body: str):
        return mo.callout(mo.md(body), kind="info", title="📝 Workshop task")

    def why(title: str, body: str):
        return mo.accordion({f"💡 {title}": mo.md(body)})

    def ok(line: str):
        return mo.md(f"✅ &nbsp;{line}")

    return ok, task, why


@app.cell(hide_code=True)
def _(mo, task, why):
    mo.vstack([
        mo.md(
            """
            # Step 3 — Write a correction back

            You notice the organism is wrong. Or a fit produced parameters the
            document should carry. Downloading the document, fixing it and
            importing it again would give you a **second entry** — a duplicate
            with the same title, and no way for a later reader to tell which of
            the two is the one that counts.

            This notebook updates the entry you already have: same ID, same
            links, same comments, same history. The extra fields and the
            attachment are replaced together, so the searchable summary and the
            document it summarises cannot drift apart.

            **Nothing is sent until you press the red button.** Everything
            before it is computed locally and shown to you in full.
            """
        ),
        why(
            "What this does *not* touch",
            """
            **Your text.** The generated part of the entry body sits between
            two visible markers:

            ```
            === BEGIN GENERATED SECTION - do not edit below, it is rebuilt
                from the attached document ===
            … tables, reaction, plot …
            === END GENERATED SECTION ===
            ```

            Only what is between them is rewritten. The method you typed, the
            note about the thermostat, the photo you pasted above it — all of
            that is read, kept and written back untouched. Put your own writing
            *outside* the markers and it will survive every update.

            The markers are visible rather than HTML comments because
            `Filter::body` runs HTMLPurifier, which deletes comments and allows
            no marker class through. Plain text in a paragraph is what
            survives — and since it is addressed to a human, being visible is
            arguably the point.

            **Older versions of your files.** Replacing an upload does not
            overwrite it: eLabFTW archives the previous one and adds a new one,
            because *"attached files are immutable (change history is kept)"*.
            After an update the entry therefore lists the old `enzymeml.json`
            as archived next to the current one. That is file history, not
            clutter — but this notebook makes sure exactly **one** of them is
            current, and always replaces that one rather than an archived copy.
            """,
        ),
        why(
            "Why the fields are replaced wholesale",
            """
            eLabFTW offers two ways to write extra fields. `metadatamerge`
            updates the values of fields that already exist and adds new ones.
            `metadata` replaces the lot.

            This notebook uses **replace**, because the document is the source
            and the fields are its projection. If a species disappears from the
            document — a reaction corrected, a compound removed — its field has
            to disappear from the entry too. A merge would leave it sitting
            there, looking as authoritative as the rest, describing something
            that is no longer in the record.

            The cost is that anything typed into these fields *inside* eLabFTW
            is overwritten. That is what the drift check below is for.
            """,
        ),
        task(
            """
            This notebook needs an API key with **write** permission — the
            read-only one from step 2 will be refused. Create a second key
            under *User panel → API keys*.

            On the shared demo, **only update an entry you created yourself**
            in step 1. Everyone is in the same account, so nothing stops you
            from patching somebody else's work except reading the ID twice.
            """
        ),
    ])
    return


@app.cell(hide_code=True)
def _(mo):
    f_connect = mo.md(
        """
        **Instance** {url} &nbsp;&nbsp; **API key (write)** {token}
        """
    ).batch(
        url=mo.ui.text(value="https://demo.elabftw.net", full_width=True),
        token=mo.ui.text(kind="password",
                         placeholder="a key with write permission",
                         full_width=True),
    )
    f_connect
    return (f_connect,)


@app.cell(hide_code=True)
def _(f_connect, mo, ok, remote):
    mo.stop(
        not (f_connect.value["url"].strip() and f_connect.value["token"].strip()),
        mo.callout(mo.md("**Waiting for an instance and a key.**"),
                   kind="neutral"),
    )

    session, connect_error = None, None
    try:
        session = remote.connect(f_connect.value["url"], f_connect.value["token"])
    except remote.RemoteError as exc:
        connect_error = str(exc)

    mo.stop(connect_error is not None,
            mo.callout(mo.md(f"### Could not connect\n\n> {connect_error}"),
                       kind="danger"))
    ok(f"Connected as **{session.whoami}** — `{session.url}`")
    return (session,)


@app.cell(hide_code=True)
def _(mo, task):
    f_entry = mo.md("**Experiment ID** {id} &nbsp; {load}").batch(
        id=mo.ui.number(start=1, stop=10_000_000, step=1, value=1),
        load=mo.ui.run_button(label="Load this entry"),
    )
    mo.vstack([
        mo.md(
            """
            ---
            ## 1 · The entry as it stands

            Loading reads the entry and the document attached to it. Still all
            `GET`s — this is the "before" that everything below is measured
            against.
            """
        ),
        task("The ID is in the URL of the entry, and in the table in "
             "[step 2](02_retrieve.py). Use one of your own."),
        f_entry,
    ])
    return (f_entry,)


@app.cell(hide_code=True)
def _(f_entry, mo, ok, pick, remote, session):
    mo.stop(not f_entry.value["load"],
            mo.md("*Enter an ID and press **Load this entry**.*"))

    original, source_upload, load_error = None, None, None
    try:
        original, source_upload = remote.fetch_document(
            session, int(f_entry.value["id"]))
    except remote.RemoteError as exc:
        load_error = str(exc)

    mo.stop(load_error is not None,
            mo.callout(mo.md(f"### That entry cannot be updated\n\n> "
                             + str(load_error).replace("\n", "\n> ")),
                       kind="danger"))

    schema = pick(original).SCHEMA
    ok(f"Entry **{int(f_entry.value['id'])}** carries a **{schema}** document "
       f"in `{source_upload['name']}` — "
       f"{len([k for k, v in original.items() if v])} populated top-level fields.")
    return original, schema


@app.cell(hide_code=True)
def _(mo, schema, task, why):
    f_mode = mo.ui.radio(
        options={
            "Correct it here": "here",
            "Upload a corrected document": "upload",
        },
        value="Correct it here", inline=True,
    )

    mo.vstack([
        mo.md(
            """
            ---
            ## 2 · The correction

            Two ways in, because the two scenarios differ in where the work
            happens. A **wrong organism** is a typo you fix in a form. A
            **fitted model** comes from an analysis that ran somewhere else and
            handed you a whole document back.
            """
        ),
        why(
            "Which to use",
            """
            *Correct it here* edits the species and the provenance in place.
            It is the short path for the mistakes people actually make: an
            organism copied from the wrong tab, an EC number off by a digit, a
            title without initials.

            *Upload a corrected document* takes a complete document and uses
            it as-is. That is the path for anything a form cannot express —
            a kinetic model fitted elsewhere, measurements reprocessed, units
            recomputed. Whatever produced it, this notebook only has to write
            it back.

            Either way the result is a document, and the same code turns it
            into extra fields as step 1 did. There is no second mapping to
            keep in sync.
            """,
        ),
        f_mode if schema == "enzymeml" else mo.callout(
            mo.md(f"The in-notebook form only knows EnzymeML species, and "
                  f"this is a **{schema}** document. Upload a corrected one "
                  "instead."), kind="warn"),
        task(
            """
            Scenario 1: change the **organism** of the protein to something
            visibly wrong — `Escherichia coli`, say — and watch what the plan
            below says it would do. Then set it back to the right value before
            sending anything.
            """
        ),
    ])
    return (f_mode,)


@app.cell(hide_code=True)
def _(mo, original, schema):
    _species = ([{"id": p.get("id"), "name": p.get("name") or "",
                  "kind": "protein",
                  "organism": p.get("organism") or "",
                  "organism_tax_id": p.get("organism_tax_id") or "",
                  "ecnumber": p.get("ecnumber") or "",
                  "inchikey": ""}
                 for p in original.get("proteins") or []]
                + [{"id": s.get("id"), "name": s.get("name") or "",
                    "kind": "small molecule", "organism": "",
                    "organism_tax_id": "", "ecnumber": "",
                    "inchikey": s.get("inchikey") or ""}
                   for s in original.get("small_molecules") or []])

    t_species = mo.ui.data_editor(
        _species or [{"id": "", "name": "", "kind": "", "organism": "",
                      "organism_tax_id": "", "ecnumber": "", "inchikey": ""}],
        label="**Species** — `id` and `kind` are read-only; they say which "
              "entry in the document each row belongs to",
        editable_columns=["name", "organism", "organism_tax_id", "ecnumber",
                          "inchikey"],
    )

    f_meta = mo.md(
        """
        **Title** {name}

        **Description** {description}
        """
    ).batch(
        name=mo.ui.text(value=original.get("name") or "", full_width=True),
        description=mo.ui.text_area(value=original.get("description") or "",
                                    full_width=True, rows=2),
    )

    f_upload = mo.ui.file(filetypes=[".json"], multiple=False, kind="area",
                          label="A corrected document to use as-is")

    mo.vstack([t_species, f_meta]) if schema == "enzymeml" else mo.md("")
    return f_meta, f_upload, t_species


@app.cell(hide_code=True)
def _(f_mode, f_upload, mo, schema):
    mo.vstack([f_upload]) if (schema != "enzymeml"
                              or f_mode.value == "upload") else mo.md("")
    return


@app.cell(hide_code=True)
def _(copy, f_meta, f_mode, f_upload, json, mo, original, schema, t_species):
    # The edited document, built fresh from the forms every run. `original` is
    # deep-copied rather than mutated: it is the "before" the plan and the
    # drift check are both measured against, and it has to stay that.
    edited, edit_error = None, None

    if schema != "enzymeml" or f_mode.value == "upload":
        if f_upload.value:
            try:
                edited = json.loads(f_upload.value[0].contents)
            except ValueError as _exc:
                edit_error = f"That file is not valid JSON — {_exc}"
        else:
            edit_error = "waiting"
    else:
        edited = copy.deepcopy(original)
        _rows = {str(r.get("id")): r for r in t_species.value if r.get("id")}

        def _set(entity, row, keys):
            for key in keys:
                value = str(row.get(key) or "").strip()
                if value:
                    entity[key] = value
                else:
                    entity.pop(key, None)

        for _p in edited.get("proteins") or []:
            _row = _rows.get(str(_p.get("id")))
            if _row:
                _set(_p, _row, ("name", "organism", "organism_tax_id", "ecnumber"))
        for _s in edited.get("small_molecules") or []:
            _row = _rows.get(str(_s.get("id")))
            if _row:
                _set(_s, _row, ("name", "inchikey"))

        _name = f_meta.value["name"].strip()
        _description = f_meta.value["description"].strip()
        edited["name"] = _name or original.get("name")
        if _description:
            edited["description"] = _description
        else:
            edited.pop("description", None)

    mo.stop(
        edited is None,
        mo.callout(
            mo.md("**Waiting for a corrected document.** Drop one on the box "
                  "above.") if edit_error == "waiting" else
            mo.md(f"### That file cannot be used\n\n> {edit_error}"),
            kind="neutral" if edit_error == "waiting" else "danger"),
    )
    return (edited,)


@app.cell(hide_code=True)
def _(compare, edited, mo, ok, original, why):
    _deltas = list(compare(original, edited))

    mo.vstack([x for x in (
        mo.md("### What you changed in the document"),
        mo.callout(
            mo.md(f"**{len(_deltas)} change(s)** to the document itself:"
                  + "".join(f"\n- `{d.path}` — {d.kind}" for d in _deltas[:20])
                  + (f"\n- … and {len(_deltas) - 20} more"
                     if len(_deltas) > 20 else "")),
            kind="info") if _deltas else ok(
            "The document is unchanged — nothing would be written."),
        why("Document changes are not the same as entry changes",
            "A change here is a change to the *record*. Whether it also "
            "changes the **entry** depends on whether that part of the "
            "document reaches an extra field, the body or the attachment — "
            "which the plan below answers exactly. Editing a field nobody "
            "projects still changes the attachment, because the attachment "
            "is the document.") if _deltas else None,
    ) if x])
    return


@app.cell(hide_code=True)
def _(edited, f_entry, mo, original, remote, remote_write, session):
    plan, plan_error = None, None
    try:
        plan = remote_write.prepare(session, int(f_entry.value["id"]), edited,
                                    original=original)
    except remote.RemoteError as exc:
        plan_error = str(exc)

    mo.stop(plan_error is not None,
            mo.callout(mo.md(f"### No plan could be made\n\n> "
                             + str(plan_error).replace("\n", "\n> ")),
                       kind="danger"))

    mo.md(
        f"""
        ---
        ## 3 · The plan

        **{plan.summary()}**. Nothing has been sent — this was all computed
        from the entry as it is now and the document as you have it.
        """
    )
    return (plan,)


@app.cell(hide_code=True)
def _(mo, plan, remote_write, why):
    # Built by appending rather than filtered with `if x`: a mo.ui.table is a
    # UIElement, and asking a UIElement whether it is truthy gets a warning
    # rather than an answer.
    _panels = []
    if plan.drift:
        _panels.append(mo.callout(
            mo.md("### Somebody edited this entry inside eLabFTW\n\n"
                  "These values are on the instance but are **not** what the "
                  "document produces, so sending would overwrite them:\n\n"
                  + "\n".join(f"- {d}" for d in plan.drift)
                  + "\n\nIf that is your own typing, put it into the document "
                  "instead — a value that only exists in the entry is a value "
                  "the next export loses."),
            kind="danger", title="Drift"))
    if not plan.fenced:
        _panels.append(mo.callout(
            mo.md("### This entry has no generated section to replace\n\n"
                  "Its body carries no `=== BEGIN GENERATED SECTION ===` "
                  "marker, which means it was written by hand or imported "
                  "before this converter started fencing its output.\n\n"
                  "The generated block will therefore be **appended** rather "
                  "than replacing anything — nothing you wrote is at risk, but "
                  "if an older generated block is already in there you will "
                  "want to delete it once, by hand. From then on the fence is "
                  "in place and updates replace only what is inside it."),
            kind="warn", title="No fence"))
    _panels.append(mo.md("**Requests that would be made:**"))
    _panels.append(mo.md(f"```\n{remote_write.describe(plan)}\n```"))
    _panels.append(
        mo.ui.table([{"What": c.where, "Now": str(c.before),
                      "Would become": str(c.after)} for c in plan.changes],
                    selection=None, page_size=20)
        if plan.changes else mo.md("*No differences.*"))
    _panels.append(why(
        "Why so few files are re-uploaded",
        "Every attachment is regenerated, but only the ones whose sha256 "
        "differs from what the instance reports are sent. Correcting an "
        "organism changes the document and therefore `enzymeml.json`, while "
        "the plot and the CSVs come out byte-identical and are left alone. "
        "The instance's own hash answers the question, so nothing has to be "
        "downloaded to find out."))
    mo.vstack(_panels)
    return


@app.cell(hide_code=True)
def _(mo, plan, task):
    f_send = mo.ui.run_button(
        label=f"⚠ Send — {plan.summary()}",
        kind="danger", disabled=plan.empty,
        tooltip="Nothing to send" if plan.empty else None,
    )

    mo.vstack([
        mo.md(
            """
            ---
            ## 4 · Send it

            This is the only cell in three notebooks that changes something
            that is not on your own machine.
            """
        ),
        task("Read the table above once more, then press it. On the shared "
             "demo, be sure the ID is yours."),
        f_send,
    ])
    return (f_send,)


@app.cell(hide_code=True)
def _(f_send, mo, plan, remote, remote_write, session):
    # Two guards, not one. The button resets itself to False after the cells
    # that read it have run, so an unrelated re-run cannot fire it again — and
    # if that ever stopped holding, an empty plan still sends nothing.
    mo.stop(not f_send.value, mo.md("*Nothing sent yet.*"))
    mo.stop(plan.empty, mo.md("*Nothing to send.*"))

    sent, send_error = [], None
    try:
        sent = remote_write.apply(session, plan)
    except remote.RemoteError as exc:
        send_error = str(exc)

    mo.callout(
        mo.md(f"### The update was refused\n\n> {send_error}\n\n"
              "A read-only API key is the usual cause — this notebook needs "
              "one with write permission."),
        kind="danger") if send_error else mo.callout(
        mo.md("### Sent\n\n"
              + "\n".join(f"- `{line}`" for line in sent)
              + "\n\nThe previous version of every replaced file is archived "
                "on the entry rather than deleted, and the changelog records "
                "the patch. Nothing about this is irreversible."),
        kind="success")
    return (sent,)


@app.cell(hide_code=True)
def _(compare, edited, f_entry, mo, remote, sent, session):
    mo.stop(not sent)

    _fresh, _upload = remote.fetch_document(session, int(f_entry.value["id"]))
    _deltas = list(compare(edited, _fresh))

    mo.callout(
        mo.md("### Read back from the instance: **identical**\n\n"
              "The document was fetched again just now, from the attachment "
              "the update wrote, and matches what you sent. The loop is "
              "closed: document → entry → document."),
        kind="success") if not _deltas else mo.callout(
        mo.md("### Read back from the instance: **differs**\n\n"
              + "\n".join(f"- `{d}`" for d in _deltas[:20])),
        kind="danger")
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ---
    ### That is the loop

    | Step | Direction |
    |---|---|
    | [0](00_build_document.py) | measurements → document |
    | [1](01_export_eln.py) | document → `.eln` → lab notebook |
    | [2](02_retrieve.py) | lab notebook → document |
    | 3 | document → the *same* lab notebook entry |

    Nothing here is maintained twice. The extra fields are never typed —
    they are derived, every time, from the document that is also attached
    in full. That is the whole claim: metadata and data stay together
    because there is only ever one copy of them, and everything else is a
    view.
    """)
    return


if __name__ == "__main__":
    app.run()
