#!/usr/bin/env python3
"""Put a few contrasting documents into an eLabFTW instance, so that
comparing entries is worth doing.

Notebook 2's best moment is the species matrix: several documents side by side,
one row per species, and the rows line up because the identifiers came from a
registry rather than from each experimenter's habits. On a fresh demo instance
that moment falls flat — every participant imported the same workshop dataset,
so the matrix is one column of ticks and the two-document diff says
"identical".

This script fixes that by seeding three experiments that genuinely differ:

    A  yeast ADH,        ethanol   + NAD+ -> acetaldehyde + NADH,  pH 8.8
    B  horse liver ADH,  ethanol   + NAD+ -> acetaldehyde + NADH,  pH 7.5
    C  human LDH-A,      L-lactate + NAD+ -> pyruvate     + NADH,  pH 9.0

A and B share all four small molecules and differ in organism; C shares only
the cofactors. So the matrix has shared rows, half-shared rows and unique rows
— which is what makes it teach something. The identifiers are not typed here:
the reactions come from Rhea and the enzymes from UniProt, which is also why
NAD+ arrives with the same id and the same InChIKey in all three documents.
That is the point being demonstrated, so it would be dishonest to fake it.

Usage — nothing is sent without ``--commit``::

    # look at what would be built, write the documents to disk
    python seed_demo.py --out examples/seed

    # dry run against an instance: builds, plans, sends nothing
    python seed_demo.py --url https://demo.elabftw.net --key $ELAB_KEY

    # actually create the three entries
    python seed_demo.py --url https://demo.elabftw.net --key $ELAB_KEY --commit

The measured values are simulated from Michaelis-Menten kinetics with a fixed
random seed. They are labelled as synthetic in every document's description,
and they are reproducible: two runs of this script produce identical numbers.

Run it **before** the workshop, not during — it fetches from Rhea, ChEBI and
UniProt, and those lookups are the slow part.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Optional

# Registry lookups and the document model both come from pyenzyme. Imported
# lazily inside build() so that --help works without the dev group installed.


# --- what to build -----------------------------------------------------------

#: One dict per document. Everything a recipe does not name is shared: the
#: vessel, the units, the time grid, the fact that NADH is what the photometer
#: actually sees at 340 nm.
RECIPES: list[dict[str, Any]] = [
    {
        "key": "adh_yeast",
        "name": "ADH kinetics: ethanol oxidation by yeast ADH1",
        "rhea": "RHEA:25290",
        "uniprot": "P00330",
        "substrate": "ethanol",
        "product": "acetaldehyde",
        "ph": 8.8,
        "temperature": 25.0,
        "group_id": "dilution_series_adh_yeast",
        # k_cat [1/min], K_m [mmol/l], enzyme [mmol/l]
        "k_cat": 14.0, "k_m": 17.0, "enzyme": 0.0005,
        "initials": [2.0, 8.0, 18.0],
        "day": 0,
    },
    {
        "key": "adh_horse",
        "name": "ADH kinetics: ethanol oxidation by horse liver ADH",
        "rhea": "RHEA:25290",
        "uniprot": "P00327",
        "substrate": "ethanol",
        "product": "acetaldehyde",
        "ph": 7.5,
        "temperature": 25.0,
        "group_id": "dilution_series_adh_horse",
        "k_cat": 8.5, "k_m": 1.1, "enzyme": 0.0005,
        "initials": [1.0, 4.0, 12.0],
        "day": 7,
    },
    {
        "key": "ldh_human",
        "name": "LDH kinetics: lactate oxidation by human LDH-A",
        "rhea": "RHEA:23444",
        "uniprot": "P00338",
        "substrate": "(S)-lactate",
        "product": "pyruvate",
        "ph": 9.0,
        "temperature": 25.0,
        "group_id": "dilution_series_ldh_human",
        "k_cat": 22.0, "k_m": 4.4, "enzyme": 0.0003,
        "initials": [1.0, 5.0, 15.0],
        "day": 21,
    },
]

#: Shared across all three, so that differences between documents are the ones
#: the recipes declare and not accidents of the vessel or the time grid.
COFACTOR_INITIAL = 20.0          # mmol/l NAD+, in excess
TIME_POINTS = [0.0, 1.0, 2.0, 4.0, 6.0, 8.0, 10.0, 12.0, 15.0, 18.0, 20.0]
DATA_UNIT = "mmol / l"
TIME_UNIT = "min"
NOISE = 0.015                    # relative, on the followed species
SEED = 20260909

DESCRIPTION = (
    "{headline} Formation of NADH followed photometrically at 340 nm; the "
    "decrease of {substrate} derived from it. Three starting concentrations "
    "around K_m, {points} time points each over {span:g} min.\n\n"
    "Synthetic teaching dataset: the numbers come from a Michaelis-Menten "
    "simulation with added noise, not from a bench. The chemical and "
    "biological identifiers are real — the reaction from Rhea {rhea}, the "
    "enzyme from UniProt {uniprot}."
)


# --- the simulation ----------------------------------------------------------

def simulate(initial: float, k_cat: float, k_m: float, enzyme: float,
             times: list[float], rng: random.Random) -> tuple[list[float], list[float]]:
    """Substrate and product over time, Michaelis-Menten, plus a little noise.

    Integrated with small fixed steps rather than solved: the closed form needs
    a Lambert W, and nothing here is worth that. The step is small enough that
    halving it moves no reported digit.
    """
    v_max = k_cat * enzyme
    step = 0.001
    substrate = initial
    out_s, out_p = [], []
    clock = 0.0
    for target in times:
        while clock < target - step / 2:
            substrate = max(0.0, substrate - step * v_max * substrate / (k_m + substrate))
            clock += step
        # Noise on what was read off the instrument, not on what was pipetted.
        jitter = 0.0 if target == 0.0 else rng.gauss(0.0, NOISE)
        product = initial - substrate
        out_s.append(round(max(0.0, substrate * (1 + jitter)), 4))
        out_p.append(round(max(0.0, product * (1 + jitter)), 4))
    return out_s, out_p


# --- building one document ---------------------------------------------------

def build(recipe: dict, *, creator: tuple[str, str, str],
          suffix: str = "") -> dict:
    """One EnzymeML v2 document, as a plain dict.

    The species and the enzyme are fetched, not typed. That costs a network
    round trip per document and buys the property the whole comparison rests
    on: two documents that use NAD+ carry the *same* NAD+.
    """
    import pyenzyme as pe

    rng = random.Random(f"{SEED}:{recipe['key']}")

    vessel = pe.Vessel(id="v_cuvette", name="Quartz cuvette 1 cm",
                       volume=1.0, unit="ml", constant=True)
    reaction, molecules = pe.fetch_rhea(recipe["rhea"], vessel_id=vessel.id)
    protein = pe.fetch_uniprot(recipe["uniprot"], vessel_id=vessel.id)

    reaction.name = f"{recipe['substrate']} oxidation"
    reaction.add_to_modifiers(species_id=protein.id,
                              role=pe.ModifierRole.CATALYST)

    by_name = {m.name: m for m in molecules}
    substrate = by_name[recipe["substrate"]]
    product = by_name[recipe["product"]]
    cofactors = [m for m in molecules if m is not substrate and m is not product]

    measurements = []
    for index, initial in enumerate(recipe["initials"]):
        series_s, series_p = simulate(initial, recipe["k_cat"], recipe["k_m"],
                                      recipe["enzyme"], TIME_POINTS, rng)
        measurement = pe.Measurement(
            id=f"m{index}",
            name=f"{substrate.name} {initial:g} mM",
            group_id=recipe["group_id"],
            ph=recipe["ph"],
            temperature=recipe["temperature"],
            temperature_unit="°C",
        )
        for species, series in ((substrate, series_s), (product, series_p)):
            measurement.add_to_species_data(
                species_id=species.id, initial=series[0], prepared=series[0],
                data=series, time=list(TIME_POINTS),
                data_unit=DATA_UNIT, time_unit=TIME_UNIT,
                data_type=pe.DataTypes.CONCENTRATION, is_simulated=False)
        # In the vessel, followed by nothing: still part of the experiment.
        for species in cofactors + [protein]:
            measurement.add_to_species_data(
                species_id=species.id,
                initial=COFACTOR_INITIAL if species is not protein
                else recipe["enzyme"],
                prepared=COFACTOR_INITIAL if species is not protein
                else recipe["enzyme"],
                data_unit=DATA_UNIT, time_unit=TIME_UNIT,
                data_type=pe.DataTypes.CONCENTRATION, is_simulated=False,
                data=[], time=[])
        measurements.append(measurement)

    given, family, mail = creator
    document = pe.EnzymeMLDocument(
        name=recipe["name"] + (f" {suffix}" if suffix else ""),
        description=DESCRIPTION.format(
            headline=f"{protein.name} from {protein.organism} converts "
                     f"{substrate.name} to {product.name}.",
            substrate=substrate.name, points=len(TIME_POINTS),
            span=TIME_POINTS[-1], rhea=recipe["rhea"],
            uniprot=recipe["uniprot"]),
        references=[f"https://www.rhea-db.org/rhea/{recipe['rhea'].split(':')[-1]}",
                    f"https://www.uniprot.org/uniprotkb/{recipe['uniprot']}"],
        vessels=[vessel],
        small_molecules=list(molecules),
        proteins=[protein],
        reactions=[reaction],
        measurements=measurements,
        creators=[pe.Creator(given_name=given, family_name=family, mail=mail)],
    )
    return json.loads(document.model_dump_json(exclude_none=True))


# --- putting it into an instance ---------------------------------------------

def create_experiment(session, *, when: str) -> int:
    """POST an empty experiment, date it, return its id.

    eLabFTW answers a creation with 201 and a ``Location`` header rather than a
    body, so the id has to be read off the header. ``date`` is patched
    separately because it is not part of the creation payload — and it is sent
    as a *string*: ``EntityParams`` maps it through ``getUnfilteredContent()``,
    the same unfiltered path as ``metadata``, and leaves the validation to
    MySQL.
    """
    from eln.remote import _api, _call

    api = _api()
    experiments = api.ExperimentsApi(session.client)
    response = _call(session, experiments.post_experiment, body={},
                     _preload_content=False)

    location = (response.getheader("Location") if hasattr(response, "getheader")
                else dict(response.headers).get("Location", ""))
    try:
        experiment_id = int(str(location).rstrip("/").rsplit("/", 1)[-1])
    except (ValueError, AttributeError):
        raise SystemExit(
            f"Could not read the new experiment's id from Location: {location!r}")

    _call(session, experiments.patch_experiment, {"date": when}, experiment_id)
    return experiment_id


def push(session, document: dict, *, when: str, commit: bool) -> tuple[Optional[int], str]:
    """Create one entry and fill it, or say what that would take."""
    from eln import remote_write

    if not commit:
        # Nothing exists to prepare against, so report the shape instead of
        # inventing an id. The entry contents are checked offline anyway.
        from eln import convert_document
        _, entries, _ = convert_document(document)
        entry = entries[0]
        return None, (f"would POST /experiments, PATCH date={when}, then write "
                      f"{len(entry.fields)} extra fields and "
                      f"{len(entry.attachments)} attachment(s)")

    experiment_id = create_experiment(session, when=when)
    plan = remote_write.prepare(session, experiment_id, document)
    remote_write.apply(session, plan)
    return experiment_id, (f"created /experiments/{experiment_id} dated {when} "
                           f"with {len(plan.metadata.get('extra_fields') or {})} "
                           f"extra fields and {len(plan.attachments)} attachment(s)")


# --- CLI ---------------------------------------------------------------------

def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Seed an eLabFTW instance with contrasting documents, so "
                    "that comparing entries in notebook 2 shows something.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Nothing is sent unless --commit is given.")
    parser.add_argument("--out", metavar="DIR", type=Path,
                        help="also write each document as JSON into DIR")
    parser.add_argument("--url", help="eLabFTW instance, e.g. demo.elabftw.net")
    parser.add_argument("--key", help="API key with write permission")
    parser.add_argument("--commit", action="store_true",
                        help="actually create the entries (default: dry run)")
    parser.add_argument("--suffix", default="",
                        help="appended to every title — on a shared instance, "
                             "use your initials")
    parser.add_argument("--creator", default="Workshop Example/example@invalid",
                        metavar="GIVEN FAMILY/MAIL",
                        help="creator recorded in the documents. The default "
                             "is a placeholder on purpose: the demo instance "
                             "is public")
    parser.add_argument("--start", metavar="YYYY-MM-DD", default="",
                        help="date of the first document (default: 28 days "
                             "ago, so the others land in the past too)")
    args = parser.parse_args(argv)

    who, _, mail = args.creator.partition("/")
    given, _, family = who.strip().partition(" ")
    creator = (given, family, mail or "example@invalid")

    start = (date.fromisoformat(args.start) if args.start
             else date.today() - timedelta(days=28))

    session = None
    if args.url:
        from eln.remote import RemoteError, connect
        if not args.key:
            parser.error("--url needs --key")
        try:
            session = connect(args.url, args.key)
        except RemoteError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        print(f"connected to {session.url} as {session.whoami}\n")
    elif args.commit:
        parser.error("--commit needs --url and --key")

    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)

    documents = []
    for recipe in RECIPES:
        print(f"building {recipe['key']} …", end=" ", flush=True)
        try:
            document = build(recipe, creator=creator, suffix=args.suffix)
        except Exception as exc:
            print(f"\nerror: {recipe['key']} could not be built: {exc}\n"
                  "  The registries are fetched over the network — if Rhea, "
                  "ChEBI or UniProt is unreachable, so is this script.",
                  file=sys.stderr)
            return 1
        when = (start + timedelta(days=recipe["day"])).isoformat()
        documents.append((recipe, document, when))
        print(f"{len(document.get('small_molecules') or [])} molecules, "
              f"{len(document.get('measurements') or [])} measurements, "
              f"dated {when}")

        if args.out:
            path = args.out / f"{recipe['key']}.json"
            path.write_text(json.dumps(document, indent=2, ensure_ascii=False),
                            encoding="utf-8")
            print(f"    wrote {path}")

    print()
    for recipe, document, when in documents:
        _, line = push(session, document, when=when, commit=args.commit)
        print(f"{recipe['key']:12} {line}")

    if not args.commit:
        print("\n(dry run — nothing was sent. Add --commit to create them.)")

    print("\nQueries that will find these once they are in:")
    print('  extrafield:"EC number":1.1.1.1          the two ADH documents')
    print('  extrafield:"Organism":"Homo sapiens"    the LDH document')
    for _, _, when in documents[:1]:
        last = documents[-1][2]
        print(f"  date:{when}..{last}          all three")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
