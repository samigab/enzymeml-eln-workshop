"""EnzymeML v2 (enzymeML.xsd) → ELN RO-Crate.

Strictly the v2 model as defined by ``enzymeML.xsd``: ``small_molecules``,
list-valued ``creators``, ``species_data`` inside measurements. EnzymeML v1
documents (``reactants``, dict-valued ``creators``, ``level``) are rejected with
an explicit message rather than silently producing empty entries — see
:func:`validate`.

Grain ``document`` (default): the whole EnzymeMLDocument becomes one entry.
A dilution series is one experiment, and splitting it per measurement both
triplicates the shared metadata and misattributes the fitted parameters —
``K_m`` is determined *across* the measurements, so writing it into each one
claims three determinations where there was one.

Grain ``measurement``: one entry per ``Measurement``. The right choice when the
document is an aggregate — runs from different sessions, people or conditions
that merely share a file.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from .crate import (CONDITIONS, IDENTITY, MEASUREMENT, MODEL, PROVENANCE,
                    SYSTEM, Attachment, Entry, Fields, Person, Resource,
                    esc, fmt, inline_image, resource_ref, slug)
from .read import merge_documents
from .util import csv_bytes, plot_png, unit_label

SCHEMA = "enzymeml"
PUBLISHER = ("EnzymeML ELN converter", "https://enzymeml.org")

# document keys that only exist in the v1 model
_V1_ONLY = ("reactants", "level", "pubmedid")


def detect(doc: dict) -> bool:
    return "measurements" in doc and ("small_molecules" in doc
                                      or "proteins" in doc or "reactions" in doc)


def validate(doc: dict) -> None:
    """Raise ValueError if this is not an EnzymeML v2 document."""
    problems = [k for k in _V1_ONLY if k in doc]
    if isinstance(doc.get("creators"), dict):
        problems.append("creators (object instead of list)")
    if "small_molecules" not in doc and "reactants" in doc:
        problems.append("small_molecules (missing; found v1 'reactants')")
    if problems:
        raise ValueError(
            "This looks like an EnzymeML v1 document, but this converter targets "
            "EnzymeML v2 as defined by enzymeML.xsd.\n"
            f"  v1 markers found: {', '.join(sorted(set(problems)))}\n"
            "  Convert it first, e.g. with pyenzyme v2, then re-run."
        )


# ---------------------------------------------------------------------------
# document indexing
# ---------------------------------------------------------------------------

class Index:
    """Resolve species/vessels by their document-local IDs."""

    def __init__(self, doc: dict):
        self.doc = doc
        self.vessels = {v.get("id"): v for v in doc.get("vessels") or []}
        self.proteins = {p.get("id"): p for p in doc.get("proteins") or []}
        self.complexes = {c.get("id"): c for c in doc.get("complexes") or []}
        self.small_molecules = {s.get("id"): s for s in doc.get("small_molecules") or []}
        self.species = {**self.small_molecules, **self.proteins, **self.complexes}

    def name(self, sid: Optional[str]) -> str:
        return (self.species.get(sid) or {}).get("name") or str(sid or "?")

    def kind(self, sid: Optional[str]) -> str:
        if sid in self.proteins:
            return "Protein"
        if sid in self.complexes:
            return "Complex"
        if sid in self.small_molecules:
            return "SmallMolecule"
        return "Species"


def _creators(doc: dict) -> list[Person]:
    return [Person(given_name=c.get("given_name"), family_name=c.get("family_name"),
                   email=c.get("mail"))
            for c in doc.get("creators") or []]


def _reaction_equation(reaction: dict, idx: Index) -> str:
    def side(elements: list[dict]) -> str:
        parts = []
        for e in elements or []:
            stoich = e.get("stoichiometry")
            prefix = "" if stoich in (None, 1, 1.0) else f"{stoich:g} "
            parts.append(f"{prefix}{idx.name(e.get('species_id'))}")
        return " + ".join(parts) or "∅"

    arrow = "⇌" if reaction.get("reversible") else "→"
    eq = f"{side(reaction.get('reactants'))} {arrow} {side(reaction.get('products'))}"
    mods = [f"{idx.name(m.get('species_id'))}"
            + (f" ({m['role']})" if m.get("role") else "")
            for m in reaction.get("modifiers") or []]
    return eq + (f"  [{', '.join(mods)}]" if mods else "")


# ---------------------------------------------------------------------------
# per-measurement extraction
# ---------------------------------------------------------------------------

class _MeasurementView:
    def __init__(self, meas: dict, idx: Index, i: int):
        self.m = meas
        self.idx = idx
        self.id = str(meas.get("id") or f"measurement_{i + 1}")
        self.name = meas.get("name") or self.id
        self.species_data = meas.get("species_data") or []

    def species_ids(self) -> list[str]:
        return [sd.get("species_id") for sd in self.species_data]

    def vessel_ids(self) -> list[str]:
        out = []
        for sid in self.species_ids():
            vid = (self.idx.species.get(sid) or {}).get("vessel_id")
            if vid and vid not in out:
                out.append(vid)
        return out

    def n_points(self) -> int:
        return max((len(sd.get("data") or []) for sd in self.species_data), default=0)

    def time_unit(self) -> str:
        for sd in self.species_data:
            u = unit_label(sd.get("time_unit"))
            if u:
                return u
        return ""

    def data_types(self) -> list[str]:
        return sorted({sd.get("data_type") for sd in self.species_data if sd.get("data_type")})

    def shared_time(self) -> Optional[list[float]]:
        """The common time grid, or None if the species disagree."""
        times = [tuple(sd.get("time") or []) for sd in self.species_data
                 if sd.get("data")]
        if not times or len(set(times)) != 1 or not times[0]:
            return None
        return list(times[0])

    # -- flat table --------------------------------------------------------
    def table(self) -> tuple[list[str], list[list[Any]]]:
        """Wide format when all species share one time grid, else long format."""
        grid = self.shared_time()
        if grid is not None:
            header = [f"time [{self.time_unit()}]" if self.time_unit() else "time"]
            cols = []
            for sd in self.species_data:
                if not sd.get("data"):
                    continue
                u = unit_label(sd.get("data_unit"))
                header.append(f"{self.idx.name(sd.get('species_id'))}{f' [{u}]' if u else ''}")
                cols.append(sd["data"])
            rows = [[grid[i], *(c[i] if i < len(c) else None for c in cols)]
                    for i in range(len(grid))]
            return header, rows

        header = ["species_id", "species", "time", "time_unit", "value", "unit",
                  "data_type", "is_simulated"]
        rows = []
        for sd in self.species_data:
            sid = sd.get("species_id")
            tu, du = unit_label(sd.get("time_unit")), unit_label(sd.get("data_unit"))
            times, data = sd.get("time") or [], sd.get("data") or []
            for t, v in zip(times, data):
                rows.append([sid, self.idx.name(sid), t, tu, v, du,
                             sd.get("data_type"), sd.get("is_simulated")])
        return header, rows


def _fields(doc: dict, view: _MeasurementView) -> list[dict]:
    f = Fields()
    idx, m = view.idx, view.m

    # --- Measurement ------------------------------------------------------
    f.text("Measurement ID", view.id, MEASUREMENT)
    f.text("Group ID", m.get("group_id"), MEASUREMENT,
           description="signals relationships between measurements")
    f.number("Number of species", len(view.species_data), MEASUREMENT)
    f.number("Number of time points", view.n_points(), MEASUREMENT)
    if view.time_unit():
        f.text("Time unit", view.time_unit(), MEASUREMENT)
    if view.data_types():
        f.text("Data type", ", ".join(view.data_types()), MEASUREMENT)
    simulated = [sd for sd in view.species_data if sd.get("is_simulated")]
    if simulated:
        f.text("Simulated species", ", ".join(idx.name(sd.get("species_id"))
                                              for sd in simulated), MEASUREMENT)

    # --- Conditions -------------------------------------------------------
    f.number("pH", m.get("ph"), CONDITIONS)
    f.number("Temperature", m.get("temperature"), CONDITIONS,
             unit=unit_label(m.get("temperature_unit")) or None)
    for sd in view.species_data:
        label = idx.name(sd.get("species_id"))
        unit = unit_label(sd.get("data_unit")) or None
        f.number(f"{label} — initial", sd.get("initial"), CONDITIONS, unit=unit)
        f.number(f"{label} — prepared", sd.get("prepared"), CONDITIONS, unit=unit)

    # --- System -----------------------------------------------------------
    for vid in view.vessel_ids():
        v = idx.vessels.get(vid) or {}
        f.text("Vessel", v.get("name") or vid, SYSTEM)
        f.number("Vessel volume", v.get("volume"), SYSTEM,
                 unit=unit_label(v.get("unit")) or None)
    names = [idx.name(s) for s in view.species_ids()]
    if names:
        f.text("Species", ", ".join(names), SYSTEM)
    for sid in view.species_ids():
        p = idx.proteins.get(sid)
        if not p:
            continue
        f.text("Enzyme", p.get("name") or sid, SYSTEM)
        f.text("EC number", p.get("ecnumber"), SYSTEM)
        f.text("Organism", p.get("organism"), SYSTEM)
        f.text("Taxonomy ID", p.get("organism_tax_id"), SYSTEM)
    for sid in view.species_ids():
        s = idx.small_molecules.get(sid)
        if s and s.get("inchikey"):
            f.text(f"{s.get('name') or sid} — InChIKey", s["inchikey"], SYSTEM)

    # --- Model: reactions and estimated parameters ------------------------
    for r in doc.get("reactions") or []:
        f.text(r.get("name") or r.get("id") or "Reaction",
               _reaction_equation(r, idx), MODEL)
        law = r.get("kinetic_law") or {}
        if law.get("equation"):
            f.text(f"{r.get('name') or 'Reaction'} — kinetic law", law["equation"], MODEL)
    for eq in doc.get("equations") or []:
        if eq.get("equation"):
            f.text(f"d({idx.name(eq.get('species_id'))})/dt"
                   if eq.get("equation_type") == "ode" else
                   f"{idx.name(eq.get('species_id'))} =",
                   eq["equation"], MODEL,
                   description=eq.get("equation_type"))
    for p in doc.get("parameters") or []:
        label = p.get("name") or p.get("symbol") or p.get("id") or "parameter"
        f.number(label, p.get("value"), MODEL, unit=unit_label(p.get("unit")) or None,
                 description=(f"stderr={p['stderr']}" if p.get("stderr") is not None else None))

    # --- Provenance -------------------------------------------------------
    f.text("Document", doc.get("name"), PROVENANCE)
    f.text("EnzymeML version", doc.get("version"), PROVENANCE)
    f.text("Created", doc.get("created"), PROVENANCE)
    f.text("Modified", doc.get("modified"), PROVENANCE)
    creators = ", ".join(p.name for p in _creators(doc) if p.name)
    f.text("Creators", creators, PROVENANCE)
    for ref in doc.get("references") or []:
        if str(ref).startswith("http"):
            f.url("Reference", ref, PROVENANCE)
        else:
            f.text("Reference", ref, PROVENANCE)
    return list(f)


def _html(doc: dict, view: _MeasurementView, *, entry_id: str,
          has_csv: bool, has_plot: bool) -> str:
    idx, m = view.idx, view.m
    rows = []
    for sd in view.species_data:
        sid = sd.get("species_id")
        u = unit_label(sd.get("data_unit"))
        rows.append(
            f"<tr><td>{esc(idx.name(sid))}</td><td>{esc(idx.kind(sid))}</td>"
            f"<td>{esc(fmt(sd.get('initial')))}</td><td>{esc(u)}</td>"
            f"<td>{len(sd.get('data') or [])}</td>"
            f"<td>{esc(sd.get('data_type') or '')}</td></tr>"
        )
    species_table = (
        "<table><thead><tr><th>Species</th><th>Type</th><th>Initial</th>"
        "<th>Unit</th><th>Points</th><th>Data type</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>" if rows else "<p>No species data.</p>"
    )

    reactions = "".join(f"<li>{esc(_reaction_equation(r, idx))}</li>"
                        for r in doc.get("reactions") or [])
    reactions_html = f"<h2>Reactions</h2><ul>{reactions}</ul>" if reactions else ""

    temp = m.get("temperature")
    tunit = unit_label(m.get("temperature_unit"))
    cond = []
    if m.get("ph") is not None:
        cond.append(f"pH {m['ph']:g}")
    if temp is not None:
        cond.append(f"{temp:g} {tunit}".strip())

    attach = ["<code>enzymeml.json</code> (machine-readable payload)"]
    if has_csv:
        attach.append("<code>timecourse.csv</code> (measurement data)")
    if has_plot:
        attach.append("<code>plot.png</code> (auto-generated)")

    desc = doc.get("description")
    desc_html = f"<h2>Description</h2><p>{esc(desc)}</p>" if desc else ""

    return (
        f"<h1>{esc(view.name)}</h1>"
        f"<p><b>Document:</b> {esc(doc.get('name', '—'))}<br>"
        f"<b>Conditions:</b> {esc(', '.join(cond)) or '—'}<br>"
        f"<b>Time points:</b> {view.n_points()}"
        f"{f' ({esc(view.time_unit())})' if view.time_unit() else ''}</p>"
        + (inline_image(entry_id, "plot.png", caption=view.name) if has_plot else "")
        + f"<h2>Species data</h2>{species_table}"
        f"{reactions_html}"
        f"{desc_html}"
        f"<h2>Attachments</h2><ul>" + "".join(f"<li>{a}</li>" for a in attach) + "</ul>"
    )


def _payload_species(doc: dict, idx: Index, measured: set[str]) -> set[str]:
    """The species a payload must carry to stay self-contained.

    The measured ones are not enough: a payload repeats the document's reactions
    and equations verbatim, so every species those mention has to travel with it
    or the payload is EnzymeML with dangling ``species_id``s. Complexes are then
    closed over their participants — a complex has no meaning without them, and
    a complex whose participants are all present belongs to this system.
    """
    sids = set(measured)
    for r in doc.get("reactions") or []:
        for role in ("reactants", "products", "modifiers"):
            sids.update(e["species_id"] for e in r.get(role) or [] if e.get("species_id"))
        law = r.get("kinetic_law") or {}
        if law.get("species_id"):
            sids.add(law["species_id"])
    sids.update(eq["species_id"] for eq in doc.get("equations") or []
                if eq.get("species_id"))

    for _ in range(len(idx.complexes) + 1):      # fixed point: complexes can nest
        grown = False
        for cid, complex_ in idx.complexes.items():
            parts = set(complex_.get("participants") or [])
            if cid in sids and not parts <= sids:
                sids |= parts
                grown = True
            elif parts and parts <= sids and cid not in sids:
                sids.add(cid)
                grown = True
        if not grown:
            break
    return sids & set(idx.species)


def _payload(doc: dict, view: _MeasurementView) -> dict:
    """Self-contained EnzymeML document holding just this measurement and the
    entities it references — see :func:`_payload_species` for the closure."""
    idx = view.idx
    sids = _payload_species(doc, idx, set(view.species_ids()))
    vids = {v for v in ((idx.species.get(s) or {}).get("vessel_id") for s in sids)
            if v}
    return {
        "version": doc.get("version"),
        "name": doc.get("name"),
        "description": doc.get("description"),
        "created": doc.get("created"),
        "modified": doc.get("modified"),
        "creators": doc.get("creators") or [],
        "vessels": [v for v in doc.get("vessels") or [] if v.get("id") in vids],
        "proteins": [p for p in doc.get("proteins") or [] if p.get("id") in sids],
        "complexes": [c for c in doc.get("complexes") or [] if c.get("id") in sids],
        "small_molecules": [s for s in doc.get("small_molecules") or []
                            if s.get("id") in sids],
        "reactions": doc.get("reactions") or [],
        "measurements": [view.m],
        "equations": doc.get("equations") or [],
        "parameters": doc.get("parameters") or [],
        "references": doc.get("references") or [],
    }


def _plot(view: _MeasurementView) -> Optional[bytes]:
    series = []
    unit = ""
    for sd in view.species_data:
        times, data = sd.get("time") or [], sd.get("data") or []
        if not times or not data:
            continue
        unit = unit or unit_label(sd.get("data_unit"))
        series.append((view.idx.name(sd.get("species_id")), times, data))
    tu = view.time_unit()
    return plot_png(series,
                    xlabel=f"time{f' [{tu}]' if tu else ''}",
                    ylabel=(", ".join(view.data_types()) or "value")
                           + (f" [{unit}]" if unit else ""),
                    title=view.name)


# ---------------------------------------------------------------------------
# document grain: the whole series as one entry
# ---------------------------------------------------------------------------

def _span(values: list[Any], unit: str = "") -> tuple[Any, bool]:
    """Collapse a value observed across measurements into one field value.

    Returns ``(value, varies)``. Identical everywhere → the value itself, which
    can stay a *number* field and therefore filterable in eLabFTW. Otherwise a
    ``min – max`` string, since a flat extra-field cannot hold a per-measurement
    series — and a single number would be a lie about the others.
    """
    vals = [v for v in values if v is not None]
    if not vals:
        return None, False
    uniq = sorted(set(vals))
    if len(uniq) == 1:
        return uniq[0], False
    return f"{fmt(uniq[0])} – {fmt(uniq[-1])}" + (f" {unit}" if unit else ""), True


def _doc_fields(doc: dict, idx: Index, views: list[_MeasurementView]) -> list[dict]:
    f = Fields()

    # --- Measurement: the series, not a single run ------------------------
    f.number("Number of measurements", len(views), MEASUREMENT)
    f.text("Measurements", ", ".join(v.name for v in views), MEASUREMENT)
    groups = sorted({v.m.get("group_id") for v in views if v.m.get("group_id")})
    if groups:
        f.text("Group ID", ", ".join(groups), MEASUREMENT,
               description="measurements sharing this ID form one series")
    pts, _ = _span([v.n_points() for v in views])
    f.add("Time points per measurement", "number" if not _ else "text", pts, MEASUREMENT)
    tu = next((v.time_unit() for v in views if v.time_unit()), "")
    if tu:
        f.text("Time unit", tu, MEASUREMENT)
    dtypes = sorted({t for v in views for t in v.data_types()})
    if dtypes:
        f.text("Data type", ", ".join(dtypes), MEASUREMENT)

    # --- Conditions: one value when constant, a span when varied ----------
    ph, ph_varies = _span([v.m.get("ph") for v in views])
    if ph is not None:
        (f.text if ph_varies else f.number)("pH", ph, CONDITIONS)
    t_unit = next((unit_label(v.m.get("temperature_unit")) for v in views
                   if v.m.get("temperature_unit")), "")
    temp, t_varies = _span([v.m.get("temperature") for v in views], t_unit)
    if temp is not None:
        if t_varies:
            f.text("Temperature", temp, CONDITIONS)
        else:
            f.number("Temperature", temp, CONDITIONS, unit=t_unit or None)

    # Starting concentrations: the varied one is the independent variable and
    # the single most useful thing to see at a glance.
    for sid in dict.fromkeys(s for v in views for s in v.species_ids()):
        unit = next((unit_label(sd.get("data_unit")) for v in views
                     for sd in v.species_data
                     if sd.get("species_id") == sid and sd.get("data_unit")), "")
        initials = [sd.get("initial") for v in views for sd in v.species_data
                    if sd.get("species_id") == sid]
        value, varies = _span(initials, unit)
        if value is None:
            continue
        label = f"{idx.name(sid)} — initial"
        if varies:
            f.text(label, value, CONDITIONS, description="varied across the series")
        else:
            f.number(label, value, CONDITIONS, unit=unit or None)

    # --- System -----------------------------------------------------------
    for vid in dict.fromkeys(v for view in views for v in view.vessel_ids()):
        vessel = idx.vessels.get(vid) or {}
        f.text("Vessel", vessel.get("name") or vid, SYSTEM)
        f.number("Vessel volume", vessel.get("volume"), SYSTEM,
                 unit=unit_label(vessel.get("unit")) or None)
    names = [idx.name(s) for s in idx.species]
    if names:
        f.text("Species", ", ".join(names), SYSTEM)
    for sid, p in idx.proteins.items():
        f.text("Enzyme", p.get("name") or sid, SYSTEM)
        f.text("EC number", p.get("ecnumber"), SYSTEM)
        f.text("Organism", p.get("organism"), SYSTEM)
        f.text("Taxonomy ID", p.get("organism_tax_id"), SYSTEM)
    for sid, s in idx.small_molecules.items():
        if s.get("inchikey"):
            f.text(f"{s.get('name') or sid} — InChIKey", s["inchikey"], SYSTEM)

    # --- Model: stated once, which is where it belongs --------------------
    for r in doc.get("reactions") or []:
        f.text(r.get("name") or r.get("id") or "Reaction",
               _reaction_equation(r, idx), MODEL)
        law = r.get("kinetic_law") or {}
        if law.get("equation"):
            f.text(f"{r.get('name') or 'Reaction'} — kinetic law", law["equation"], MODEL)
    for eq in doc.get("equations") or []:
        if eq.get("equation"):
            f.text(f"d({idx.name(eq.get('species_id'))})/dt"
                   if eq.get("equation_type") == "ode" else
                   f"{idx.name(eq.get('species_id'))} =",
                   eq["equation"], MODEL, description=eq.get("equation_type"))
    for p in doc.get("parameters") or []:
        label = p.get("name") or p.get("symbol") or p.get("id") or "parameter"
        f.number(label, p.get("value"), MODEL, unit=unit_label(p.get("unit")) or None,
                 description="fitted across the whole series"
                             + (f", stderr={p['stderr']}" if p.get("stderr") is not None else ""))

    # --- Provenance -------------------------------------------------------
    f.text("Document", doc.get("name"), PROVENANCE)
    f.text("EnzymeML version", doc.get("version"), PROVENANCE)
    f.text("Created", doc.get("created"), PROVENANCE)
    f.text("Modified", doc.get("modified"), PROVENANCE)
    f.text("Creators", ", ".join(p.name for p in _creators(doc) if p.name), PROVENANCE)
    for ref in doc.get("references") or []:
        (f.url if str(ref).startswith("http") else f.text)("Reference", ref, PROVENANCE)
    return list(f)


def _doc_plot(views: list[_MeasurementView]) -> Optional[bytes]:
    """All measurements on one axes — the point of a series is the comparison."""
    series, unit, tu = [], "", ""
    for view in views:
        tu = tu or view.time_unit()
        for sd in view.species_data:
            times, data = sd.get("time") or [], sd.get("data") or []
            if not times or not data:
                continue
            unit = unit or unit_label(sd.get("data_unit"))
            series.append((f"{view.name} · {view.idx.name(sd.get('species_id'))}",
                           times, data))
    types = sorted({t for v in views for t in v.data_types()})
    return plot_png(series,
                    xlabel=f"time{f' [{tu}]' if tu else ''}",
                    ylabel=(", ".join(types) or "value") + (f" [{unit}]" if unit else ""),
                    title="All measurements")


def _doc_html(doc: dict, idx: Index, views: list[_MeasurementView], *,
              entry_id: str, has_plot: bool, csv_names: list[str]) -> str:
    rows = []
    for view in views:
        parts = []
        for sd in view.species_data:
            if not sd.get("initial"):
                continue
            unit = unit_label(sd.get("data_unit"))
            parts.append(f"{idx.name(sd.get('species_id'))} {fmt(sd.get('initial'))}"
                         + (f" {unit}" if unit else ""))
        inits = ", ".join(parts)
        rows.append(
            f"<tr><td>{esc(view.name)}</td><td>{esc(view.m.get('ph'))}</td>"
            f"<td>{esc(fmt(view.m.get('temperature')))} "
            f"{esc(unit_label(view.m.get('temperature_unit')))}</td>"
            f"<td>{view.n_points()}</td><td>{esc(inits)}</td></tr>")
    table = ("<table><thead><tr><th>Measurement</th><th>pH</th><th>Temperature</th>"
             "<th>Points</th><th>Initial concentrations</th></tr></thead>"
             f"<tbody>{''.join(rows)}</tbody></table>")

    reactions = "".join(f"<li>{esc(_reaction_equation(r, idx))}</li>"
                        for r in doc.get("reactions") or [])
    params = "".join(
        f"<li>{esc(p.get('name') or p.get('symbol') or p.get('id'))} = "
        f"{esc(fmt(p.get('value')))} {esc(unit_label(p.get('unit')))}"
        + (f" ± {esc(fmt(p['stderr']))}" if p.get("stderr") is not None else "")
        + "</li>"
        for p in doc.get("parameters") or [])

    attach = ["<code>enzymeml.json</code> (complete machine-readable document)"]
    attach += [f"<code>{esc(n)}</code>" for n in csv_names]
    if has_plot:
        attach.append("<code>plot.png</code> (all measurements, auto-generated)")

    return (
        f"<h1>{esc(doc.get('name') or 'EnzymeML document')}</h1>"
        + (f"<p>{esc(doc.get('description'))}</p>" if doc.get("description") else "")
        + (inline_image(entry_id, "plot.png",
                        caption="All measurements of the series") if has_plot else "")
        + f"<h2>Measurements</h2>{table}"
        + (f"<h2>Reactions</h2><ul>{reactions}</ul>" if reactions else "")
        + (f"<h2>Parameters</h2><ul>{params}</ul>"
           "<p><i>Fitted across the whole series — not per measurement.</i></p>"
           if params else "")
        + "<h2>Attachments</h2><ul>"
        + "".join(f"<li>{a}</li>" for a in attach) + "</ul>"
    )


def _species_id(sid: str) -> str:
    """Crate id for a species resource item, named once so entries can link it."""
    return f"species-{slug(sid)}"


def _species_resource(species: dict, kind: str) -> Resource:
    sid = species.get("id", "species")
    name = species.get("name") or sid
    rows = [
        ("ID", sid),
        ("Type", kind),
        ("EC number", species.get("ecnumber")),
        ("Organism", species.get("organism")),
        ("Taxonomy ID", species.get("organism_tax_id")),
        ("Sequence", species.get("sequence")),
        ("InChIKey", species.get("inchikey")),
        ("InChI", species.get("inchi")),
        ("SMILES", species.get("canonical_smiles")),
        ("Participants", ", ".join(species.get("participants") or []) or None),
        ("Synonyms", ", ".join(species.get("synonymous_names") or []) or None),
    ]
    html = (f"<h1>{esc(name)}</h1><ul>"
            + "".join(f"<li><b>{esc(k)}:</b> {esc(v)}</li>" for k, v in rows if v)
            + "</ul>")

    f = Fields()
    f.text("Species ID", sid, IDENTITY)
    f.text("Type", kind, IDENTITY)
    f.text("EC number", species.get("ecnumber"), IDENTITY)
    f.text("Organism", species.get("organism"), IDENTITY)
    f.text("Taxonomy ID", species.get("organism_tax_id"), IDENTITY)
    f.text("Sequence", species.get("sequence"), IDENTITY)
    f.text("InChIKey", species.get("inchikey"), IDENTITY)
    f.text("InChI", species.get("inchi"), IDENTITY)
    f.text("SMILES", species.get("canonical_smiles"), IDENTITY)
    for ref in species.get("references") or []:
        if str(ref).startswith("http"):
            f.url("Reference", ref, IDENTITY)
        else:
            f.text("Reference", ref, IDENTITY)

    return Resource(id=_species_id(sid), name=name, html=html, fields=list(f),
                    keywords=[name, kind], category=kind)


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------

def convert(doc: dict, *, grain: str = "document", links: bool = False,
            plots: bool = True, csv: bool = True) -> tuple[list[Entry], list[Resource]]:
    validate(doc)
    idx = Index(doc)
    entries: list[Entry] = []
    used: list[str] = []

    views = ([] if grain == "document" else
             [_MeasurementView(m, idx, i) for i, m in enumerate(doc.get("measurements") or [])])

    for view in views:
        header, rows = view.table()
        csv_data = csv_bytes(header, rows) if csv and rows else None
        png = _plot(view) if plots else None

        atts = [Attachment("enzymeml.json",
                           json.dumps(_payload(doc, view), indent=2,
                                      ensure_ascii=False).encode("utf-8"),
                           description="EnzymeML document restricted to this measurement.",
                           encoding_format="application/json")]
        if csv_data:
            atts.append(Attachment("timecourse.csv", csv_data,
                                   description="Measurement time course.",
                                   encoding_format="text/csv"))
        if png:
            atts.append(Attachment("plot.png", png,
                                   description="Species data vs. time (auto-generated).",
                                   encoding_format="image/png", image=True))

        mentions = []
        if links:
            for sid in view.species_ids():
                if sid in idx.species:
                    if sid not in used:
                        used.append(sid)
                    mentions.append(resource_ref(_species_id(sid)))

        entries.append(Entry(
            id=slug(view.id),
            name=f"{doc.get('name') or 'EnzymeML'} — {view.name}",
            html=_html(doc, view, entry_id=slug(view.id),
                       has_csv=bool(csv_data), has_plot=bool(png)),
            fields=_fields(doc, view),
            keywords=["EnzymeML", *(idx.name(s) for s in view.species_ids())],
            authors=_creators(doc),
            attachments=atts,
            mentions=mentions,
            date=doc.get("created"),
        ))

    if grain == "document" or not views:
        # One entry for the whole document: a dilution series is one experiment,
        # and the fitted parameters belong to the series rather than to any
        # single measurement. See the grain discussion in the README.
        all_views = [_MeasurementView(m, idx, i)
                     for i, m in enumerate(doc.get("measurements") or [])]
        entry_id = "document"

        atts = [Attachment("enzymeml.json",
                           json.dumps(doc, indent=2, ensure_ascii=False).encode("utf-8"),
                           description="Complete EnzymeML document.",
                           encoding_format="application/json")]
        csv_names: list[str] = []
        if csv:
            for view in all_views:
                header, rows = view.table()
                if not rows:
                    continue
                name = f"timecourse_{slug(view.id)}.csv"
                csv_names.append(name)
                atts.append(Attachment(name, csv_bytes(header, rows),
                                       description=f"Time course of {view.name}.",
                                       encoding_format="text/csv"))
        png = _doc_plot(all_views) if plots else None
        if png:
            atts.append(Attachment("plot.png", png,
                                   description="All measurements (auto-generated).",
                                   encoding_format="image/png", image=True))

        mentions = []
        if links:
            for sid in idx.species:
                if sid not in used:
                    used.append(sid)
                mentions.append(resource_ref(_species_id(sid)))

        entries.append(Entry(
            id=entry_id,
            name=doc.get("name") or "EnzymeML document",
            html=_doc_html(doc, idx, all_views, entry_id=entry_id,
                           has_plot=bool(png), csv_names=csv_names),
            fields=_doc_fields(doc, idx, all_views),
            keywords=["EnzymeML", *(idx.name(s) for s in idx.species)],
            authors=_creators(doc),
            attachments=atts,
            mentions=mentions,
            date=doc.get("created"),
        ))

    resources = [_species_resource(idx.species[s], idx.kind(s)) for s in used]
    return entries, resources


def title(doc: dict) -> str:
    return f"EnzymeML export — {doc.get('name') or 'document'}"


# ---------------------------------------------------------------------------
# reverse: entry payloads -> one EnzymeMLDocument
# ---------------------------------------------------------------------------

# How :func:`_payload` distributed the document across entries, read backwards.
# ``reactions``/``equations``/``parameters`` are document-level but copied into
# every payload, so they de-duplicate by value rather than concatenating.
_MERGE = dict(
    by_id={"vessels": "id", "proteins": "id", "complexes": "id",
           "small_molecules": "id"},
    concat=("measurements",),
    unique=("creators", "reactions", "equations", "parameters", "references"),
)

#: Nothing: every part of a v2 document is reachable from some entry, provided
#: :func:`_payload_species` closes each payload over what its reactions and
#: equations mention. A species referenced by nothing at all would land here.
EXPECTED_LOSS = ()


def reassemble(payloads: list[dict]) -> dict:
    """Merge per-measurement payloads back into one EnzymeMLDocument.

    Lossless for grain ``measurement``: every entity a measurement references is
    repeated in its payload, so the union restores them. Species that no
    measurement mentions exist only in ``source.document.json`` — see
    :mod:`eln.read` for why that route is preferred when available.
    """
    return merge_documents(payloads, **_MERGE)
