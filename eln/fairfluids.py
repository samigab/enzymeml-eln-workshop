"""FAIRFluids (fairfluids.xsd) → ELN RO-Crate.

Grain ``fluid`` (default): one eLabFTW experiment per ``Fluid``. A fluid bundles
a compound system, the properties measured on it, the parameters varied, and the
sample's measurement series — which is exactly the unit a researcher thinks of
as "one experiment".

Grain ``document``: the whole FAIRFluidsDocument becomes a single entry.

Compounds can additionally be emitted as linked resource items (``--links``).
"""

from __future__ import annotations

import json
from typing import Any, Optional

from .crate import (CONDITIONS, IDENTITY, MEASUREMENT, MODEL, PROVENANCE,
                    SAMPLE, SYSTEM, Attachment, Entry, Fields, Person, Resource,
                    esc, resource_ref, slug, strip_ld)
from .read import merge_documents
from .util import csv_bytes, plot_png, unit_label

SCHEMA = "fairfluids"
PUBLISHER = ("FAIRFluids ELN converter", "https://github.com/FAIRChemistry/FAIRFluids")


def detect(doc: dict) -> bool:
    return "fluid" in doc and "compound" in doc


# ---------------------------------------------------------------------------
# document indexing
# ---------------------------------------------------------------------------

class Index:
    """Resolve the document's define-once entities by their local IDs."""

    def __init__(self, doc: dict):
        self.doc = doc
        self.compounds = {c.get("compoundID"): c for c in doc.get("compound") or []}

    def compound_name(self, cid: str) -> str:
        c = self.compounds.get(cid) or {}
        return c.get("commonName") or c.get("name_IUPAC") or cid


def _fluid_id(fluid: dict, i: int) -> str:
    fid = fluid.get("fluidID")
    if isinstance(fid, list):
        fid = fid[0] if fid else None
    return str(fid or f"fluid_{i + 1}")


def _authors(doc: dict) -> list[Person]:
    return [Person(given_name=a.get("given_name"), family_name=a.get("family_name"),
                   orcid=a.get("orcid"), email=a.get("email"))
            for a in (doc.get("citation") or {}).get("author") or []]


def _version(doc: dict) -> str:
    v = doc.get("version") or {}
    major, minor = v.get("versionMajor"), v.get("versionMinor")
    return f"{major}.{minor}" if major is not None else ""


# ---------------------------------------------------------------------------
# per-fluid extraction
# ---------------------------------------------------------------------------

