import marimo

__generated_with = "0.24.0"
app = marimo.App(width="medium", app_title="Step 1 — Export an .eln")


@app.cell(hide_code=True)
def _():
    import marimo as mo

    return (mo,)


@app.cell(hide_code=True)
def _():
    import base64
    import copy
    import datetime as dt
    import json

    from eln import convert_document, pick, read_eln
    from eln.crate import GROUPS, eln_bytes, inline_image
    from eln.diff import compare, report, summarise

    return (
        GROUPS,
        base64,
        compare,
        convert_document,
        copy,
        dt,
        eln_bytes,
        inline_image,
        json,
        pick,
        read_eln,
        report,
        summarise,
    )


@app.cell(hide_code=True)
def _(mo):
    def ok(line: str):
        """A one-line confirmation, in the same shape as in step 0."""
        return mo.md(f"✅ &nbsp;{line}")

    def why(title: str, body: str):
        """Background reading, folded away."""
        return mo.accordion({f"💡 {title}": mo.md(body)})

    def key_of(path: str) -> str:
        """A form key for a dotted path.

        `mo.md(...).batch()` substitutes through `str.format`, which reads
        `{citation.title}` as *attribute `title` of key `citation`*. Flatten
        the dot away and the placeholder is a plain name again.
        """
        return path.replace(".", "__")

    def get(doc: dict, path: str):
        """Read a dotted path, tolerating missing intermediate objects."""
        node = doc
        for part in path.split("."):
            if not isinstance(node, dict):
                return None
            node = node.get(part)
        return node

    def put(doc: dict, path: str, value) -> None:
        """Write a dotted path, creating intermediate objects as needed.

        A value that is empty *deletes* the key rather than writing ``""``:
        in both schemas an absent field and an empty one mean the same thing,
        and the diff treats them the same, so writing the empty string would
        only add noise to the document.
        """
        parts = path.split(".")
        node = doc
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        if value in (None, "", []):
            node.pop(parts[-1], None)
        else:
            node[parts[-1]] = value

    return get, key_of, ok, put, why


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    # Step 1 — From a structured document to a lab notebook entry

    Drop in an EnzymeML or FAIRFluids document and get an `.eln` package
    that eLabFTW imports as an experiment with native, searchable *extra
    fields*.

    This notebook does not care where the document came from —
    [step 0](00_build_document.py) builds one with PyEnzyme, but a file
    from a colleague or from an instrument pipeline works just as well.
    That indifference is the point: the adapter sits behind a format, not
    behind a tool.

    **Nothing below this line exists until you upload a file.** The
    notebook has no example of its own on purpose — every number, table
    and preview you will see is derived from *your* document.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    upload = mo.ui.file(filetypes=[".json"], multiple=False, kind="area",
                        label="EnzymeML v2 or FAIRFluids JSON")
    upload
    return (upload,)


@app.cell(hide_code=True)
def _(json, mo, pick, upload):
    mo.stop(
        not upload.value,
        mo.callout(
            mo.md(
                "**Waiting for a document.**\n\n"
                "Drop a JSON file above. If you have just come from step 0, "
                "that is the `kinetics.json` you downloaded there. Any "
                "EnzymeML v2 or FAIRFluids document works."
            ),
            kind="neutral"),
    )

    _file = upload.value[0]
    source, _raw = _file.name, _file.contents

    # Reading and detection happen together so that *every* way a file can be
    # unusable ends in the same explained callout rather than a traceback in a
    # room of thirty people. Three failures are expected here, and only the
    # first is obvious: the file is not JSON; it is JSON of a schema we do not
    # handle; or it is a schema we do handle in a version we do not — an
    # EnzymeML v1 document passes detection and only fails inside convert().
    uploaded, schema, problem = None, None, None
    try:
        uploaded = json.loads(_raw)
        if not isinstance(uploaded, dict):
            raise ValueError("the file is valid JSON, but not a JSON object")
        module = pick(uploaded)
        # Not every converter has a version guard; EnzymeML does, because a v1
        # document passes detection and would only fail much later.
        if hasattr(module, "validate"):
            module.validate(uploaded)
        schema = module.SCHEMA
    except json.JSONDecodeError as exc:
        problem = f"`{source}` is not valid JSON — {exc}"
    except ValueError as exc:
        problem = str(exc)

    mo.stop(
        problem is not None,
        mo.callout(
            mo.md("### That file cannot be converted\n\n"
                  + "\n".join(f"> {line}" for line in str(problem).splitlines())
                  + "\n\nUpload a different one."),
            kind="danger"),
    )
    return schema, source, uploaded


