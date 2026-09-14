"""Phase 2 — the same machinery, against EnzymeML v2.

Nothing in `store.py`, `graph.py`, `layout.py` or `widget.py` changed to get
here. What this module adds is the two things that are genuinely
domain-specific:

`FIELDS`
    which properties each kind of entity has, and how to ask for them. Derived
    from pyenzyme's own models where it can be, spelled out where a workshop
    needs a shorter list than the schema allows.

`build_document`
    how the flat log nests into an `EnzymeMLDocument`.

It builds the *real* pyenzyme objects, not a lookalike. That is what makes the
JSON preview trustworthy: it is `model_dump_json` on the same class that
`notebooks/01_export_eln.py` will later read, so anything the participant sees
on screen is something the converter will accept.
"""

from __future__ import annotations

from typing import Any, Mapping

import pyenzyme as pe

from .store import Entity, FormField, Step, children_of, of_kind

#: Entity kinds that hold a species — used to offer the right `species_id`
#: choices, and to notice when a reaction names something nobody declared.
SPECIES_KINDS = ("Protein", "SmallMolecule")

#: A `UnitDefinition` is four `BaseUnit` objects saying *litre, exponent 1,
#: scale −3*. That is the right thing for the file to store and the wrong
#: thing to draw: `ml` says it, and the four extra nodes per vessel would
#: outnumber the chemistry.
INLINE = ("UnitDefinition", "BaseUnit")

#: Fields that end in `_id` and are not references into this document.
#: `559292` is a strain in NCBI's database, and `dilution_series_1` is a label
#: the participant invented — neither points at a node here.
NOT_REFERENCES = ("organism_tax_id", "group_id")


#: The forms, one entry per entity kind. `choices_from` may be "vessels",
#: "species", "reactions" or "measurements" — see `choices` below.
FIELDS: dict[str, tuple[FormField, ...]] = {
    "Document": (
        FormField("name", "Title", "text", "Untitled experiment",
                  placeholder="what you will search for in two years",
                  required=True),
        FormField("description", "Description", "area",
                  placeholder="What was measured, on what, and why?"),
        FormField("references", "References", "area",
                  placeholder="one DOI or URL per line",
                  hint="the method, the paper, the protocol"),
    ),
    "Creator": (
        FormField("given_name", "First name", "text", required=True),
        FormField("family_name", "Last name", "text", required=True),
        FormField("mail", "E-mail", "text",
                  placeholder="a placeholder — the demo is public!",
                  required=True),
    ),
    "Vessel": (
        FormField("id", "ID", "text", "v1", required=True,
                  hint="the handle every species will point at"),
        FormField("name", "Name", "text", "quartz cuvette, 1 cm", required=True),
        FormField("volume", "Volume", "number", 1.0, required=True),
        FormField("unit", "Unit", "select", "ml",
                  choices=("ml", "ul", "l", "nl")),
        FormField("constant", "Constant volume", "switch", True),
    ),
    "Protein": (
        FormField("id", "ID", "text", required=True),
        FormField("name", "Name", "text", required=True),
        FormField("ecnumber", "EC number", "text", placeholder="1.1.1.1",
                  hint="what it does — an identifier, not a name"),
        FormField("organism", "Organism", "text",
                  placeholder="Saccharomyces cerevisiae"),
        FormField("organism_tax_id", "NCBI taxonomy ID", "text",
                  placeholder="559292"),
        FormField("sequence", "Sequence", "area",
                  placeholder="MSIPETQKGVIFYESHGKLEYKDIPVPKPKANELLINVKYSGVCHTD…"),
        FormField("vessel_id", "In vessel", "select", choices_from="vessels",
                  needs="Vessel"),
        FormField("constant", "Held constant", "switch", True),
    ),
    "SmallMolecule": (
        FormField("id", "ID", "text", required=True),
        FormField("name", "Name", "text", required=True),
        FormField("inchikey", "InChIKey", "text",
                  placeholder="LFQSCWFLJHTTHZ-UHFFFAOYSA-N",
                  hint="the column that turns a name into an identity"),
        FormField("canonical_smiles", "SMILES", "text", placeholder="CCO"),
        FormField("vessel_id", "In vessel", "select", choices_from="vessels",
                  needs="Vessel"),
        FormField("constant", "Held constant", "switch", False),
    ),
    "Reaction": (
        FormField("id", "ID", "text", "r1", required=True,
                  hint="a Rhea id is a good one: RHEA:25290"),
        FormField("name", "Name", "text", required=True,
                  placeholder="ethanol oxidation"),
        FormField("reversible", "Reversible", "switch", True),
    ),
    "Participant": (
        FormField("reaction", "Reaction", "select", choices_from="reactions",
                  required=True, needs="Reaction"),
        FormField("species_id", "Species", "select", choices_from="species",
                  required=True, needs="Protein or SmallMolecule"),
        FormField("role", "Role", "select", "reactant",
                  choices=("reactant", "product", "biocatalyst", "catalyst",
                           "inhibitor", "activator", "buffer", "solvent",
                           "additive")),
        FormField("stoichiometry", "Stoichiometry", "number", 1.0),
    ),
    "Measurement": (
        FormField("id", "ID", "text", required=True),
        FormField("name", "Name", "text", required=True),
        FormField("group_id", "Series", "text",
                  placeholder="dilution_series_1",
                  hint="the same string in every run that belongs together"),
        FormField("ph", "pH", "number"),
        FormField("temperature", "Temperature", "number"),
        FormField("temperature_unit", "Temperature unit", "select", "°C",
                  choices=("°C", "K")),
    ),
    "SpeciesData": (
        FormField("measurement", "Measurement", "select",
                  choices_from="measurements", required=True,
                  needs="Measurement"),
        FormField("species_id", "Species", "select", choices_from="species",
                  required=True, needs="Protein or SmallMolecule"),
        FormField("initial", "Initial value", "number"),
        FormField("data_unit", "Data unit", "text", "mmol / l"),
        FormField("time_unit", "Time unit", "text", "min"),
        FormField("data_type", "What was measured", "select", "concentration",
                  choices=("concentration", "absorbance", "amount",
                           "conversion", "fluorescence", "peakarea",
                           "transmittance", "turnover", "yield")),
    ),
}

