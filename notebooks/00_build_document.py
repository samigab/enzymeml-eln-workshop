import marimo

__generated_with = "0.24.0"
app = marimo.App(
    width="medium",
    app_title="Step 0 — Build an EnzymeML document",
)


@app.cell(hide_code=True)
def _():
    import marimo as mo

    return (mo,)


@app.cell(hide_code=True)
def _():
    import io
    import json
    import re
    from pathlib import Path

    import pandas as pd
    import pyenzyme as pe

    return Path, io, json, pd, pe, re


@app.cell(hide_code=True)
def _(mo):
    def task(body: str):
        """A workshop instruction: the concrete values for the example dataset.

        Kept visually apart from the explanations so that the notebook stays
        readable for someone building their own document, who can skip every
        blue box without losing the thread.
        """
        return mo.callout(mo.md(body), kind="info", title="📝 Workshop task")

    def why(title: str, body: str):
        """Background reading, folded away.

        The default view of every block is: heading, one sentence, form,
        result. Whoever wants the reasoning opens the fold; whoever is here
        to fill in a form is not made to scroll past it.
        """
        return mo.accordion({f"💡 {title}": mo.md(body)})

    def ok(line: str):
        """A one-line confirmation under a form."""
        return mo.md(f"✅ &nbsp;{line}")

    def filled(editor, key="id"):
        """The rows of a data editor that carry an identifier.

        An editor hands back exactly what is on screen — blank rows, half-typed
        rows and all. A row without an identifier is a row someone started and
        abandoned, so it is not a building block yet.
        """
        out = []
        for raw in editor.value:
            row = {k: ("" if v is None else v) for k, v in raw.items()}
            if str(row.get(key, "")).strip():
                row[key] = str(row[key]).strip()
                out.append(row)
        return out

    def text(row, key, default=""):
        value = str(row.get(key, "")).strip()
        return value or default

    def number(row, key, default=None):
        try:
            return float(str(row.get(key, "")).strip())
        except (TypeError, ValueError):
            return default

    def flag(row, key, default=True):
        value = row.get(key, "")
        if isinstance(value, bool):
            return value
        if str(value).strip() == "":
            return default
        return str(value).strip().lower() in ("true", "yes", "y", "1")

    return filled, flag, number, ok, task, text, why


@app.cell(hide_code=True)
def _(mo, task):
    mo.vstack([
        mo.md(
            """
            # Step 0 — Build an EnzymeML document

            A form, filled in block by block. Each block is one part of an
            EnzymeML document: a table or a few fields, and underneath, what
            arrived. The tables grow — **+** adds a row, the row menu deletes
            one — so the same notebook carries a document with one substrate
            or with twenty. The code that does the building is folded away;
            click any collapsed cell to read it.

            | Block | What it holds |
            |---|---|
            | 1 · Document | title, description, who did it, references |
            | 2 · Vessels | where the reaction happened, and how much of it |
            | 3 · Registries | two identifiers that fill blocks 4–6 for you |
            | 4 · Small molecules | substrates, products, cofactors, buffers |
            | 5 · Proteins | enzymes, with EC number and organism |
            | 6 · Reaction | who reacts with whom, and who merely catalyses |
            | 7 · Measurements | the numbers, and the conditions behind them |
            | 8 · Assemble | all of it as one document, ready to download |

            Nothing here knows that lab notebooks exist — that is
            [step 1](01_export_eln.py). The **kinetic model is deliberately
            left out**: fitting rate laws is its own session, and a document
            without a model is still a complete record of what was measured.
            """
        ),
        task(
            """
            **Boxes like this one are the workshop instructions** and give the
            concrete values for the example dataset — yeast alcohol
            dehydrogenase oxidising ethanol, three runs, eleven time points
            each.

            Everything outside these boxes applies to *any* document. If you
            came with data of your own, skip the blue boxes and put your own
            values in the same forms.
            """
        ),
    ])
    return


@app.cell(hide_code=True)
def _(doc, mo):
    # The document at a glance — this cell sits at the top but depends on
    # everything below it, so it updates live as the blocks are filled in.
    mo.vstack([
        mo.hstack(
            [
                mo.stat(len(doc.small_molecules) + len(doc.proteins),
                        label="Species", bordered=True,
                        caption=f"{len(doc.proteins)} of them proteins"),
                mo.stat(sum(len(r.reactants) + len(r.products) + len(r.modifiers)
                            for r in doc.reactions),
                        label="Reaction participants", bordered=True,
                        caption=f"in {len(doc.reactions)} reaction(s)"),
                mo.stat(len(doc.measurements), label="Measurements",
                        bordered=True,
                        caption=f"in {len(doc.vessels)} vessel(s)"),
                mo.stat(sum(len(e.data) for m in doc.measurements
                            for e in m.species_data),
                        label="Data points", bordered=True,
                        caption="from the CSV files"),
            ],
            widths="equal",
        ),
        mo.md("*Your document so far — these numbers update as you fill in "
              "the blocks below.*"),
    ])
    return


@app.cell(hide_code=True)
def _(mo, task):
    mo.vstack([
        mo.md(
            """
            ---
            ## 1 · The document

            Who, what, and where to read more. None of it is derivable from
            the measurements — which is precisely why it has to be written
            down somewhere that will still be readable in ten years.
            """
        ),
        task(
            """
            Put **your initials in the title**: the public demo instance
            shares one account, so fifteen entries called *ADH kinetics* are
            fifteen entries nobody can tell apart.

            Use a **placeholder e-mail**. The demo is public and reset every
            24 h; no real addresses, no real research data.
            """
        ),
    ])
    return