@app.cell(hide_code=True)
def _(mo, ok, schema, source, uploaded):
    mo.vstack([
        ok(f"**{source}** — recognised as **{schema}**, "
           f"{len([k for k, v in uploaded.items() if v])} populated top-level "
           f"fields: {', '.join(k for k, v in uploaded.items() if v)}"),
        mo.accordion({"🔍 The document as uploaded": mo.tree(uploaded)}),
    ])
    return


@app.cell(hide_code=True)
def _():
    # Which top-level fields are provenance — the part of a document that
    # describes the work rather than the measurement, and the part a machine
    # can never fill in. Dotted paths, so the two schemas can put them at
    # different depths without the form knowing.
    #
    # Schema versions are deliberately absent: `version` says which grammar
    # the file follows, and letting somebody type `3.0` into it would produce
    # a document that lies about itself.
    PROVENANCE = {
        "enzymeml": {
            "fields": [
                ("name", "Title", "text"),
                ("description", "Description — what was done, and how", "area"),
                ("created", "Created (ISO 8601)", "text"),
                ("references", "References — DOI or URL, one per line", "lines"),
            ],
            "people": ("creators", "Creators",
                       ["given_name", "family_name", "mail"]),
            "stamp": "modified",
        },
        "fairfluids": {
            "fields": [
                ("citation.title", "Publication title", "text"),
                ("citation.doi", "DOI", "text"),
                ("citation.pub_name", "Journal", "text"),
                ("citation.publication_year", "Year", "text"),
                ("citation.lit_volume_num", "Volume", "text"),
                ("citation.page", "Pages", "text"),
                ("citation.url_citation", "URL", "text"),
                ("citation.litType", "Literature type", "text"),
            ],
            "people": ("citation.author", "Authors",
                       ["given_name", "family_name", "email", "orcid",
                        "affiliation"]),
            "stamp": None,
        },
    }
    return (PROVENANCE,)


@app.cell(hide_code=True)
def _(mo, why):
    mo.vstack([
        mo.md(
            """
            ---
            ## The provenance, before it is frozen

            The fields below are filled in from your document and stay
            editable. Whatever you change here is what gets exported — the
            uploaded file is never written to.
            """
        ),
        why(
            "Why edit here rather than in the JSON",
            """
            These are the fields that describe *the work*: what it is called,
            what was done, who did it, what to cite. No instrument produces
            them and no converter can infer them, so they are exactly the
            fields that tend to be missing — and the export is the last
            moment before they are frozen into a lab notebook entry that
            somebody else will search.

            Everything else in the document — species, measurements, units,
            the numbers — is passed through untouched. This is a metadata
            form, not an editor.
            """,
        ),
    ])
    return


@app.cell(hide_code=True)
def _(PROVENANCE, get, key_of, mo, schema, uploaded):
    _spec = PROVENANCE[schema]

    def _widget(kind, value):
        if kind == "area":
            return mo.ui.text_area(value=value or "", full_width=True, rows=3)
        if kind == "lines":
            return mo.ui.text_area(
                value="\n".join(str(v) for v in (value or [])),
                full_width=True, rows=3)
        return mo.ui.text(value="" if value is None else str(value),
                          full_width=True)

    f_provenance = mo.md(
        "\n\n".join(f"**{label}** {{{key_of(path)}}}"
                    for path, label, _ in _spec["fields"])
    ).batch(**{key_of(path): _widget(kind, get(uploaded, path))
               for path, _, kind in _spec["fields"]})

    _people_path, _people_label, _people_columns = _spec["people"]
    _people = get(uploaded, _people_path) or []
    t_people = mo.ui.data_editor(
        [{c: (p.get(c) or "") for c in _people_columns} for p in _people] or
        [{c: "" for c in _people_columns}],
        label=f"**{_people_label}** — one row per person; add or remove rows "
              "as needed",
    )

    mo.vstack([f_provenance, t_people])
    return f_provenance, t_people