#: The order the workshop walks through, and why each step comes when it does.
STEPS: tuple[tuple[str, str, str], ...] = (
    ("Document", "The document",
     "One object to hang everything else on. It starts almost empty — a title "
     "and nothing else — and that is already more than a CSV file carries."),
    ("Vessel", "The vessel",
     "Where the experiment happened. Every species will point at it, which is "
     "the first reference edge you will see."),
    ("Protein", "Proteins",
     "The enzyme. Give it an EC number and a taxonomy ID and it stops being a "
     "name in your lab's dialect."),
    ("SmallMolecule", "Small molecules",
     "Substrates, products, cofactors, buffer. Add a second one and watch two "
     "separate nodes appear — the model does not merge them because they are "
     "the same *kind* of thing."),
    ("Reaction", "The reaction",
     "What happened. On its own it is an empty box; the participants below "
     "are what give it meaning."),
    ("Participant", "Reaction participants",
     "The link no database can give you: that *this* protein catalyses "
     "*this* reaction. Every row here is a dashed edge into a species you "
     "already declared."),
    ("Measurement", "Measurements",
     "One run, with the conditions it ran under. pH and temperature are not "
     "in the CSV either."),
    ("SpeciesData", "The numbers",
     "Finally the data — bound to a species, in a unit, against a time axis. "
     "This is the only step that adds numbers; everything before it was the "
     "reason the numbers mean anything."),
    ("Creator", "Who measured it",
     "The last thing the numbers cannot say, and the first thing anyone "
     "looking for them will search on."),
)


#: Class name to pyenzyme class, so the inspector can answer "what else fits
#: in here?" from the schema rather than from a hand-written list.
MODELS = {
    m.__name__: m
    for m in (
        pe.EnzymeMLDocument, pe.Creator, pe.Vessel, pe.Protein,
        pe.SmallMolecule, pe.Complex, pe.Reaction, pe.ReactionElement,
        pe.ModifierElement, pe.Measurement, pe.MeasurementData,
        pe.Equation, pe.Parameter,
    )
}


def graph_of(document: pe.EnzymeMLDocument, **options: Any):
    """`build_graph` with the EnzymeML-specific settings already applied."""
    from .graph import build_graph

    return build_graph(
        document, inline=INLINE, not_references=NOT_REFERENCES, **options
    )


