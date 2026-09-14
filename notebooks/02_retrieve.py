import marimo

__generated_with = "0.24.0"
app = marimo.App(width="medium", app_title="Step 2 — Retrieve from eLabFTW")


@app.cell(hide_code=True)
def _():
    import marimo as mo

    return (mo,)


@app.cell(hide_code=True)
def _():
    import io
    import json
    import zipfile

    from eln import pick, remote
    from eln.diff import compare, summarise

    return compare, io, json, pick, remote, summarise, zipfile


@app.cell(hide_code=True)
def _(mo):
    def task(body: str):
        """A workshop instruction, in the same blue box as in steps 0 and 1."""
        return mo.callout(mo.md(body), kind="info", title="📝 Workshop task")

    def why(title: str, body: str):
        """Background reading, folded away."""
        return mo.accordion({f"💡 {title}": mo.md(body)})

    def ok(line: str):
        return mo.md(f"✅ &nbsp;{line}")

    return ok, task, why


@app.cell(hide_code=True)
def _(mo, task):
    mo.vstack(
        [
            mo.md(
                """
            # Step 2 — Get the documents back out

            Steps 0 and 1 went one way: a document became a lab notebook entry.
            This one goes the other way. It connects to a running eLabFTW,
            searches it, and turns entries back into the EnzymeML or FAIRFluids
            documents they were made from.

            That return trip is the whole claim of the exercise. A lab notebook
            you can only write into is an archive; one you can read out of is a
            **source**. Everything here is a `GET` — nothing on the instance
            changes. Correcting and re-uploading is
            [step 3](03_update.py), which asks before it sends.

            **Nothing below exists until you connect.**
            """
            ),
            task(
                """
            On <https://demo.elabftw.net>, go to **User panel → API keys** and
            create one. **Read-only permission is enough** for this notebook —
            pick it, and nothing you do here can damage anything.
            
            
            The key goes in the password field below and is never written to
            disk by this notebook. The demo is reset every 24 h, key included.
            """
            ),
        ]
    )
    return


@app.cell(hide_code=True)
def _(mo):
    f_connect = mo.md(
        """
        **Instance** {url} &nbsp;&nbsp; **API key** {token}
        """
    ).batch(
        url=mo.ui.text(
            value="https://demo.elabftw.net", placeholder="https://…", full_width=True
        ),
        token=mo.ui.text(
            kind="password", placeholder="from User panel → API keys", full_width=True
        ),
    )
    f_connect
    return (f_connect,)


@app.cell(hide_code=True)
def _(f_connect, mo, ok, remote):
    mo.stop(
        not (f_connect.value["url"].strip() and f_connect.value["token"].strip()),
        mo.callout(
            mo.md("**Waiting for an instance and a key.** Both fields above "
                  "have to be filled in before anything is fetched."),
            kind="neutral"),
    )

    session, connect_error = None, None
    try:
        session = remote.connect(f_connect.value["url"],
                                 f_connect.value["token"])
    except remote.RemoteError as exc:
        connect_error = str(exc)

    mo.stop(
        connect_error is not None,
        mo.callout(mo.md(f"### Could not connect\n\n> {connect_error}"),
                   kind="danger"),
    )
    ok(f"Connected as **{session.whoami}** — `{session.url}`. "
       "Every call from here on is a read.")
    return (session,)


@app.cell(hide_code=True)
def _(mo, remote, task, why):
    mo.vstack([
        mo.md(
            """
            ---
            ## Find the entries

            `q` searches title, body and elabid. `extended` is eLabFTW's
            advanced query language, and it is the more interesting of the two:
            it reaches the **extra fields** — the ones step 1 wrote.
            """
        ),
        why(
            "The query language",
            "Search terms this instance understands, from eLabFTW's own "
            "grammar (`src/node/grammar/queryGrammar.pegjs`):\n\n"
            + "\n".join(f"- `{q}` — {what}" for q, what in remote.QUERY_EXAMPLES)
            + "\n\nThey combine with `and`, `or` and `not`. This is where the "
            "work from step 1 pays off: `extrafield:\"Organism\":…` only finds "
            "anything because the organism was written as a *field* rather "
            "than buried in the prose of an entry body."
        ),
        task(
            """
            Leave both boxes empty first and just look at what the demo
            contains. Then try `extrafield:"Group ID":dilution_series_1` to
            find the series somebody exported in step 1 — including, if the
            timing works out, your own.
            """
        ),
    ])
    return