@app.cell(hide_code=True)
def _(mo):
    f_doc = mo.md(
        """
        **Title** — what you will search for in two years {name}

        **Description** {description}

        **Who measured?** {given_name} {family_name} {mail}

        **References** — DOI or URL of the method, one per line {references}
        """
    ).batch(
        name=mo.ui.text(full_width=True, value="ADH kinetics: ethanol oxidation"),
        description=mo.ui.text_area(
            full_width=True, rows=3,
            placeholder="What was measured, on what, and why?"),
        given_name=mo.ui.text(placeholder="First name"),
        family_name=mo.ui.text(placeholder="Last name"),
        mail=mo.ui.text(placeholder="a placeholder — the demo is public!"),
        references=mo.ui.text_area(full_width=True, rows=2,
                                   placeholder="https://doi.org/…"),
    )
    f_doc
    return (f_doc,)


@app.cell(hide_code=True)
def _(mo, task):
    mo.vstack([
        mo.md(
            """
            ---
            ## 2 · Vessels

            Every species lives in a vessel: a cuvette, a well, a fermenter.
            One row per vessel — most experiments have exactly one.
            """
        ),
        task(
            """
            One vessel is enough: a **quartz cuvette** of **1.0 ml**. Leave
            the row as it is.
            """
        ),
    ])
    return


@app.cell(hide_code=True)
def _(mo):
    t_vessels = mo.ui.data_editor(
        [{"id": "v1", "name": "quartz cuvette, 1 cm",
          "volume": 1.0, "unit": "ml", "constant": True}],
        label="**Vessels** — `unit` accepts anything PyEnzyme can parse: "
              "`ml`, `ul`, `l`, `mmol / l`",
    )
    t_vessels
    return (t_vessels,)


@app.cell(hide_code=True)
def _(filled, flag, number, pe, t_vessels, text):
    # Built fresh from the table on every run rather than edited in place, so
    # re-running this cell alone can never leave a half-updated object behind.
    vessel_error = None
    vessels = []
    try:
        vessels = [
            pe.Vessel(
                id=row["id"],
                name=text(row, "name", row["id"]),
                volume=number(row, "volume", 0.0),
                unit=text(row, "unit", "l"),
                constant=flag(row, "constant", True),
            )
            for row in filled(t_vessels)
        ]
    except Exception as exc:  # an unparseable unit should not kill the notebook
        vessel_error = str(exc)
    return vessel_error, vessels


@app.cell(hide_code=True)
def _(mo, ok, vessel_error, vessels, why):
    def _decomposition(vessel):
        rows = "".join(
            f"<tr><td>{b.kind.value}</td><td>{b.exponent}</td>"
            f"<td>{b.multiplier}</td><td>{b.scale}</td></tr>"
            for b in vessel.unit.base_units
        )
        return (
            f"**`{vessel.id}`** stores `{vessel.unit.name}` as:\n\n"
            "<table>"
            "<tr><th>base unit</th><th>exponent</th><th>multiplier</th>"
            f"<th>scale</th></tr>{rows}</table>"
        )

    mo.callout(
        mo.md(f"**The vessel could not be built**\n\n> `{vessel_error}`"),
        kind="warn") if vessel_error else mo.vstack([
        ok(", ".join(f"`{v.id}` — {v.name}, {v.volume} `{v.unit.name}`"
                     for v in vessels)),
        why(
            "Why the unit looks different from what you typed",
            "\n\n".join(_decomposition(v) for v in vessels) +
            """

            You typed the string `ml`; the document holds *litre, exponent 1,
            scale −3*. PyEnzyme decomposes every unit into SBML base units,
            so `1/s` and `mmol / l` end up as unambiguous as `ml` does.

            This is the argument of the whole workshop in miniature: **what
            you type for convenience and what the file stores for machines
            need not be the same thing** — as long as something does the
            translation reliably, every time, without you remembering to.
            """,
        ),
    ]) if vessels else mo.callout(
        mo.md("**No vessel yet** — every species needs one."), kind="warn")
    return


@app.cell(hide_code=True)
def _(mo, task, why):
    mo.vstack([
        mo.md(
            """
            ---
            ## 3 · Let the registries fill in blocks 4–6

            Give two identifiers and the next three blocks arrive pre-filled:
            the reaction with every molecule in it from
            [Rhea](https://www.rhea-db.org), the enzyme with EC number,
            organism and sequence from [UniProt](https://www.uniprot.org).
            Whatever comes back seeds the tables below, where you can still
            correct and extend it.
            """
        ),
        why(
            "Why fetch instead of typing",
            """
            An InChIKey retyped from a browser tab is a 27-character string
            with no checksum, and a wrong one is worse than none, because it
            is wrong *confidently*. The registries have already done the
            looking-up; two short identifiers replace five molecules' worth
            of retyping.

            Turn the switch off — or work offline — and the tables are
            seeded with the built-in example instead. Same tables, same
            columns; the only difference is who typed the identifiers.
            """,
        ),
        task(
            """
            Leave the two identifiers as they are:
            [RHEA:25290](https://www.rhea-db.org/rhea/25290) is *ethanol +
            NAD⁺ ⇌ acetaldehyde + NADH + H⁺*, and
            [P00330](https://www.uniprot.org/uniprotkb/P00330) is yeast
            alcohol dehydrogenase 1.

            Then flip the switch off and on and watch blocks 4–6 change.
            **Fill in the tables after the fetch**, not before — changing an
            identifier rebuilds them from scratch and your edits go with
            them.
            """
        ),
    ])
    return