#: Kinds there is exactly one of, mapped to the key they always live under.
#: The document is not something you add a second of — you edit the one you
#: have — so its tab submits an `update` step rather than an `add`.
SINGLETONS = {"Document": "doc"}

#: Kinds whose objects carry their own `id`, and therefore get a node id of the
#: form `Protein:alcohol_dehydrogenase_1`. Knowing that is what lets a click on
#: the graph find its way back to the entity in the log.
IDENTIFIED = ("Vessel", "Protein", "SmallMolecule", "Reaction", "Measurement")


def node_keys(entities: Mapping[str, Entity]) -> dict[str, str]:
    """Graph node id → the key of the entity behind it.

    The graph is built from the pydantic document, which has never heard of the
    log; this is the one place the two are tied back together, and it is a
    lookup rather than a stored link so it cannot go stale.

    Only entities with an identifier of their own appear. A reaction
    participant's node id is `Reaction:r1/reactants[0]` — a position, not a
    name — and positions shift as the document is edited, so they are not
    offered for editing.
    """
    out: dict[str, str] = {}
    document = next(iter(of_kind(entities, "Document")), None)
    if document is not None:
        out["EnzymeMLDocument"] = document.key
    for kind in IDENTIFIED:
        for entity in of_kind(entities, kind):
            out[f"{kind}:{entity.text('id', entity.key)}"] = entity.key
    return out


def choices(entities: Mapping[str, Entity], source: str) -> list[str]:
    """The identifiers a `choices_from` field may point at."""
    if source == "vessels":
        return [e.text("id", e.key) for e in of_kind(entities, "Vessel")]
    if source == "species":
        return [e.text("id", e.key) for e in of_kind(entities, *SPECIES_KINDS)]
    if source == "reactions":
        return [e.key for e in of_kind(entities, "Reaction")]
    if source == "measurements":
        return [e.key for e in of_kind(entities, "Measurement")]
    return []


def label_for(entities: Mapping[str, Entity], key: str) -> str:
    """How a foreign key reads in a dropdown: the name, not the handle."""
    entity = entities.get(key)
    if entity is None:
        return key
    return entity.text("name") or entity.text("id", key)