@app.cell(hide_code=True)
def _(mo):
    f_search = mo.md(
        """
        **q** {q} &nbsp;&nbsp; **extended** {extended} &nbsp;&nbsp;
        **limit** {limit}
        """
    ).batch(
        q=mo.ui.text(placeholder="a word in title or body"),
        extended=mo.ui.text(placeholder="date:2026-09-01..2026-09-30", full_width=True),
        limit=mo.ui.number(start=1, stop=200, step=1, value=25),
    )
    f_search
    return (f_search,)


@app.cell(hide_code=True)
def _(mo, remote, session):
    # What this instance actually names its fields — better than guessing at
    # somebody else's vocabulary. Failure here is not worth stopping for.
    try:
        _keys = remote.extra_field_keys(session, limit=25)
    except remote.RemoteError:
        _keys = []

    (
        mo.accordion(
            {
                f"💡 Extra-field names in use on this instance ({len(_keys)})": mo.ui.table(
                    [{"Field": k["key"], "Entries": k["count"]} for k in _keys],
                    selection=None,
                )
            }
        )
        if _keys
        else mo.md("")
    )
    return


@app.cell(hide_code=True)
def _(f_search, mo, remote, session):
    results, search_error = [], None
    try:
        results = remote.search(
            session,
            q=f_search.value["q"],
            extended=f_search.value["extended"],
            limit=int(f_search.value["limit"]),
        )
    except remote.RemoteError as exc:
        search_error = str(exc)

    mo.stop(
        search_error is not None,
        mo.callout(
            mo.md(
                f"### The search was refused\n\n> {search_error}\n\n"
                "An invalid `extended` query is the usual cause — eLabFTW "
                "rejects the whole query rather than ignoring the bad part."
            ),
            kind="danger",
        ),
    )

    t_results = mo.ui.table(
        results,
        selection="multi",
        page_size=15,
        label="**Select the entries to fetch**",
    )
    mo.vstack(
        [
            mo.md(
                f"**{len(results)} entr{'y' if len(results) == 1 else 'ies'}**"
                + (" — nothing matched; widen the query." if not results else "")
            ),
            t_results,
        ]
    )
    return (t_results,)


@app.cell(hide_code=True)
def _(mo, t_results, task):
    f_fetch = mo.ui.run_button(
        label=f"⬇ Fetch {len(t_results.value)} selected document(s)",
        disabled=not t_results.value,
        kind="success",
    )

    mo.vstack(
        [
            mo.md(
                """
            ---
            ## Fetch the documents

            Selecting rows costs nothing; fetching them talks to the server, so
            it takes a deliberate click. One request per entry to list its
            attachments, one more to download the document itself.
            """
            ),
            task(
                """
            Pick **two entries from different days** and fetch them both. That
            is scenario 3 — two runs side by side — and it is the reason the
            date went into a field instead of only into the title.
            """
            ),
            f_fetch,
        ]
    )
    return (f_fetch,)


@app.cell(hide_code=True)
def _(f_fetch, mo, pick, remote, session, t_results):
    mo.stop(not f_fetch.value, mo.md("*Select rows above and press the button.*"))

    documents, failures = [], []
    for _row in t_results.value:
        _eid = _row["id"]
        try:
            _doc, _upload = remote.fetch_document(session, _eid)
            documents.append(
                {
                    "id": _eid,
                    "title": _row["title"],
                    "date": _row["date"],
                    "document": _doc,
                    "schema": pick(_doc).SCHEMA,
                    "via": _upload["name"],
                }
            )
        except remote.RemoteError as exc:
            failures.append((_eid, _row["title"], str(exc)))

    mo.stop(
        not documents,
        mo.callout(
            mo.md(
                "### Nothing could be turned back into a document\n\n"
                + "\n".join(
                    f"- **{i} · {t}** — {e.splitlines()[0]}" for i, t, e in failures
                )
            ),
            kind="danger",
        ),
    )
    return documents, failures