class _FluidView:
    """Flattens one Fluid into the tables the crate needs."""

    def __init__(self, fluid: dict, idx: Index, i: int):
        self.fluid = fluid
        self.idx = idx
        self.id = _fluid_id(fluid, i)
        self.compound_ids = [c for c in fluid.get("compounds") or []]
        self.compound_names = [idx.compound_name(c) for c in self.compound_ids]
        self.sample = fluid.get("sample") or {}
        self.measurements = self.sample.get("measurement") or []
        self.properties = {p.get("propertyID"): p for p in fluid.get("property") or []}
        self.parameters = {p.get("parameterID"): p for p in fluid.get("parameter") or []}
        self.fitted_models = fluid.get("fitted_model") or []

    # -- labels ------------------------------------------------------------
    def parameter_label(self, pid: str) -> str:
        p = self.parameters.get(pid) or {}
        label = p.get("parameters") or pid
        assoc = [self.idx.compound_name(c) for c in p.get("associated_compounds") or []]
        return f"{label} [{', '.join(assoc)}]" if assoc else str(label)

    def parameter_unit(self, pid: str) -> str:
        return unit_label((self.parameters.get(pid) or {}).get("unit"))

    def property_label(self, pid: str) -> str:
        p = self.properties.get(pid) or {}
        return str(p.get("properties") or pid)

    def property_unit(self, pid: str) -> str:
        return unit_label((self.properties.get(pid) or {}).get("unit"))

    @property
    def system_name(self) -> str:
        return " + ".join(self.compound_names) or self.id

    # -- values ------------------------------------------------------------
    def param_values(self, pid: str) -> list[float]:
        out = []
        for m in self.measurements:
            for pv in m.get("parameterValue") or []:
                if pv.get("parameterID") == pid and pv.get("paramValue") is not None:
                    out.append(pv["paramValue"])
        return out

    def prop_values(self, pid: str) -> list[float]:
        out = []
        for m in self.measurements:
            for pv in m.get("propertyValue") or []:
                if pv.get("propertyID") == pid and pv.get("propValue") is not None:
                    out.append(pv["propValue"])
        return out

    def methods(self) -> list[str]:
        return sorted({m.get("method") for m in self.measurements if m.get("method")})

    def source_dois(self) -> list[str]:
        return sorted({m.get("source_doi") for m in self.measurements if m.get("source_doi")})

    # -- flat table --------------------------------------------------------
    def table(self) -> tuple[list[str], list[list[Any]]]:
        """(header, rows) — one row per measurement, parameters then properties."""
        pids = list(self.parameters)
        prids = list(self.properties)
        header = ["measurement_id"]
        for pid in pids:
            u = self.parameter_unit(pid)
            header.append(f"{self.parameter_label(pid)}{f' [{u}]' if u else ''}")
        for pid in prids:
            u = self.property_unit(pid)
            header.append(f"{self.property_label(pid)}{f' [{u}]' if u else ''}")
            header.append(f"{self.property_label(pid)} uncertainty")
        header += ["method", "source_doi"]

        rows = []
        for m in self.measurements:
            pvals = {pv.get("parameterID"): pv.get("paramValue")
                     for pv in m.get("parameterValue") or []}
            rvals = {pv.get("propertyID"): pv for pv in m.get("propertyValue") or []}
            row: list[Any] = [m.get("measurement_id")]
            row += [pvals.get(pid) for pid in pids]
            for pid in prids:
                pv = rvals.get(pid) or {}
                row += [pv.get("propValue"), pv.get("uncertainty")]
            row += [m.get("method"), m.get("source_doi")]
            rows.append(row)
        return header, rows


# ---------------------------------------------------------------------------
# entry building
# ---------------------------------------------------------------------------