@app.cell(hide_code=True)
def _(mo):
    f_fetch = mo.md(
        """
        {fetch} &nbsp; **Ask the registries**

        **Rhea reaction** {rhea} &nbsp;&nbsp;
        **UniProt accessions** {uniprot}
        """
    ).batch(
        fetch=mo.ui.switch(value=True),
        rhea=mo.ui.text(value="RHEA:25290", placeholder="RHEA:… (optional)"),
        uniprot=mo.ui.text(value="P00330", placeholder="comma-separated"),
    )
    f_fetch
    return (f_fetch,)


@app.cell(hide_code=True)
def _():
    # The built-in example, in exactly the shape the tables below use. This is
    # what the two fetch calls save you from typing — and the fallback when the
    # conference wifi gives up ten minutes into the session.
    EXAMPLE_MOLECULES = [
        {"id": "ethanol", "name": "ethanol",
         "inchikey": "LFQSCWFLJHTTHZ-UHFFFAOYSA-N", "constant": False},
        {"id": "nad_1", "name": "NAD(1-)",
         "inchikey": "BAWFJGJZGIEFAR-NNYOXOHSSA-M", "constant": False},
        {"id": "acetaldehyde", "name": "acetaldehyde",
         "inchikey": "IKHGUXGNUITLKF-UHFFFAOYSA-N", "constant": False},
        {"id": "nadh_2", "name": "NADH(2-)",
         "inchikey": "BOPGDPNILDQYTO-NNYOXOHSSA-L", "constant": False},
        {"id": "hydron", "name": "hydron",
         "inchikey": "GPRLSGONYQIRFK-UHFFFAOYSA-N", "constant": False},
    ]
    EXAMPLE_PROTEINS = [
        {"id": "alcohol_dehydrogenase_1", "name": "Alcohol dehydrogenase 1",
         "ecnumber": "1.1.1.1", "organism": "Saccharomyces cerevisiae",
         "organism_tax_id": "559292", "constant": True},
    ]
    EXAMPLE_REACTION = {"id": "RHEA:25290", "name": "ethanol oxidation",
                        "reversible": True}
    EXAMPLE_PARTICIPANTS = (
        [{"species_id": s, "role": "reactant", "stoichiometry": 1.0}
         for s in ("ethanol", "nad_1")]
        + [{"species_id": s, "role": "product", "stoichiometry": 1.0}
           for s in ("acetaldehyde", "nadh_2", "hydron")]
        + [{"species_id": "alcohol_dehydrogenase_1", "role": "biocatalyst",
            "stoichiometry": 1.0}]
    )
    return (
        EXAMPLE_MOLECULES,
        EXAMPLE_PARTICIPANTS,
        EXAMPLE_PROTEINS,
        EXAMPLE_REACTION,
    )


@app.cell(hide_code=True)
def _(
    EXAMPLE_MOLECULES,
    EXAMPLE_PARTICIPANTS,
    EXAMPLE_PROTEINS,
    EXAMPLE_REACTION,
    f_fetch,
    pe,
    vessels,
):
    def from_registries(rhea_id, accessions, vessel_id):
        """Two identifiers in, three tables' worth of rows out."""
        reaction, molecules, proteins = None, [], []
        if rhea_id:
            reaction, molecules = pe.fetch_rhea(rhea_id, vessel_id=vessel_id)
        for accession in accessions:
            proteins.append(pe.fetch_uniprot(accession, vessel_id=vessel_id))

        seeds = {
            "molecules": [{"id": m.id, "name": m.name,
                           "inchikey": m.inchikey or "", "constant": m.constant}
                          for m in molecules],
            "proteins": [{"id": p.id, "name": p.name,
                          "ecnumber": p.ecnumber or "",
                          "organism": p.organism or "",
                          "organism_tax_id": p.organism_tax_id or "",
                          "constant": p.constant}
                         for p in proteins],
            "reaction": {"id": reaction.id, "name": reaction.name,
                         "reversible": reaction.reversible} if reaction
                        else dict(EXAMPLE_REACTION),
            "participants": [
                {"species_id": s.species_id, "role": role,
                 "stoichiometry": s.stoichiometry}
                for role, group in (("reactant", reaction.reactants if reaction else []),
                                    ("product", reaction.products if reaction else []))
                for s in group
            ] + [{"species_id": p.id, "role": "biocatalyst",
                  "stoichiometry": 1.0} for p in proteins],
        }
        # Everything a five-column table cannot sensibly show: the 350-character
        # sequence, the synonym lists, the cross-references. Kept aside by id and
        # merged back when the objects are built, so correcting a name in the
        # table does not silently discard the parts you never saw.
        extras = {
            m.id: {"inchi": m.inchi, "canonical_smiles": m.canonical_smiles,
                   "synonymous_names": list(m.synonymous_names),
                   "references": list(m.references)}
            for m in molecules
        }
        extras.update({
            p.id: {"sequence": p.sequence, "references": list(p.references)}
            for p in proteins
        })
        return seeds, extras

    _vessel_id = vessels[0].id if vessels else "v1"
    _fallback = {"molecules": EXAMPLE_MOLECULES, "proteins": EXAMPLE_PROTEINS,
                 "reaction": EXAMPLE_REACTION,
                 "participants": EXAMPLE_PARTICIPANTS}

    if f_fetch.value["fetch"]:
        try:
            seeds, extras = from_registries(
                f_fetch.value["rhea"].strip(),
                [a.strip() for a in f_fetch.value["uniprot"].split(",") if a.strip()],
                _vessel_id,
            )
            origin, fetch_error = "fetched from Rhea and UniProt", None
        except Exception as exc:
            seeds, extras = _fallback, {}
            origin, fetch_error = "the built-in example", str(exc)
    else:
        seeds, extras = _fallback, {}
        origin, fetch_error = "the built-in example (switch is off)", None
    return extras, fetch_error, origin, seeds