@app.cell(hide_code=True)
def _(documents, failures, mo, ok):
    mo.vstack(
        [
            x
            for x in (
                ok(
                    f"**{len(documents)} document(s)** read back: "
                    + ", ".join(
                        f"`{d['schema']}` from entry {d['id']}" for d in documents
                    )
                ),
                (
                    mo.callout(
                        mo.md(
                            "**Entries that carry no document:**\n\n"
                            + "\n".join(
                                f"- **{i} · {t}** — {e.splitlines()[0]}"
                                for i, t, e in failures
                            )
                            + "\n\nAn entry written by hand in eLabFTW has extra fields "
                            "but no attachment, and extra fields alone cannot be turned "
                            "back into a document — they are a summary, not the record."
                        ),
                        kind="warn",
                    )
                    if failures
                    else None
                ),
            )
            if x
        ]
    )
    return


@app.cell(hide_code=True)
def _(documents, mo):
    def _facts(entry):
        doc = entry["document"]
        if entry["schema"] == "enzymeml":
            measurements = doc.get("measurements") or []
            phs = sorted({m.get("ph") for m in measurements if m.get("ph")})
            temps = sorted(
                {m.get("temperature") for m in measurements if m.get("temperature")}
            )
            series = sorted(
                {m.get("group_id") for m in measurements if m.get("group_id")}
            )
            return {
                "Entry": entry["id"],
                "Date": entry["date"],
                "Name": doc.get("name") or "",
                "Species": len(doc.get("small_molecules") or [])
                + len(doc.get("proteins") or []),
                "Measurements": len(measurements),
                "Points": sum(
                    len(s.get("data") or [])
                    for m in measurements
                    for s in m.get("species_data") or []
                ),
                "pH": ", ".join(str(p) for p in phs),
                "T": ", ".join(str(t) for t in temps),
                "Series": ", ".join(series),
                "Creators": ", ".join(
                    f"{c.get('given_name','')} {c.get('family_name','')}".strip()
                    for c in doc.get("creators") or []
                ),
            }
        citation = doc.get("citation") or {}
        return {
            "Entry": entry["id"],
            "Date": entry["date"],
            "Name": citation.get("title") or "",
            "Species": len(doc.get("compound") or []),
            "Measurements": len(doc.get("fluid") or []),
            "Points": "",
            "pH": "",
            "T": "",
            "Series": "",
            "Creators": ", ".join(
                f"{a.get('given_name','')} {a.get('family_name','')}".strip()
                for a in citation.get("author") or []
            ),
        }

    mo.vstack(
        [
            mo.md(
                "---\n## Side by side\n\nOne row per document — the comparison "
                "that a folder of PDFs cannot give you."
            ),
            mo.ui.table([_facts(d) for d in documents], selection=None),
        ]
    )
    return