def _fields(doc: dict, view: _FluidView) -> list[dict]:
    f = Fields()
    cit = doc.get("citation") or {}

    # --- Measurement ------------------------------------------------------
    for pid in view.properties:
        f.text("Measured property", view.property_label(pid), MEASUREMENT,
               description="property reported for this fluid")
        unit = view.property_unit(pid)
        if unit:
            f.text("Property unit", unit, MEASUREMENT)
        vals = view.prop_values(pid)
        if vals:
            f.number(f"{view.property_label(pid)} (min)", min(vals), MEASUREMENT, unit=unit or None)
            f.number(f"{view.property_label(pid)} (max)", max(vals), MEASUREMENT, unit=unit or None)
    f.number("Number of measurements", len(view.measurements), MEASUREMENT)
    methods = view.methods()
    if methods:
        f.text("Method", ", ".join(methods), MEASUREMENT,
               description="how the property value was obtained")
    descs = sorted({m.get("method_description") for m in view.measurements
                    if m.get("method_description")})
    if descs:
        f.text("Method description", " | ".join(descs), MEASUREMENT)

    # --- System -----------------------------------------------------------
    f.text("Fluid ID", view.id, SYSTEM)
    f.text("Chemical system", view.system_name, SYSTEM)
    f.number("Number of components", len(view.compound_ids), SYSTEM)
    keys = []
    for cid in view.compound_ids:
        c = view.idx.compounds.get(cid) or {}
        k = c.get("standard_InChI_key")
        if k:
            keys.append(f"{k} ({view.idx.compound_name(cid)})")
    if keys:
        f.text("Components (InChIKey)", "; ".join(keys), SYSTEM)

    # --- Conditions: parameter ranges as numeric fields --------------------
    for pid in view.parameters:
        vals = view.param_values(pid)
        if not vals:
            continue
        label = view.parameter_label(pid)
        unit = view.parameter_unit(pid) or None
        if min(vals) == max(vals):
            f.number(label, min(vals), CONDITIONS, unit=unit)
        else:
            f.number(f"{label} (min)", min(vals), CONDITIONS, unit=unit)
            f.number(f"{label} (max)", max(vals), CONDITIONS, unit=unit)

    # --- Sample -----------------------------------------------------------
    if view.sample.get("sample_id"):
        f.text("Sample ID", view.sample["sample_id"], SAMPLE)
    storage = view.sample.get("storage") or {}
    f.text("Storage type", storage.get("storage_type"), SAMPLE)
    cond = storage.get("storage_conditions") or {}
    f.number("Storage temperature", cond.get("Temperature"), SAMPLE)
    f.number("Storage pressure", cond.get("Pressure"), SAMPLE)
    for label, key in (("Gassed", "gassed"), ("Inert", "inert"), ("Light", "light")):
        if cond.get(key) is not None:
            f.text(label, cond[key], SAMPLE)
    prep = view.sample.get("preparation") or {}
    f.text("Preparation method", prep.get("prepMethod"), SAMPLE)
    vendor = view.sample.get("vendor_chemical") or {}
    f.text("Vendor", vendor.get("Vendor"), SAMPLE)
    f.text("LOT", vendor.get("LOT"), SAMPLE)
    f.text("Purity", vendor.get("purity"), SAMPLE)
    f.text("CAS", vendor.get("CAS"), SAMPLE)

    # --- Fitted models ----------------------------------------------------
    for fm in view.fitted_models:
        name = fm.get("model_name") or fm.get("modelID") or "model"
        f.text(f"{name} — equation", fm.get("model_equation"), MODEL)
        f.text(f"{name} — fit method", fm.get("method"), MODEL)
        f.text(f"{name} — fitted property", fm.get("fitted_property"), MODEL)
        f.number(f"{name} — R²", fm.get("r_squared"), MODEL)
        f.number(f"{name} — n points", fm.get("n_points"), MODEL)
        for fp in fm.get("FittedParameter") or fm.get("fitted_parameter") or []:
            pname = fp.get("name") or "parameter"
            f.number(f"{name} · {pname}", fp.get("value"), MODEL,
                     unit=unit_label(fp.get("unit")) or None,
                     description=(f"u={fp.get('standard_uncertainty')}"
                                  if fp.get("standard_uncertainty") is not None else None))

    # --- Provenance -------------------------------------------------------
    doi = cit.get("doi") or (view.source_dois() or [None])[0]
    if doi:
        f.url("Source DOI", f"https://doi.org/{doi}", PROVENANCE, description=doi)
    f.text("Publication", cit.get("title"), PROVENANCE)
    f.text("Journal", cit.get("pub_name"), PROVENANCE)
    f.text("Publication year", cit.get("publication_year"), PROVENANCE)
    f.text("Literature type", cit.get("litType"), PROVENANCE)
    authors = ", ".join(p.name for p in _authors(doc) if p.name)
    f.text("Authors", authors, PROVENANCE)
    f.url("Citation URL", cit.get("url_citation"), PROVENANCE)
    f.text("FAIRFluids version", _version(doc), PROVENANCE)
    return list(f)