@app.cell(hide_code=True)
def _(extras, fetch_error, mo, ok, origin, seeds):
    _carried = sum(1 for values in extras.values()
                   for value in values.values() if value)

    mo.vstack([x for x in (
        ok(
            f"Tables 4–6 seeded from **{origin}**: "
            f"{len(seeds['molecules'])} small molecules, "
            f"{len(seeds['proteins'])} proteins, "
            f"{len(seeds['participants'])} reaction participants"
            + (f" — plus {_carried} values carried along out of sight "
               "(sequences, InChIs, SMILES, synonyms, cross-references)."
               if _carried else ".")
        ),
        mo.callout(
            mo.md(f"**The registries could not be reached**, so the built-in "
                  f"example was used instead:\n\n> `{fetch_error}`"),
            kind="warn") if fetch_error else None,
    ) if x])
    return


@app.cell(hide_code=True)
def _(mo, task, why):
    mo.vstack([
        mo.md(
            """
            ---
            ## 4 · Small molecules

            Substrates, products, cofactors, buffer components — anything
            that is not a protein, one row per species.
            """
        ),
        why(
            "What the columns mean",
            """
            `id` is what the reaction and the measurements will refer to.
            `constant` marks the species whose concentration you hold fixed
            rather than follow.

            The `inchikey` is the column that turns a name into an identity:
            *ethanol*, *EtOH* and *ethyl alcohol* are three strings and one
            `LFQSCWFLJHTTHZ-UHFFFAOYSA-N`.
            """,
        ),
        task(
            """
            Nothing to do if the fetch worked — check that five molecules
            arrived and that each has an InChIKey.

            If you want to see what the fetch spared you: turn the switch in
            block 3 off, then compare the two tables. They are identical, and
            one of them somebody had to type.
            """
        ),
    ])
    return


@app.cell(hide_code=True)
def _(mo, seeds):
    t_molecules = mo.ui.data_editor(
        [dict(row) for row in seeds["molecules"]] or
        [{"id": "", "name": "", "inchikey": "", "constant": False}],
        label="**Small molecules**",
    )
    t_molecules
    return (t_molecules,)


@app.cell(hide_code=True)
def _(mo, task):
    mo.vstack([
        mo.md(
            """
            ---
            ## 5 · Proteins

            The same table, four columns richer. `ecnumber` says what the
            enzyme *does*; `organism_tax_id` says exactly which organism it
            came from — *S. cerevisiae* is a name, `559292` is a strain.
            """
        ),
        task(
            """
            One protein, from UniProt. Note what is *not* in the table: the
            347-amino-acid sequence came along with the fetch and is carried
            into the document anyway. Tables are for what humans read; the
            file keeps the rest.
            """
        ),
    ])
    return


@app.cell(hide_code=True)
def _(mo, seeds):
    t_proteins = mo.ui.data_editor(
        [dict(row) for row in seeds["proteins"]] or
        [{"id": "", "name": "", "ecnumber": "", "organism": "",
          "organism_tax_id": "", "constant": True}],
        label="**Proteins** — enzymes and any other protein in the vessel",
    )
    t_proteins
    return (t_proteins,)


@app.cell(hide_code=True)
def _(extras, filled, flag, pe, t_molecules, t_proteins, text, vessels):
    _vessel = vessels[0].id if vessels else "v1"

    small_molecules = [
        pe.SmallMolecule(
            id=row["id"],
            name=text(row, "name", row["id"]),
            vessel_id=_vessel,
            constant=flag(row, "constant", False),
            inchikey=text(row, "inchikey") or None,
            # merged back: what the registry knew and the table cannot show
            **{k: v for k, v in extras.get(row["id"], {}).items() if v},
        )
        for row in filled(t_molecules)
    ]

    proteins = [
        pe.Protein(
            id=row["id"],
            name=text(row, "name", row["id"]),
            vessel_id=_vessel,
            constant=flag(row, "constant", True),
            ecnumber=text(row, "ecnumber") or None,
            organism=text(row, "organism") or None,
            organism_tax_id=text(row, "organism_tax_id") or None,
            **{k: v for k, v in extras.get(row["id"], {}).items() if v},
        )
        for row in filled(t_proteins)
    ]

    species_ids = [s.id for s in small_molecules + proteins]
    return proteins, small_molecules, species_ids