@app.cell(hide_code=True)
def _(PROVENANCE, mo, schema, uploaded):
    _stamp = PROVENANCE[schema]["stamp"]

    f_stamp = mo.ui.checkbox(
        value=True,
        label=f"Set `{_stamp}` to now if anything above changed "
              f"(currently `{uploaded.get(_stamp) or '—'}`)",
    ) if _stamp else mo.ui.checkbox(value=False, label="")

    mo.vstack([
        f_stamp,
        mo.md(f"*The point of a `{_stamp}` field is to be wrong the moment "
              "somebody edits around it. Since this notebook is the thing "
              "doing the editing, it can keep the field honest — but only if "
              "you let it.*"),
    ]) if _stamp else mo.md(
        f"*The {schema} schema has no modification timestamp, so there is "
        "nothing to stamp.*")
    return (f_stamp,)


@app.cell(hide_code=True)
def _(
    PROVENANCE,
    compare,
    copy,
    dt,
    f_provenance,
    f_stamp,
    get,
    key_of,
    put,
    schema,
    t_people,
    uploaded,
):
    # A deep copy: the uploaded document is evidence and stays as it arrived,
    # so the diff below has something truthful to compare against.
    document = copy.deepcopy(uploaded)
    _spec = PROVENANCE[schema]

    for _path, _, _kind in _spec["fields"]:
        _value = f_provenance.value[key_of(_path)]
        if _kind == "lines":
            _value = [line.strip() for line in _value.splitlines() if line.strip()]
        else:
            _value = _value.strip()
        put(document, _path, _value)

    _people_path, _, _columns = _spec["people"]
    _original = get(uploaded, _people_path) or []
    _rows = [{c: str(row.get(c) or "").strip() for c in _columns}
             for row in t_people.value]
    _rows = [r for r in _rows if any(r.values())]
    # Merged onto the original entries by position rather than replacing them:
    # a person in these schemas also carries ld_id and friends, and rebuilding
    # the row from five visible columns would quietly drop the identity the
    # file arrived with. A cleared cell removes its key, so emptying a field
    # means the same thing here as it does in the form above.
    def _merge(original: dict, row: dict) -> dict:
        merged = dict(original)
        for column, value in row.items():
            if value:
                merged[column] = value
            else:
                merged.pop(column, None)
        return merged

    put(document, _people_path,
        [_merge(_original[i] if i < len(_original) else {}, row)
         for i, row in enumerate(_rows)])

    edits = [d for d in compare(uploaded, document)]
    _stamp = _spec["stamp"]
    if _stamp and f_stamp.value and edits:
        document[_stamp] = dt.datetime.now(dt.timezone.utc).replace(
            microsecond=0).isoformat().replace("+00:00", "Z")
    return document, edits


@app.cell(hide_code=True)
def _(document, edits, mo, ok, schema):
    mo.callout(
        mo.md(
            f"**{len(edits)} change(s)** — this edited document is what gets "
            "exported below, and what the round-trip is checked against:"
            + "".join(f"\n- `{d.path}`: {d.kind}" for d in edits)
            + (f"\n\nThe `modified` timestamp now reads "
               f"`{document.get('modified')}`."
               if schema == "enzymeml" and document.get("modified") else "")
        ),
        kind="info", title="Edited") if edits else ok(
        "Nothing changed — the document is exported exactly as it arrived.")
    return