def _html(doc: dict, view: _FluidView, *, has_csv: bool, has_plot: bool) -> str:
    cit = doc.get("citation") or {}
    props = "; ".join(
        f"{view.property_label(pid)}"
        + (f" ({view.property_unit(pid)})" if view.property_unit(pid) else "")
        for pid in view.properties
    ) or "—"

    rows = []
    for pid in view.parameters:
        vals = view.param_values(pid)
        if not vals:
            continue
        unit = view.parameter_unit(pid)
        span = (f"{min(vals):g}" if min(vals) == max(vals)
                else f"{min(vals):g} – {max(vals):g}")
        rows.append(f"<tr><td>{esc(view.parameter_label(pid))}</td>"
                    f"<td>{esc(span)}</td><td>{esc(unit)}</td></tr>")
    cond_table = (
        "<table><thead><tr><th>Parameter</th><th>Range</th><th>Unit</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>" if rows else "<p>No parameters recorded.</p>"
    )

    authors = ", ".join(p.name for p in _authors(doc) if p.name)
    src = ""
    if cit.get("title") or cit.get("doi"):
        src = f"<p><b>Source:</b> {esc(authors)} — <i>{esc(cit.get('title', ''))}</i>"
        if cit.get("pub_name"):
            src += f", {esc(cit['pub_name'])}"
        if cit.get("publication_year"):
            src += f" ({esc(cit['publication_year'])})"
        if cit.get("doi"):
            src += f' <a href="https://doi.org/{esc(cit["doi"])}">{esc(cit["doi"])}</a>'
        src += "</p>"

    attach = ["<code>fairfluids.json</code> (machine-readable payload)"]
    if has_csv:
        attach.append("<code>measurements.csv</code> (flat data table)")
    if has_plot:
        attach.append("<code>plot.png</code> (auto-generated)")

    return (
        f"<h1>{esc(view.system_name)}</h1>"
        f"<p><b>Fluid:</b> {esc(view.id)}<br>"
        f"<b>Components:</b> {esc(', '.join(view.compound_names)) or '—'}<br>"
        f"<b>Measured property:</b> {esc(props)}<br>"
        f"<b>Measurements:</b> {len(view.measurements)}<br>"
        f"<b>Method:</b> {esc(', '.join(view.methods())) or '—'}</p>"
        f"<h2>Conditions</h2>{cond_table}"
        f"{src}"
        f"<h2>Attachments</h2><ul>" + "".join(f"<li>{a}</li>" for a in attach) + "</ul>"
    )


def _payload(doc: dict, view: _FluidView) -> dict:
    """A self-contained FAIRFluids document holding just this fluid and the
    compounds it references (lossless payload for one entry)."""
    return {
        "version": doc.get("version"),
        "citation": doc.get("citation"),
        # document order, not reference order: the per-entry payloads are merged
        # back by first appearance, so keeping the document's own order here is
        # what makes that merge reproduce the original list
        "compound": [c for c in doc.get("compound") or []
                     if c.get("compoundID") in set(view.compound_ids)],
        "fluid": [view.fluid],
    }


def _plot(view: _FluidView) -> Optional[bytes]:
    """Property vs. temperature (or first parameter), split into series by the
    remaining varying parameters so composition families stay separable."""
    if not view.properties or not view.parameters:
        return None
    prop_id = next(iter(view.properties))
    x_id = next((pid for pid in view.parameters
                 if (view.parameters[pid].get("parameters") or "") == "Temperature"),
                next(iter(view.parameters)))

    # Parameters that vary and are not the x axis define the series grouping.
    # In a mixture the mole fractions are collinear (x_1 fixes x_2, x_3 …), so
    # keep only the smallest prefix that still separates every series — a legend
    # repeating three derived fractions is noise.
    candidates = [pid for pid in view.parameters
                  if pid != x_id and len(set(view.param_values(pid))) > 1]

    def keys(ids: list[str]) -> set[tuple]:
        return {tuple(pvals.get(g) for g in ids)
                for pvals in ({pv.get("parameterID"): pv.get("paramValue")
                               for pv in meas.get("parameterValue") or []}
                              for meas in view.measurements)}

    full = len(keys(candidates))
    group_ids: list[str] = []
    for pid in candidates:
        if len(keys(group_ids)) >= full:
            break
        group_ids.append(pid)

    series: dict[tuple, tuple[list[float], list[float]]] = {}
    for m in view.measurements:
        pvals = {pv.get("parameterID"): pv.get("paramValue")
                 for pv in m.get("parameterValue") or []}
        rvals = {pv.get("propertyID"): pv.get("propValue")
                 for pv in m.get("propertyValue") or []}
        x, y = pvals.get(x_id), rvals.get(prop_id)
        if x is None or y is None:
            continue
        key = tuple(pvals.get(g) for g in group_ids)
        xs, ys = series.setdefault(key, ([], []))
        xs.append(x)
        ys.append(y)

    def label(key: tuple) -> str:
        parts = [f"{view.parameter_label(g)}={v:g}"
                 for g, v in zip(group_ids, key) if v is not None]
        return "; ".join(parts) or view.system_name

    xu, yu = view.parameter_unit(x_id), view.property_unit(prop_id)
    return plot_png(
        [(label(k), xs, ys) for k, (xs, ys) in sorted(series.items(),
                                                      key=lambda kv: str(kv[0]))],
        xlabel=f"{view.parameter_label(x_id)}{f' [{xu}]' if xu else ''}",
        ylabel=f"{view.property_label(prop_id)}{f' [{yu}]' if yu else ''}",
        title=view.system_name,
    )