@app.cell(hide_code=True)
def _(mo, proteins, small_molecules):
    mo.accordion({
        f"🔍 Review: {len(small_molecules) + len(proteins)} species as the "
        "document will store them": mo.ui.table(
            [{"ID": s.id, "Name": s.name, "Kind": kind,
              "Identifier": getattr(s, "inchikey", None) or
                            getattr(s, "ecnumber", None) or "",
              "Constant": s.constant,
              "Carried along": ", ".join(
                  k for k in ("inchi", "canonical_smiles", "sequence",
                              "synonymous_names", "references")
                  if getattr(s, k, None))}
             for kind, group in (("small molecule", small_molecules),
                                 ("protein", proteins))
             for s in group],
            selection=None),
    }) if (small_molecules or proteins) else mo.callout(
        mo.md("**No species yet.**"), kind="warn")
    return


@app.cell(hide_code=True)
def _(mo, task, why):
    mo.vstack([
        mo.md(
            """
            ---
            ## 6 · The reaction

            One row per participant — and among them **the one row no
            database gave you**. Rhea knows the chemistry, UniProt knows the
            protein, and neither knows that *this* protein catalyses *this*
            reaction. That link is your experiment, not a database fact, and
            it is the reason the document exists at all.
            """
        ),
        why(
            "The roles",
            """
            `role` is either `reactant`, `product`, or one of the modifier
            roles — `biocatalyst`, `catalyst`, `inhibitor`, `activator`,
            `buffer`, `solvent`, `additive`. A modifier takes part without
            being consumed.

            The biocatalyst row is seeded for you so the example runs. Delete
            it and look at what is left: a correct chemical equation and a
            correct protein entry, with nothing connecting them.
            """,
        ),
        task(
            """
            Six rows: two reactants, three products, one biocatalyst. Leave
            them, but read the last one — everything above it was fetched,
            and that one was not.
            """
        ),
    ])
    return


@app.cell(hide_code=True)
def _(mo, seeds):
    f_reaction = mo.md(
        """
        **Reaction ID** {id} &nbsp;&nbsp; **Name** {name} &nbsp;&nbsp;
        **Reversible** {reversible}
        """
    ).batch(
        id=mo.ui.text(value=seeds["reaction"]["id"]),
        name=mo.ui.text(value=seeds["reaction"]["name"] or ""),
        reversible=mo.ui.checkbox(value=bool(seeds["reaction"]["reversible"])),
    )

    t_participants = mo.ui.data_editor(
        [dict(row) for row in seeds["participants"]] or
        [{"species_id": "", "role": "reactant", "stoichiometry": 1.0}],
        label="**Participants** — `species_id` must match an `id` from block 4 "
              "or 5",
    )
    mo.vstack([f_reaction, t_participants])
    return f_reaction, t_participants


@app.cell(hide_code=True)
def _(f_reaction, filled, number, pe, species_ids, t_participants, text):
    _ROLES = {role.value for role in pe.ModifierRole}

    reaction = pe.Reaction(
        id=f_reaction.value["id"] or "r1",
        name=f_reaction.value["name"] or None,
        reversible=f_reaction.value["reversible"],
    )

    unknown_species, unknown_roles = [], []
    for _row in filled(t_participants, key="species_id"):
        _sid = _row["species_id"]
        _role = text(_row, "role", "reactant").lower()
        _stoich = number(_row, "stoichiometry", 1.0)
        if _sid not in species_ids:
            # A typo here does not raise; it produces a document that references
            # a species nobody declared. Better said out loud than caught later.
            unknown_species.append(_sid)
        if _role == "reactant":
            reaction.add_to_reactants(species_id=_sid, stoichiometry=_stoich)
        elif _role == "product":
            reaction.add_to_products(species_id=_sid, stoichiometry=_stoich)
        elif _role in _ROLES:
            reaction.add_to_modifiers(species_id=_sid, role=pe.ModifierRole(_role))
        else:
            unknown_roles.append(_role)
    return reaction, unknown_roles, unknown_species


@app.cell(hide_code=True)
def _(mo, ok, reaction, unknown_roles, unknown_species):
    _equation = (
        " + ".join(f"{s.stoichiometry:g} {s.species_id}" for s in reaction.reactants)
        + (" ⇌ " if reaction.reversible else " → ")
        + " + ".join(f"{s.stoichiometry:g} {s.species_id}" for s in reaction.products)
    )
    _modifiers = "".join(f"<br>&emsp;catalysed by `{m.species_id}` "
                         f"(*{m.role.value}*)" for m in reaction.modifiers)

    mo.vstack([x for x in (
        ok(f"`{reaction.id}` &nbsp; **{_equation}**{_modifiers}"),
        mo.callout(
            mo.md("**Participants that are not declared as species:** "
                  + ", ".join(f"`{s}`" for s in unknown_species)
                  + "\n\nAdd them in block 4 or 5, or fix the spelling."),
            kind="warn") if unknown_species else None,
        mo.callout(
            mo.md("**Unknown roles, these rows were skipped:** "
                  + ", ".join(f"`{r}`" for r in unknown_roles)),
            kind="warn") if unknown_roles else None,
    ) if x])
    return