@app.cell(hide_code=True)
def _(mo, why):
    f_links = mo.ui.checkbox(
        value=False,
        label="Also emit every species as its own **resource item**, linked "
              "from the entry",
    )

    mo.vstack([
        mo.md("---\n## What eLabFTW will receive"),
        f_links,
        why(
            "What a resource item is, and why this is off by default",
            """
            eLabFTW keeps two kinds of record: *experiments*, which happen
            once, and *resources* — its database of things that persist
            across experiments: compounds, enzymes, equipment, cell lines.
            With this switch on, every species in your document additionally
            becomes a resource item, and the experiment links to it.

            The species are in the export either way: as extra fields, in
            the entry body, and in full inside the attached JSON. Nothing is
            lost by leaving this off — the switch only decides whether they
            *also* get their own database entries.

            It is off by default because those entries are shared, permanent
            and awkward to remove, so fifteen participants importing at once
            would leave fifteen copies of ethanol in a database nobody
            volunteered to curate. On your own instance, where a compound
            really is worth having once and referring to many times, turn it
            on. On the shared demo, prefer to look rather than leave traces.

            This is the `--links` flag of `python -m eln`.
            """,
        ),
    ])
    return (f_links,)


@app.cell(hide_code=True)
def _(convert_document, document, f_links, mo):
    # The same call the CLI makes, so schema detection, grain default and
    # publisher metadata cannot drift between `python -m eln` and here.
    crate, entries, resources, conversion_error = None, [], [], None
    try:
        crate, entries, resources = convert_document(
            document, links=f_links.value, plots=True, csv=True)
    except Exception as exc:
        conversion_error = f"{type(exc).__name__}: {exc}"

    mo.stop(
        conversion_error is not None,
        mo.callout(
            mo.md("### The document passed detection but not conversion\n\n"
                  f"> `{conversion_error}`\n\n"
                  "If you edited the fields above, undo the last change; "
                  "otherwise the document is structurally different from what "
                  "the converter expects."),
            kind="danger"),
    )
    return crate, entries, resources


@app.cell(hide_code=True)
def _(entries, mo, resources):
    mo.hstack([
        mo.stat(value=len(entries), label="lab notebook entries",
                caption="one per experiment", bordered=True),
        mo.stat(value=sum(len(e.fields) for e in entries), label="extra fields",
                caption="grouped and typed", bordered=True),
        mo.stat(value=len(resources), label="resource items",
                caption="linked inventory — the switch above", bordered=True),
        mo.stat(value=sum(len(e.attachments) for e in entries),
                label="attachments", caption="payload, tables, plot",
                bordered=True),
    ], widths="equal")
    return


@app.cell(hide_code=True)
def _(GROUPS, entries, mo):
    _names = {g["id"]: g["name"] for g in GROUPS}

    # Keyed by entry id, not by name: FAIRFluids happily produces six fluids
    # under four distinct names, and a dict keyed on the name would drop two
    # tabs without saying so. The name goes inside the tab instead.
    mo.ui.tabs({
        e.id: mo.vstack([
            mo.md(f"**{e.name}** — this is exactly how eLabFTW will show "
                  "these: grouped, typed and searchable."),
            mo.ui.table(
                [{"Group": _names.get(f["group_id"], "?"), "Field": f["name"],
                  "Value": f["value"], "Unit": f.get("unit", "")}
                 for f in e.fields],
                selection=None, page_size=15),
        ])
        for e in entries
    }) if entries else mo.md("*no entries*")
    return


@app.cell(hide_code=True)
def _(base64, entries, inline_image, mo, why):
    _e = entries[0]
    _png = next((a.data for a in _e.attachments if a.name == "plot.png"), None)

    # The body points its <img> at `app/download.php?f=…`, which only resolves
    # once eLabFTW has rewritten it to the real upload on import. For the
    # preview here, swap that reference for the image itself — so this panel
    # shows what the entry will look like *after* the import.
    _body = _e.html
    if _png:
        _ref = inline_image(_e.id, "plot.png").split('src="')[1].split('"')[0]
        _body = _body.replace(
            _ref, "data:image/png;base64," + base64.b64encode(_png).decode("ascii"))

    mo.vstack([
        mo.md(f"### The entry body of *{_e.name}*\n\n"
              "What eLabFTW shows when the entry is opened. The plot is not "
              "previewed separately — it is in the body, which is where it "
              "will be."
              + ("" if _png else "\n\n*No plot: matplotlib is not installed, "
                                 "so the body has none either.*")),
        why(
            "About the BEGIN/END GENERATED SECTION markers",
            """
            Everything between them is derived from the document and will be
            **rebuilt** if the entry is ever updated from a corrected document
            in [step 3](03_update.py). Everything outside them is yours and is
            left alone.

            So once the entry is in eLabFTW, write your method, your notes and
            your own images *above or below* the markers, never between them.
            That is the whole contract, and it is stated in the entry itself
            rather than in a manual nobody has open at the time.
            """,
        ),
        mo.Html(_body),
    ])
    return