def build_document(
    entities: Mapping[str, Entity],
) -> tuple[pe.EnzymeMLDocument, list[str]]:
    """Fold the log into a real `EnzymeMLDocument`, and say what went wrong.

    Tolerant on purpose. A half-filled form is the normal state of this
    notebook, not an error, and a participant who has typed a vessel's name but
    not yet its volume should still see the vessel node appear. What cannot be
    built is reported rather than raised, so one bad unit string never takes
    the whole page down.
    """
    problems: list[str] = []
    meta = next(iter(of_kind(entities, "Document")), None)

    document = pe.EnzymeMLDocument(
        name=(meta.text("name", "Untitled experiment") if meta
              else "Untitled experiment"),
        description=(meta.text("description") or None) if meta else None,
        references=(
            [line.strip() for line in meta.text("references").splitlines()
             if line.strip()]
            if meta else []
        ),
    )

    for entity in of_kind(entities, "Creator"):
        document.creators.append(
            pe.Creator(
                given_name=entity.text("given_name"),
                family_name=entity.text("family_name"),
                mail=entity.text("mail"),
            )
        )

    for entity in of_kind(entities, "Vessel"):
        try:
            document.vessels.append(
                pe.Vessel(
                    id=entity.text("id", entity.key),
                    name=entity.text("name", entity.key),
                    volume=entity.number("volume", 0.0) or 0.0,
                    unit=entity.text("unit", "l"),
                    constant=entity.flag("constant", True),
                )
            )
        except Exception as exc:  # an unparseable unit, almost always
            problems.append(f"Vessel `{entity.text('id', entity.key)}`: {exc}")

    for entity in of_kind(entities, "Protein"):
        document.proteins.append(
            pe.Protein(
                id=entity.text("id", entity.key),
                name=entity.text("name", entity.key),
                sequence=entity.text("sequence") or None,
                ecnumber=entity.text("ecnumber") or None,
                organism=entity.text("organism") or None,
                organism_tax_id=entity.text("organism_tax_id") or None,
                vessel_id=entity.text("vessel_id") or None,
                constant=entity.flag("constant", True),
            )
        )

    for entity in of_kind(entities, "SmallMolecule"):
        document.small_molecules.append(
            pe.SmallMolecule(
                id=entity.text("id", entity.key),
                name=entity.text("name", entity.key),
                inchikey=entity.text("inchikey") or None,
                canonical_smiles=entity.text("canonical_smiles") or None,
                vessel_id=entity.text("vessel_id") or None,
                constant=entity.flag("constant", False),
            )
        )

    known_species = {s.id for s in document.small_molecules + document.proteins}
    roles = {role.value for role in pe.ModifierRole}

    for entity in of_kind(entities, "Reaction"):
        reaction = pe.Reaction(
            id=entity.text("id", entity.key),
            name=entity.text("name", entity.key),
            reversible=entity.flag("reversible", True),
        )
        for part in children_of(entities, entity.key, via="reaction",
                                kind="Participant"):
            species = part.text("species_id")
            role = part.text("role", "reactant").lower()
            stoichiometry = part.number("stoichiometry", 1.0) or 1.0
            if not species:
                continue
            if species not in known_species:
                problems.append(
                    f"Reaction `{reaction.id}` names `{species}`, which is not "
                    "declared as a protein or small molecule."
                )
            if role == "reactant":
                reaction.add_to_reactants(species_id=species,
                                          stoichiometry=stoichiometry)
            elif role == "product":
                reaction.add_to_products(species_id=species,
                                         stoichiometry=stoichiometry)
            elif role in roles:
                reaction.add_to_modifiers(species_id=species,
                                          role=pe.ModifierRole(role))
            else:
                problems.append(f"Unknown role `{role}` — row skipped.")
        document.reactions.append(reaction)

    for entity in of_kind(entities, "Measurement"):
        temperature = entity.number("temperature")
        measurement = pe.Measurement(
            id=entity.text("id", entity.key),
            name=entity.text("name", entity.key),
            group_id=entity.text("group_id") or None,
            ph=entity.number("ph"),
            temperature=temperature,
            temperature_unit=(entity.text("temperature_unit", "°C")
                              if temperature is not None else None),
        )
        for series in children_of(entities, entity.key, via="measurement",
                                  kind="SpeciesData"):
            species = series.text("species_id")
            if not species:
                continue
            times = _floats(series.props.get("time"))
            values = _floats(series.props.get("data"))
            if len(times) != len(values):
                problems.append(
                    f"`{measurement.id}` / `{species}`: {len(times)} time "
                    f"points against {len(values)} values."
                )
                times, values = [], []
            try:
                measurement.add_to_species_data(
                    species_id=species,
                    initial=series.number("initial"),
                    prepared=series.number("initial"),
                    data_unit=series.text("data_unit", "mmol / l"),
                    time_unit=series.text("time_unit", "min"),
                    data_type=pe.DataTypes(series.text("data_type",
                                                       "concentration")),
                    is_simulated=False,
                    time=times,
                    data=values,
                )
            except Exception as exc:
                problems.append(f"`{measurement.id}` / `{species}`: {exc}")
        document.measurements.append(measurement)

    return document, problems


def _floats(value: Any) -> list[float]:
    """Whatever the form put in the props, as a list of numbers.

    Accepts a real list (from a CSV upload) or free text (from a textarea),
    because both are how a participant might supply eleven numbers.
    """
    if value in (None, ""):
        return []
    if isinstance(value, (list, tuple)):
        items: list[Any] = list(value)
    else:
        items = str(value).replace(",", " ").replace(";", " ").split()
    out: list[float] = []
    for item in items:
        try:
            out.append(float(item))
        except (TypeError, ValueError):
            continue
    return out