@app.cell(hide_code=True)
def _(mo, task):
    mo.vstack([
        mo.md(
            """
            ---
            ## 7 · The measurements

            **This is the source of truth.** Nothing in blocks 1–6 rewrites
            it; the document was built *around* it. A raw file carries no
            units and no identity, so this block closes that gap in three
            short forms: **7a** which column is which species, **7b** the
            conditions, **7c** what was in the vessel without being followed.
            """
        ),
        task(
            """
            Leave the upload empty and the three bundled CSVs are used —
            `examples/workshop/data/ethanol_*mM.csv`, one file per run. Drop
            your own CSVs on it if you brought some.
            """
        ),
    ])
    return


@app.cell(hide_code=True)
def _(mo):
    f_csv = mo.ui.file(
        filetypes=[".csv"], multiple=True, kind="area",
        label="Drop time-series CSVs here — one file per run, or one file with "
              "an `id` column",
    )
    f_csv
    return (f_csv,)


@app.cell(hide_code=True)
def _(Path, f_csv, io, pd, re):
    DATA_DIR = Path(__file__).resolve().parent.parent / "examples/workshop/data"

    def natural(name):
        """Sort key that reads digit runs as numbers, so 2 comes before 18."""
        return [int(p) if p.isdigit() else p
                for p in re.split(r"(\d+)", name)]

    def read_runs(uploads):
        """One frame from many CSVs, with a run identifier on every row.

        PyEnzyme splits a frame into measurements on an `id` column. A file that
        does not carry one *is* one run, and its filename is as good a name for
        it as anything the file itself offers.
        """
        frames = []
        for name, payload in sorted(uploads, key=lambda u: natural(u[0])):
            frame = pd.read_csv(io.BytesIO(payload))
            if "id" not in frame.columns:
                frame.insert(0, "id", Path(name).stem)
            frames.append(frame)
        # An empty frame rather than an exception: a notebook with nothing to
        # read yet is a normal state, not a broken one.
        return pd.concat(frames, ignore_index=True) if frames \
            else pd.DataFrame({"id": []})

    if f_csv.value:
        raw = read_runs([(f.name, f.contents) for f in f_csv.value])
        source = f"{len(f_csv.value)} uploaded file(s)"
    else:
        _bundled = list(DATA_DIR.glob("*.csv"))
        raw = read_runs([(p.name, p.read_bytes()) for p in _bundled])
        source = f"{len(_bundled)} bundled example file(s)"

    columns = [c for c in raw.columns if c != "id"]
    return columns, raw, source


@app.cell(hide_code=True)
def _(columns, mo, ok, raw, source):
    mo.vstack([
        ok(f"**{len(raw)} rows** from {source}, "
           f"{raw['id'].nunique()} runs, {len(columns)} data columns"),
        mo.accordion({"🔍 First rows of the raw data": mo.ui.table(
            raw.head(6).to_dict("records"), selection=None)}),
    ])
    return


@app.cell(hide_code=True)
def _(mo, task):
    mo.vstack([
        mo.md(
            """
            ### 7a · Which column is which species

            Put the matching species `id` next to each column — or the word
            `time` for the time axis. **A column left blank is not
            imported**, which is how you drop the instrument's bookkeeping
            columns. The proposals are guesses from matching column names
            against your species ids; that is why they sit in an editable
            table rather than being applied quietly.
            """
        ),
        task(
            """
            Check all three rows. `time_min → time`, `ethanol_mmol_per_l →
            ethanol`, `nadh_mmol_per_l → nadh_2`.

            That last one is the whole exercise in one line: the file says
            *nadh*, the reaction says `nadh_2`, and only a human knows they
            are the same thing.
            """
        ),
    ])
    return


@app.cell(hide_code=True)
def _(columns, mo, species_ids):
    def _guess(column):
        tokens = set(column.lower().replace("-", "_").split("_"))
        if column.lower().startswith("time"):
            return "time"
        for sid in species_ids:
            if sid.lower() in tokens or sid.lower().split("_")[0] in tokens:
                return sid
        return ""

    t_mapping = mo.ui.data_editor(
        [{"column": c, "maps to": _guess(c)} for c in columns] or
        [{"column": "", "maps to": ""}],
        label="**Column mapping** — `time`, a species id, or blank to skip",
        editable_columns=["maps to"],
    )
    t_mapping
    return (t_mapping,)


@app.cell(hide_code=True)
def _(mo):
    f_units = mo.md(
        """
        **Data unit** {data_unit} &nbsp;&nbsp; **Time unit** {time_unit}
        &nbsp;&nbsp; **What was measured** {data_type}
        """
    ).batch(
        data_unit=mo.ui.text(value="mmol / l"),
        time_unit=mo.ui.text(value="min"),
        data_type=mo.ui.dropdown(
            ["concentration", "absorbance", "amount", "conversion",
             "fluorescence", "peakarea", "transmittance", "turnover", "yield"],
            value="concentration"),
    )
    mo.vstack([
        mo.md("The units the CSV does not carry. They apply to every mapped "
              "column, which is the common case; a file mixing units per "
              "column needs one pass per unit."),
        f_units,
    ])
    return (f_units,)