def _compound_id(cid: str) -> str:
    """Crate id for a compound resource item, named once so entries can link it."""
    return f"compound-{slug(cid)}"


def _compound_resource(compound: dict) -> Resource:
    cid = compound.get("compoundID", "compound")
    name = compound.get("commonName") or compound.get("name_IUPAC") or cid
    rows = [
        ("Common name", compound.get("commonName")),
        ("IUPAC name", compound.get("name_IUPAC")),
        ("InChIKey", compound.get("standard_InChI_key")),
        ("InChI", compound.get("standard_InChI")),
        ("SMILES", compound.get("smiles_code")),
        ("SELFIES", compound.get("SELFIE")),
        ("Molar weight (g/mol)", compound.get("molar_weigth")),
        ("PubChem CID", compound.get("pubChemID")),
    ]
    html = (f"<h1>{esc(name)}</h1><ul>"
            + "".join(f"<li><b>{esc(k)}:</b> {esc(v)}</li>" for k, v in rows if v is not None)
            + "</ul>")

    f = Fields()
    f.text("Compound ID", cid, IDENTITY)
    f.text("IUPAC name", compound.get("name_IUPAC"), IDENTITY)
    f.text("InChIKey", compound.get("standard_InChI_key"), IDENTITY)
    f.text("InChI", compound.get("standard_InChI"), IDENTITY)
    f.text("SMILES", compound.get("smiles_code"), IDENTITY)
    f.text("SELFIES", compound.get("SELFIE"), IDENTITY)
    f.number("Molar weight", compound.get("molar_weigth"), IDENTITY, unit="g/mol")
    if compound.get("pubChemID"):
        f.url("PubChem", f"https://pubchem.ncbi.nlm.nih.gov/compound/{compound['pubChemID']}",
              IDENTITY, description=str(compound["pubChemID"]))

    return Resource(id=_compound_id(cid), name=name, html=html, fields=list(f),
                    keywords=[name, compound.get("standard_InChI_key")],
                    category="Compound")


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------