def starter_log() -> list[Step]:
    """A worked example, as a log — the same ADH experiment as notebook 0.

    Loading it is not cheating: stepping through somebody else's twelve edits
    with the slider is the fastest way to see what the graph is *for*, and the
    participant then clears it and does their own.
    """
    return [
        Step("add", "Document", "doc",
             {"name": "ADH kinetics: ethanol oxidation",
              "description": "Yeast alcohol dehydrogenase oxidising ethanol, "
                             "followed by NADH absorbance at 340 nm."},
             "Document **ADH kinetics** created"),
        Step("add", "Vessel", "vessel_1",
             {"id": "v1", "name": "quartz cuvette, 1 cm", "volume": 1.0,
              "unit": "ml", "constant": True},
             "Vessel **v1** added"),
        Step("add", "Protein", "protein_1",
             {"id": "alcohol_dehydrogenase_1", "name": "Alcohol dehydrogenase 1",
              "ecnumber": "1.1.1.1", "organism": "Saccharomyces cerevisiae",
              "organism_tax_id": "559292", "vessel_id": "v1", "constant": True},
             "Protein **Alcohol dehydrogenase 1** added"),
        Step("add", "SmallMolecule", "smallmolecule_1",
             {"id": "ethanol", "name": "ethanol",
              "inchikey": "LFQSCWFLJHTTHZ-UHFFFAOYSA-N",
              "canonical_smiles": "CCO", "vessel_id": "v1", "constant": False},
             "Small molecule **ethanol** added"),
        Step("add", "SmallMolecule", "smallmolecule_2",
             {"id": "nad_1", "name": "NAD(1-)",
              "inchikey": "BAWFJGJZGIEFAR-NNYOXOHSSA-M",
              "vessel_id": "v1", "constant": False},
             "Small molecule **NAD(1-)** added"),
        Step("add", "SmallMolecule", "smallmolecule_3",
             {"id": "acetaldehyde", "name": "acetaldehyde",
              "inchikey": "IKHGUXGNUITLKF-UHFFFAOYSA-N",
              "vessel_id": "v1", "constant": False},
             "Small molecule **acetaldehyde** added"),
        Step("add", "SmallMolecule", "smallmolecule_4",
             {"id": "nadh_2", "name": "NADH(2-)",
              "inchikey": "BOPGDPNILDQYTO-NNYOXOHSSA-L",
              "vessel_id": "v1", "constant": False},
             "Small molecule **NADH(2-)** added"),
        Step("add", "Reaction", "reaction_1",
             {"id": "RHEA:25290", "name": "ethanol oxidation",
              "reversible": True},
             "Reaction **ethanol oxidation** added"),
        Step("add", "Participant", "participant_1",
             {"reaction": "reaction_1", "species_id": "ethanol",
              "role": "reactant", "stoichiometry": 1.0},
             "ethanol is a **reactant**"),
        Step("add", "Participant", "participant_2",
             {"reaction": "reaction_1", "species_id": "nad_1",
              "role": "reactant", "stoichiometry": 1.0},
             "NAD(1-) is a **reactant**"),
        Step("add", "Participant", "participant_3",
             {"reaction": "reaction_1", "species_id": "acetaldehyde",
              "role": "product", "stoichiometry": 1.0},
             "acetaldehyde is a **product**"),
        Step("add", "Participant", "participant_4",
             {"reaction": "reaction_1", "species_id": "nadh_2",
              "role": "product", "stoichiometry": 1.0},
             "NADH(2-) is a **product**"),
        Step("add", "Participant", "participant_5",
             {"reaction": "reaction_1",
              "species_id": "alcohol_dehydrogenase_1",
              "role": "biocatalyst", "stoichiometry": 1.0},
             "ADH is the **biocatalyst** — the one link no database gave you"),
        Step("add", "Measurement", "measurement_1",
             {"id": "ethanol_2mM", "name": "Ethanol 2 mM",
              "group_id": "dilution_series_1", "ph": 8.8, "temperature": 25.0,
              "temperature_unit": "°C"},
             "Measurement **Ethanol 2 mM** added"),
        Step("add", "SpeciesData", "speciesdata_1",
             {"measurement": "measurement_1", "species_id": "ethanol",
              "initial": 2.0, "data_unit": "mmol / l", "time_unit": "min",
              "data_type": "concentration",
              "time": [0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20],
              "data": [2.0, 1.73, 1.5, 1.3, 1.12, 0.97, 0.84, 0.73,
                       0.63, 0.54, 0.47]},
             "11 data points bound to **ethanol**"),
        Step("add", "Creator", "creator_1",
             {"given_name": "Ada", "family_name": "Lovelace",
              "mail": "ada@example.org"},
             "Creator **Ada Lovelace** added"),
    ]