@app.cell(hide_code=True)
def _(documents, mo, why):
    # Which species appear in which document. With one document this is a
    # list; with several it is the question you actually came to ask.
    _names = {}
    for _entry in documents:
        _doc = _entry["document"]
        for _species in (
            (_doc.get("small_molecules") or [])
            + (_doc.get("proteins") or [])
            + (_doc.get("compound") or [])
        ):
            _key = (
                _species.get("id")
                or _species.get("compoundID")
                or _species.get("name")
                or "?"
            )
            _names.setdefault(str(_key), {})[_entry["id"]] = (
                _species.get("name") or _species.get("commonName") or "✓"
            )

    _ids = [d["id"] for d in documents]
    _rows = [
        {"Species": k, **{f"Entry {i}": v.get(i, "—") for i in _ids}}
        for k, v in sorted(_names.items())
    ]
    _shared = sum(1 for _, v in _names.items() if len(v) == len(_ids))

    mo.vstack(
        [
            mo.md(
                f"**{len(_names)} distinct species** across the selection, "
                f"**{_shared}** present in all of them."
            ),
            mo.ui.table(_rows, selection=None, page_size=15),
            why(
                "Why this table is the point",
                """
            The species ids line up because they came from the same
            registries — Rhea's `ethanol` is Rhea's `ethanol` in every
            document that fetched it. Had each experiment invented its own
            names, this table would be a diagonal of ones: every row present
            in exactly one column, nothing comparable with anything.

            That is what identifiers buy, and it is invisible until the
            moment you put two experiments next to each other.
            """,
            ),
        ]
    )
    return


@app.cell(hide_code=True)
def _(compare, documents, mo, summarise, why):
    # With exactly two documents, our own round-trip differ answers "what
    # changed between these" as well as it answers "did the export survive".
    _pair = documents[:2] if len(documents) == 2 else None

    if _pair:
        _deltas = list(compare(_pair[0]["document"], _pair[1]["document"]))
        _counts = ", ".join(f"{n} {k}" for k, n in summarise(_deltas).items() if n)
        _top = sorted({d.path.split(".")[1].split("[")[0]
                       for d in _deltas if d.path.count(".") >= 1})
        _out = mo.vstack([
            mo.md(f"### Entry {_pair[0]['id']} vs. entry {_pair[1]['id']}\n\n"
                  f"**{len(_deltas)} difference(s)** — {_counts or 'none'}. "
                  + (f"They sit under: {', '.join(f'`{t}`' for t in _top)}."
                     if _top else "The two documents are identical.")),
            why("Every difference",
                "```\n" + "\n".join(str(d) for d in _deltas[:60])
                + (f"\n… and {len(_deltas) - 60} more" if len(_deltas) > 60 else "")
                + "\n```"),
        ])
    else:
        _out = mo.md(
            "*Select exactly two entries to get a structural diff between "
            "them here — the same comparison that checks the round trip in "
            "step 1, pointed at two experiments instead.*")
    _out
    return


@app.cell(hide_code=True)
def _(documents, io, json, mo, zipfile):
    _one = len(documents) == 1
    if _one:
        _payload = (
            json.dumps(documents[0]["document"], indent=2, ensure_ascii=False) + "\n"
        ).encode()
        _name = f"entry-{documents[0]['id']}.json"
        _mime = "application/json"
    else:
        _buffer = io.BytesIO()
        with zipfile.ZipFile(_buffer, "w", zipfile.ZIP_DEFLATED) as _zf:
            for _entry in documents:
                _zf.writestr(
                    f"entry-{_entry['id']}.json",
                    json.dumps(_entry["document"], indent=2, ensure_ascii=False) + "\n",
                )
        _payload = _buffer.getvalue()
        _name = "documents.zip"
        _mime = "application/zip"

    mo.vstack(
        [
            mo.md(
                """
            ---
            ## Take them with you

            These are the documents themselves, not a rendering of them: the
            same bytes step 1 attached, ready for the analysis of your choice
            or for step 3.
            """
            ),
            mo.download(
                data=_payload,
                filename=_name,
                mimetype=_mime,
                label=f"⬇ {_name} ({max(1, len(_payload) // 1024)} KB)",
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

    **[Step 3](03_update.py)** closes the loop: correct something in a
    document you just fetched — a wrong organism, a wrong reaction — and
    write it back to the *same* entry, extra fields and attachment
    together, without creating a second one.

    That notebook builds the request, shows it to you in full, and sends
    nothing until you press a button. Reading, as here, is safe; writing
    into a lab notebook somebody else may be reading is not, and the
    difference deserves two notebooks rather than one.
    """
    )
    return


if __name__ == "__main__":
    app.run()