def convert(doc: dict, *, grain: str = "fluid", links: bool = False,
            plots: bool = True, csv: bool = True) -> tuple[list[Entry], list[Resource]]:
    idx = Index(doc)
    entries: list[Entry] = []
    used_compounds: list[str] = []

    if grain == "document":
        views = []
    else:
        views = [_FluidView(f, idx, i) for i, f in enumerate(doc.get("fluid") or [])]

    for view in views:
        atts: list[Attachment] = []

        header, rows = view.table()
        csv_data = csv_bytes(header, rows) if csv and rows else None

        png = _plot(view) if plots else None

        payload = json.dumps(_payload(doc, view), indent=2, ensure_ascii=False).encode("utf-8")
        atts.append(Attachment("fairfluids.json", payload,
                               description="FAIRFluids document restricted to this fluid.",
                               encoding_format="application/json"))
        if csv_data:
            atts.append(Attachment("measurements.csv", csv_data,
                                   description="Flat measurement table (parameters and properties).",
                                   encoding_format="text/csv"))
        if png:
            atts.append(Attachment("plot.png", png,
                                   description="Property vs. temperature (auto-generated).",
                                   encoding_format="image/png", image=True))

        mentions = []
        if links:
            for cid in view.compound_ids:
                if cid in idx.compounds:
                    if cid not in used_compounds:
                        used_compounds.append(cid)
                    mentions.append(resource_ref(_compound_id(cid)))

        prop_names = [view.property_label(p) for p in view.properties]
        entries.append(Entry(
            id=slug(view.id),
            name=f"{view.system_name} — {', '.join(prop_names) or 'FAIRFluids'}",
            html=_html(doc, view, has_csv=bool(csv_data), has_plot=bool(png)),
            fields=_fields(doc, view),
            keywords=[*prop_names, *view.compound_names, "FAIRFluids"],
            authors=_authors(doc),
            attachments=atts,
            mentions=mentions,
        ))

    if grain == "document" or not views:
        cit = doc.get("citation") or {}
        title = cit.get("title") or "FAIRFluids document"
        n_meas = sum(len((f.get("sample") or {}).get("measurement") or [])
                     for f in doc.get("fluid") or [])
        payload = json.dumps(doc, indent=2, ensure_ascii=False).encode("utf-8")
        f = Fields()
        f.number("Number of fluids", len(doc.get("fluid") or []), MEASUREMENT)
        f.number("Number of measurements", n_meas, MEASUREMENT)
        f.number("Number of compounds", len(idx.compounds), SYSTEM)
        f.text("Compounds", ", ".join(idx.compound_name(c) for c in idx.compounds), SYSTEM)
        if cit.get("doi"):
            f.url("Source DOI", f"https://doi.org/{cit['doi']}", PROVENANCE,
                  description=cit["doi"])
        f.text("Publication", cit.get("title"), PROVENANCE)
        f.text("Journal", cit.get("pub_name"), PROVENANCE)
        f.text("Publication year", cit.get("publication_year"), PROVENANCE)
        entries.append(Entry(
            id="document",
            name=title,
            html=(f"<h1>{esc(title)}</h1>"
                  f"<p>{len(doc.get('fluid') or [])} fluid(s), {n_meas} measurement(s), "
                  f"{len(idx.compounds)} compound(s).</p>"
                  f"<p>Full machine-readable FAIRFluids JSON is attached as "
                  f"<code>fairfluids.json</code>.</p>"),
            fields=list(f),
            keywords=["FAIRFluids"],
            authors=_authors(doc),
            attachments=[Attachment("fairfluids.json", payload,
                                    description="Complete FAIRFluids document.",
                                    encoding_format="application/json")],
        ))

    resources = [_compound_resource(idx.compounds[c]) for c in used_compounds]
    return entries, resources


def title(doc: dict) -> str:
    cit = doc.get("citation") or {}
    return f"FAIRFluids export — {cit.get('title') or cit.get('doi') or 'document'}"


# ---------------------------------------------------------------------------
# reverse: entry payloads -> one FAIRFluidsDocument
# ---------------------------------------------------------------------------

_MERGE = dict(
    by_id={"compound": "compoundID"},
    concat=("fluid",),
    unique=(),
)

#: What the ``entries`` route provably cannot return, and why.
#:
#: ``ld_id`` names the document as a whole ("this FAIRFluidsDocument"). A
#: per-fluid payload is a fragment of that document, not that document, so
#: stamping it with the same identifier would be a false claim rather than a
#: preserved one. The envelope therefore travels only in the root
#: ``source.document.json`` — which is the reason it is written by default.
EXPECTED_LOSS = ("$.ld_id", "$.ld_type", "$.ld_context")


def reassemble(payloads: list[dict]) -> dict:
    """Merge per-fluid payloads back into one FAIRFluidsDocument.

    Lossier than the EnzymeML equivalent by exactly :data:`EXPECTED_LOSS`;
    everything else — compounds, fluids, citation, version — comes back intact,
    though compounds return in first-reference rather than document order.
    """
    return merge_documents(payloads, **_MERGE)