@app.cell(hide_code=True)
def _(columns, f_units, pe, raw, t_mapping):
    mapping = {row["column"]: str(row["maps to"] or "").strip()
               for row in t_mapping.value
               if row["column"] in columns}
    kept = {c: t for c, t in mapping.items() if t}

    measurements, measurement_error = [], None
    if "time" not in kept.values():
        measurement_error = "No column is mapped to `time`."
    else:
        try:
            _frame = raw[["id"] + list(kept)].rename(columns=kept)
            measurements = pe.from_dataframe(
                _frame,
                data_unit=f_units.value["data_unit"],
                time_unit=f_units.value["time_unit"],
            )
            for _m in measurements:
                for _entry in _m.species_data:
                    _entry.data_type = pe.DataTypes(f_units.value["data_type"])
                    _entry.is_simulated = False
        except Exception as exc:
            measurement_error = str(exc)

    followed = sorted({e.species_id for m in measurements for e in m.species_data})
    return followed, measurement_error, measurements


@app.cell(hide_code=True)
def _(mo, task, why):
    mo.vstack([
        mo.md(
            """
            ### 7b · The conditions

            pH, temperature, and which runs belong together — properties of
            the experiment, not of any column. The `id` column is read-only;
            it is the key the data came in under.
            """
        ),
        why(
            "What the series ID is for",
            """
            A shared `group_id` is what tells a reader in two years that
            these runs are one dilution series and not three unrelated
            experiments. It is one string, repeated — and it is the
            difference between *three files that happen to sit together* and
            *one experiment in three parts*.
            """,
        ),
        task(
            """
            All three runs: **pH 8.8**, **25 °C**, series ID
            `dilution_series_1` — the same string in all three rows, that is
            the point of it.

            Give each run a name a human can read: `Ethanol 2 mM`, `Ethanol
            8 mM`, `Ethanol 18 mM` match the file names.
            """
        ),
    ])
    return


@app.cell(hide_code=True)
def _(measurements, mo):
    t_runs = mo.ui.data_editor(
        [{"id": m.id, "name": m.name, "group_id": "", "ph": None,
          "temperature": None}
         for m in measurements] or
        [{"id": "", "name": "", "group_id": "", "ph": None,
          "temperature": None}],
        label="**Runs** — one row per measurement found in the files",
        editable_columns=["name", "group_id", "ph", "temperature"],
    )
    t_runs
    return (t_runs,)


@app.cell(hide_code=True)
def _(followed, mo, species_ids, task):
    _missing = [s for s in species_ids if s not in followed]

    t_initials = mo.ui.data_editor(
        [{"species_id": s, "initial": None} for s in _missing] or
        [{"species_id": "", "initial": None}],
        label="**Species present but not followed** — initial concentration, "
              "in the data unit above; applies to every run",
        editable_columns=["initial"],
    )

    mo.vstack([
        mo.md(
            f"""
            ### 7c · The species you did not follow

            {len(_missing)} of your species have no column in the files:
            {", ".join(f"`{s}`" for s in _missing) or "none"}. They were in
            the vessel all the same, and leaving them out reads as *there was
            no enzyme in the cuvette*. An initial concentration is data too —
            fill in what you pipetted.
            """
        ),
        task(
            """
            NAD⁺ (`nad_1`) **20**, the enzyme **0.0005**, acetaldehyde and H⁺
            **0** — nothing had reacted yet at t = 0.
            """
        ),
        t_initials,
    ])
    return (t_initials,)


@app.cell(hide_code=True)
def _(f_units, filled, measurements, number, pe, t_initials, t_runs, text):
    # from_dataframe returns fresh objects each run, and both loops below only
    # touch those — so this cell is safe to re-run on its own.
    _conditions = {row["id"]: row for row in filled(t_runs)}
    _initials = [(row["species_id"], number(row, "initial"))
                 for row in filled(t_initials, key="species_id")]

    for _measurement in measurements:
        _row = _conditions.get(_measurement.id, {})
        _measurement.name = text(_row, "name", _measurement.id)
        _measurement.group_id = text(_row, "group_id") or None
        _measurement.ph = number(_row, "ph")
        _measurement.temperature = number(_row, "temperature")
        _measurement.temperature_unit = (
            "°C" if _measurement.temperature is not None else None)
        for _sid, _initial in _initials:
            if _initial is None:
                continue
            # No time series, but a concentration all the same — whatever the
            # instrument recorded over time, what you pipetted was an amount.
            _measurement.add_to_species_data(
                species_id=_sid, initial=_initial, prepared=_initial,
                data_unit=f_units.value["data_unit"],
                time_unit=f_units.value["time_unit"],
                data_type=pe.DataTypes.CONCENTRATION,
                is_simulated=False, time=[], data=[],
            )
    return


