"""Convert schema-typed JSON documents into ELN RO-Crate (``.eln``) packages.

Two dedicated converters share the crate plumbing in :mod:`eln.crate`:

* :mod:`eln.fairfluids` — FAIRFluids documents (``fairfluids.xsd``)
* :mod:`eln.enzymeml`   — EnzymeML v2 documents (``enzymeML.xsd``)

The conversion is reversible: :func:`import_file` reads an ``.eln`` back into
the source document, and :func:`roundtrip` exports and re-imports in one step so
the mapping can be checked against the original.

Typical use::

    python -m eln fairfluids.json -o urea_water.eln --links
    python -m eln enzymeml.json  -o kinetics.eln --grain measurement
    python -m eln kinetics.eln   -o back.json --from entries
"""

from .crate import Attachment, Entry, Resource, build_crate, write_eln
from .read import Crate, CrateEntry, merge_documents, read_eln

__all__ = ["Attachment", "Entry", "Resource", "Crate", "CrateEntry",
           "build_crate", "write_eln", "read_eln", "merge_documents",
           "convert_document", "convert_file", "import_file", "roundtrip",
           "pick", "CONVERTERS"]

from . import enzymeml, fairfluids  # noqa: E402  (circular-free, after crate)

CONVERTERS = {fairfluids.SCHEMA: fairfluids, enzymeml.SCHEMA: enzymeml}


def pick(doc: dict, schema: str = "auto"):
    """Return the converter module for a document."""
    if schema != "auto":
        try:
            return CONVERTERS[schema]
        except KeyError:
            raise ValueError(f"unknown schema {schema!r}; "
                             f"expected one of {', '.join(CONVERTERS)}") from None
    for mod in CONVERTERS.values():
        if mod.detect(doc):
            return mod
    raise ValueError(
        "could not detect the schema from the document's top-level keys "
        f"({', '.join(list(doc)[:8])}…). Pass --schema explicitly.")


def convert_document(doc: dict, *, schema: str = "auto", grain: str = "auto",
                     links: bool = False, plots: bool = True, csv: bool = True,
                     category: str = "", license: str = "",
                     embed_source: bool = True):
    """Turn a parsed document into a crate. Returns (crate, entries, resources).

    The whole export except reading and writing files, so callers that hold a
    document in memory — a notebook, a web service — get the same schema
    detection, grain default and publisher metadata as the CLI instead of
    reassembling them by hand and drifting.
    """
    mod = pick(doc, schema)
    if grain == "auto":
        # EnzymeML defaults to one entry for the whole document: see the grain
        # discussion in eln.enzymeml. FAIRFluids keeps per-fluid, where the
        # fluids really are separate systems rather than one series.
        grain = "fluid" if mod is fairfluids else "document"

    entries, resources = mod.convert(doc, grain=grain, links=links,
                                     plots=plots, csv=csv)
    name, url = mod.PUBLISHER
    crate = build_crate(
        entries,
        resources=resources,
        source_document=doc if embed_source else None,
        title=mod.title(doc),
        description=f"{mod.SCHEMA} document exported as an ELN RO-Crate.",
        category=category or mod.SCHEMA.capitalize(),
        license=license,
        publisher_name=name,
        publisher_url=url,
    )
    return crate, entries, resources


def convert_file(path, out_path, *, schema: str = "auto", grain: str = "auto",
                 links: bool = False, plots: bool = True, csv: bool = True,
                 category: str = "", license: str = "", embed_source: bool = True):
    """Read a JSON document and write an ``.eln``. Returns (path, entries, resources)."""
    import json
    from pathlib import Path

    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    crate, entries, resources = convert_document(
        doc, schema=schema, grain=grain, links=links, plots=plots, csv=csv,
        category=category, license=license, embed_source=embed_source)
    out = write_eln(crate, Path(out_path), root_name=Path(out_path).stem)
    return out, entries, resources


def import_file(path, out_path=None, *, schema: str = "auto", route: str = "auto"):
    """Read an ``.eln`` back into its source document.

    ``route`` selects the reconstruction strategy (see :mod:`eln.read`):
    ``source`` uses the complete document attached at the crate root,
    ``entries`` rebuilds it by merging the per-entry payloads, ``auto`` prefers
    ``source`` and falls back to ``entries``.

    Returns ``(document, route_used, crate)``.
    """
    import json
    from pathlib import Path

    crate = read_eln(path)

    if route not in ("auto", "source", "entries"):
        raise ValueError(f"unknown route {route!r}; expected source, entries or auto")

    if route in ("auto", "source") and crate.source_document is not None:
        doc, used = crate.source_document, "source"
    elif route == "source":
        from .crate import ROOT_DOCUMENT_NAME
        raise ValueError(
            f"{Path(path).name} has no {ROOT_DOCUMENT_NAME} at the crate root "
            "(written with --no-source?); try --from entries")
    else:
        payloads = [p for p in (e.payload() for e in crate.entries) if p]
        if not payloads:
            raise ValueError(
                f"{Path(path).name}: no JSON payloads on any entry, so the "
                "document cannot be rebuilt; only the extra-fields survive here")
        mod = pick(payloads[0], schema)
        if not hasattr(mod, "reassemble"):
            raise ValueError(f"the {mod.SCHEMA} converter cannot rebuild documents")
        doc, used = mod.reassemble(payloads), "entries"

    if out_path is not None:
        Path(out_path).write_text(
            json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return doc, used, crate


def roundtrip(path, *, route: str = "entries", keep=None, **convert_kw):
    """Export a source document, read it back and diff it against the original.

    Returns ``(original, restored, deltas)``. The default route deliberately
    skips ``source.document.json``: reading back the file we just copied in
    proves nothing, whereas rebuilding from the entries exercises the actual
    mapping. Pass ``keep=<path>`` to retain the intermediate ``.eln``.
    """
    import json
    import tempfile
    from pathlib import Path

    from .diff import compare

    original = json.loads(Path(path).read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(keep) if keep else Path(tmp) / (Path(path).stem + ".eln")
        eln_path, _, _ = convert_file(path, target, **convert_kw)
        restored, _, _ = import_file(eln_path, route=route)
    return original, restored, list(compare(original, restored))