@app.cell(hide_code=True)
def _(crate, document, eln_bytes, json, mo, source):
    _stem = source.removesuffix(".json") or "document"
    package = eln_bytes(crate, root_name=_stem)
    _edited = (json.dumps(document, indent=2, ensure_ascii=False) + "\n").encode()

    mo.vstack([
        mo.md(
            f"""
            ---
            ## Take it with you

            The `.eln` is a ZIP with one root folder, `ro-crate-metadata.json`
            inside it, and the payload next to it — RO-Crate 1.2 in its `.eln`
            shape. The JSON next to it is your document *with the edits you
            just made*, so the corrected provenance does not only live inside
            the lab notebook package.
            """
        ),
        mo.hstack([
            mo.download(data=package, filename=f"{_stem}.eln",
                        mimetype="application/zip",
                        label=f"⬇ {_stem}.eln ({len(package) // 1024} KB)"),
            mo.download(data=_edited, filename=f"{_stem}.edited.json",
                        mimetype="application/json",
                        label=f"⬇ {_stem}.edited.json "
                              f"({max(1, len(_edited) // 1024)} KB)"),
        ], justify="start", gap=1),
    ])
    return (package,)


@app.cell(hide_code=True)
def _(compare, document, mo, package, pick, read_eln, report, summarise, why):
    _module = pick(document)
    _crate = read_eln(package)
    _restored = _module.reassemble(
        [p for p in (e.payload() for e in _crate.entries) if p])

    # Losses the schema module declares as structurally unavoidable are named
    # rather than counted — the same rule roundtrip_eln.py applies — so that a
    # *new* loss still turns this callout red instead of hiding in a crowd.
    _declared = set(getattr(_module, "EXPECTED_LOSS", ()))
    _deltas = [d for d in compare(document, _restored) if d.path not in _declared]
    _text, _ok = report(_deltas)

    # `report` leads with the individual deltas, which makes a poor headline.
    # The verdict is what belongs in bold; the deltas belong in the fold.
    _counts = ", ".join(f"{n} {kind}" for kind, n in summarise(_deltas).items() if n)
    _verdict = ("identical" if not _deltas
                else f"no information lost ({_counts})" if _ok
                else _counts)

    mo.vstack([x for x in (
        mo.callout(
            mo.md(
                f"### Round trip: **{_verdict}**\n\n"
                "The `.eln` was just read back and compared against the edited "
                "document — **without** the safety copy at the crate root, so "
                "from the entries alone. Your data comes back out of the lab "
                "notebook, not just in."
                + (f"\n\n{len(_declared)} path(s) are declared in "
                   f"`{_module.SCHEMA}.EXPECTED_LOSS` as unreachable by this "
                   "route and are not counted: "
                   + ", ".join(f"`{p}`" for p in sorted(_declared))
                   + ". They travel in the copy at the crate root instead."
                   if _declared else "")
            ),
            kind="success" if _ok else "danger",
        ),
        why("What the differences are", f"```\n{_text}\n```") if _deltas else None,
    ) if x])
    return


@app.cell(hide_code=True)
def _(mo, source):
    mo.md(f"""
    ---
    ### On to eLabFTW

    1. Download `{source.removesuffix('.json')}.eln`.
    2. Upload it at <https://demo.elabftw.net> under *Import*.
    3. Open the entry and expand the **Extra fields** — the same groups
       as in the table above, now searchable. The plot appears in the
       entry body and among the attachments.

    Remember: the demo shares one account with everyone and is reset
    daily. What you keep is the file on your own machine — which is why
    both downloads above are worth taking.
    """)
    return


if __name__ == "__main__":
    app.run()