@app.cell(hide_code=True)
def _(measurement_error, measurements, mo):
    mo.callout(
        mo.md(f"**The measurements could not be read**\n\n> `{measurement_error}`"),
        kind="warn") if measurement_error else mo.ui.table(
        [{"ID": m.id, "Name": m.name, "Series": m.group_id, "pH": m.ph,
          "T [°C]": m.temperature,
          "Points": sum(len(e.data) for e in m.species_data),
          "Followed": ", ".join(e.species_id for e in m.species_data if e.data),
          "Initial only": ", ".join(e.species_id for e in m.species_data
                                    if not e.data)}
         for m in measurements],
        selection=None)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ---
    ## 8 · Assemble

    Every block above was built on its own so you could look at it. Now they
    become one document — in a single expression, so re-running this cell can
    never add anything twice.
    """)
    return


@app.cell(hide_code=True)
def _(f_doc, measurements, pe, proteins, reaction, small_molecules, vessels):
    _meta = f_doc.value

    doc = pe.EnzymeMLDocument(
        name=_meta["name"] or "Untitled experiment",
        description=_meta["description"] or None,
        references=[line.strip() for line in _meta["references"].splitlines()
                    if line.strip()],
        vessels=list(vessels),
        small_molecules=list(small_molecules),
        proteins=list(proteins),
        reactions=[reaction] if reaction.reactants or reaction.products else [],
        measurements=list(measurements),
        creators=(
            [pe.Creator(given_name=_meta["given_name"] or "",
                        family_name=_meta["family_name"] or "",
                        mail=_meta["mail"] or "")]
            if _meta["given_name"] or _meta["family_name"] else []
        ),
    )
    return (doc,)


@app.cell(hide_code=True)
def _(doc, mo):
    _blanks = [
        label for label, ok_ in (
            ("a description (block 1)", bool(doc.description)),
            ("a creator (block 1)", bool(doc.creators)),
            ("a reference (block 1)", bool(doc.references)),
            ("pH on every run (block 7b)",
             all(m.ph is not None for m in doc.measurements)),
            ("a temperature on every run (block 7b)",
             all(m.temperature is not None for m in doc.measurements)),
            ("a series ID on every run (block 7b)",
             all(m.group_id for m in doc.measurements)),
            ("an InChIKey on every small molecule (block 4)",
             all(s.inchikey for s in doc.small_molecules)),
        ) if not ok_
    ]

    mo.vstack([x for x in (
        mo.callout(
            mo.md(
                f"**{doc.name}** — {len(doc.vessels)} vessel(s), "
                f"{len(doc.small_molecules)} small molecules, "
                f"{len(doc.proteins)} protein(s), "
                f"{len(doc.reactions)} reaction(s), "
                f"{len(doc.measurements)} measurements, "
                f"{sum(len(e.data) for m in doc.measurements for e in m.species_data)} "
                "data points."
            ),
            kind="success"),
        mo.callout(
            mo.md("**Still missing:** "
                  + "".join(f"\n- {b}" for b in _blanks)
                  + "\n\nThe document is valid without them. It is simply not "
                  "findable — these are the fields somebody searches on when "
                  "they do not already know what they are looking for."),
            kind="neutral", title="Checklist") if _blanks else mo.callout(
            mo.md("Every recommended field is filled in."),
            kind="success", title="Checklist"),
    ) if x])
    return


@app.cell(hide_code=True)
def _(doc, mo):
    mo.accordion({
        "🔍 Review the finished document": mo.ui.tabs({
            "Species": mo.ui.table(
                [{"ID": s.id, "Name": s.name, "Kind": kind,
                  "Vessel": s.vessel_id,
                  "Identifier": getattr(s, "inchikey", None) or
                                getattr(s, "ecnumber", None) or ""}
                 for kind, group in (("small molecule", doc.small_molecules),
                                     ("protein", doc.proteins))
                 for s in group],
                selection=None),
            "Reaction": mo.md(
                "\n".join(
                    f"**`{r.id}`** — {r.name}\n\n"
                    + "\n".join(f"- {role}: `{s.species_id}` × {s.stoichiometry:g}"
                                for role, group in (("reactant", r.reactants),
                                                    ("product", r.products))
                                for s in group)
                    + "".join(f"\n- modifier: `{m.species_id}` ({m.role.value})"
                              for m in r.modifiers)
                    for r in doc.reactions)
                or "*no reaction*"),
            "Measurements": mo.ui.table(
                [{"ID": m.id, "Name": m.name, "Series": m.group_id, "pH": m.ph,
                  "T [°C]": m.temperature,
                  "Points": sum(len(e.data) for e in m.species_data)}
                 for m in doc.measurements],
                selection=None),
            "Vessels": mo.ui.table(
                [{"ID": v.id, "Name": v.name, "Volume": v.volume,
                  "Unit": v.unit.name} for v in doc.vessels],
                selection=None),
        }),
    })
    return


@app.cell(hide_code=True)
def _(doc, json, mo):
    document = json.loads(doc.model_dump_json(exclude_none=True))
    payload = (json.dumps(document, indent=2, ensure_ascii=False) + "\n").encode()

    mo.vstack([
        mo.md(
            f"""
            ### The file

            **{len(payload):,} bytes** across
            {len([k for k, v in document.items() if v])} populated top-level
            fields. PyEnzyme attached JSON-LD identifiers to every entity
            along the way, so a vessel is not merely *called* a vessel but is
            typed as `OBO:OBI_0400081` — the document is linked data whether
            or not anybody asked for it.
            """
        ),
        mo.download(data=payload, filename="kinetics.json",
                    mimetype="application/json",
                    label=f"⬇ kinetics.json ({max(1, len(payload) // 1024)} KB)"),
    ])
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ---
    ### Next

    Download `kinetics.json` and take it to **[step 1](01_export_eln.py)**,
    which turns any such document into a lab notebook entry.

    The two steps are deliberately separate: step 1 does not care that this
    document came from PyEnzyme, and this notebook does not care that an ELN
    exists. A structured document is worth having either way.

    **The kinetic model comes later.** A rate law, its parameters and a fit
    are a session of their own; leaving them out here keeps the question
    *what did you measure* apart from the question *what do you think it
    means*. The document you just built answers the first one completely.
    """)
    return


if __name__ == "__main__":
    app.run()
