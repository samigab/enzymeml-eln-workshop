"""Read an ``.eln`` package back into its parts — the inverse of :mod:`eln.crate`.

Schema-agnostic on purpose: this module knows about crates, entries and
attachments, not about EnzymeML or FAIRFluids. Turning the pieces back into a
source document is the schema module's job (its ``reassemble``).

Three reconstruction routes exist, in decreasing fidelity:

``source``
    ``source.document.json`` at the crate root. Byte-identical round-trip,
    including entities no entry references. Absent when the crate was written
    with ``--no-source``.
``entries``
    The per-entry payloads (``enzymeml.json`` …) merged back together. Lossless
    for everything reachable from an entry; document-level orphans are dropped.
    This is the route that still works after a foreign ELN has re-exported the
    crate, as long as it kept the attachments.
``fields``
    The eLabFTW extra-fields alone. Lossy by construction — the fields are
    rendered strings, not the source model. Not a reconstruction route; exposed
    as :attr:`CrateEntry.fields` so the loss can be *measured* rather than
    argued about.
"""

from __future__ import annotations

import io
import json
import posixpath
import zipfile
from dataclasses import dataclass, field as dc_field
from pathlib import Path
from typing import Any, Optional

from .crate import ROOT_DOCUMENT_NAME


@dataclass
class CrateEntry:
    """One ``Dataset`` node from the crate, with its payload files."""

    id: str                                        # folder name, e.g. "m0"
    name: str
    genre: str
    node: dict
    files: dict[str, bytes] = dc_field(default_factory=dict)   # basename -> bytes
    fields: dict[str, dict] = dc_field(default_factory=dict)   # extra-field name -> spec

    def payload(self, name: Optional[str] = None) -> Optional[dict]:
        """Parse an attached JSON payload.

        Without ``name`` the entry's single JSON attachment is used; entries
        carry exactly one (the CSV and the plot are derived views of it).
        """
        if name is not None:
            data = self.files.get(name)
            return json.loads(data) if data else None
        candidates = [n for n in self.files if n.endswith(".json")]
        if len(candidates) != 1:
            return None
        return json.loads(self.files[candidates[0]])

    @property
    def field_values(self) -> dict[str, str]:
        return {k: v.get("value") for k, v in self.fields.items()}


@dataclass
class Crate:
    root: str
    graph: list[dict]
    node: dict
    entries: list[CrateEntry] = dc_field(default_factory=list)
    resources: list[CrateEntry] = dc_field(default_factory=list)
    source_document: Optional[dict] = None

    @property
    def title(self) -> str:
        return self.node.get("name") or self.root


def _extra_fields(node: dict, by_id: Optional[dict[str, dict]] = None) -> dict[str, dict]:
    """Recover the eLabFTW extra-fields from a node's ``variableMeasured``.

    Prefers the ``elabftw_metadata`` blob, which carries type, group and unit;
    falls back to the individual ``PropertyValue`` nodes emitted alongside it
    for generic consumers.

    Handles both shapes a crate can use. We write, and eLabFTW writes,
    ``{"@id": …}`` references into the graph — proper flattened JSON-LD. But
    eLabFTW exports older than its internal ELN version 103 nested the
    PropertyValue objects inline, and so did this converter until we moved to
    ro-crate-py. A reader has no reason to be strict about a distinction it can
    simply absorb, so both are accepted.
    """
    by_id = by_id or {}
    pvs = node.get("variableMeasured") or []
    if isinstance(pvs, dict):
        pvs = [pvs]
    pvs = [by_id.get(pv["@id"], pv) if isinstance(pv, dict) and set(pv) == {"@id"} else pv
           for pv in pvs]
    for pv in pvs:
        if isinstance(pv, dict) and pv.get("propertyID") == "elabftw_metadata":
            try:
                meta = json.loads(pv.get("value") or "{}")
            except json.JSONDecodeError:
                break
            return meta.get("extra_fields") or {}
    out: dict[str, dict] = {}
    for pv in pvs:
        if not isinstance(pv, dict) or pv.get("propertyID") == "elabftw_metadata":
            continue
        spec = {"type": pv.get("valueReference") or "text", "value": pv.get("value")}
        if pv.get("unitText"):
            spec["unit"] = pv["unitText"]
        if pv.get("description"):
            spec["description"] = pv["description"]
        out[str(pv.get("propertyID"))] = spec
    return out


def read_eln(source: Path | str | bytes) -> Crate:
    """Open an ``.eln`` and return its crate structure.

    Accepts a path or the raw ZIP bytes, so a crate built in memory by
    :func:`eln.crate.eln_bytes` can be read straight back without a temporary
    file. Raises ValueError.
    """
    if isinstance(source, bytes):
        path, handle = Path("<bytes>"), io.BytesIO(source)
    else:
        path = handle = Path(source)
    try:
        zf = zipfile.ZipFile(handle)
    except zipfile.BadZipFile as exc:
        raise ValueError(f"{path.name} is not a ZIP archive, so not an .eln ({exc})") from None
    with zf:
        names = [n for n in zf.namelist() if not n.endswith("/")]
        roots = {n.split("/")[0] for n in names}
        if len(roots) != 1:
            raise ValueError(
                f"{path.name}: an .eln must have exactly one root folder, "
                f"found {sorted(roots) or 'none'}")
        root = roots.pop()

        meta_arc = f"{root}/ro-crate-metadata.json"
        if meta_arc not in names:
            raise ValueError(f"{path.name}: no {meta_arc}")
        try:
            crate_json = json.loads(zf.read(meta_arc))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path.name}: {meta_arc} is not valid JSON ({exc})") from None

        # Payload bytes keyed by crate-relative path: "m0/data.csv".
        payloads = {n[len(root) + 1:]: zf.read(n) for n in names if n != meta_arc}

    graph = crate_json.get("@graph") or []
    if not isinstance(graph, list):
        raise ValueError(f"{path.name}: @graph is not a list")
    by_id = {n.get("@id"): n for n in graph if isinstance(n, dict)}

    root_node = by_id.get("./")
    if root_node is None:
        raise ValueError(f"{path.name}: no './' root Dataset node")

    crate = Crate(root=root, graph=graph, node=root_node)

    src = payloads.get(ROOT_DOCUMENT_NAME)
    if src is not None:
        try:
            crate.source_document = json.loads(src)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"{path.name}: {ROOT_DOCUMENT_NAME} is not valid JSON ({exc})") from None

    # Entries are the Dataset nodes below the root, in root hasPart order so the
    # reassembled document keeps the original entity order.
    parts = root_node.get("hasPart") or []
    if isinstance(parts, dict):
        parts = [parts]
    for ref in parts:
        if not isinstance(ref, dict):
            continue
        nid = ref.get("@id") or ""
        node = by_id.get(nid)
        if node is None or not nid.endswith("/") or nid == "./":
            continue                                   # a File, or a dangling ref
        types = node.get("@type")
        types = types if isinstance(types, list) else [types]
        if "Dataset" not in types:
            continue

        # Crates in the wild write folder ids both ways — ro-crate-py normalises
        # to "m0/", eLabFTW's exporter writes "./m0/". Compare without the prefix
        # so either resolves against the payload paths.
        folder = nid[2:] if nid.startswith("./") else nid   # "m0/"
        files = {posixpath.basename(k): v for k, v in payloads.items()
                 if k.startswith(folder) and k != folder}
        item = CrateEntry(
            id=folder.rstrip("/"),
            name=node.get("name") or folder.rstrip("/"),
            genre=node.get("genre") or "experiment",
            node=node,
            files=files,
            fields=_extra_fields(node, by_id),
        )
        (crate.resources if item.genre == "item" else crate.entries).append(item)

    return crate


# ---------------------------------------------------------------------------
# merging per-entry payloads back into one document
# ---------------------------------------------------------------------------

def _empty(value: Any) -> bool:
    return value is None or value == [] or value == {} or value == ""


def _key(item: Any) -> str:
    return json.dumps(item, sort_keys=True, ensure_ascii=False, default=str)


def merge_documents(payloads: list[dict], *,
                    by_id: Optional[dict[str, str]] = None,
                    concat: tuple[str, ...] = (),
                    unique: tuple[str, ...] = ()) -> dict:
    """Merge per-entry payloads back into a single source document.

    Each payload is itself a valid document of the schema, restricted to one
    entry, so merging is per-key rather than structural:

    ``by_id``  ``{key: id_field}`` — entity lists; keep the first item per ID.
               These are the define-once entities every payload that references
               them had to repeat.
    ``concat`` lists that partition across entries (the measurements/fluids the
               grain split on); concatenated in entry order.
    ``unique`` lists copied wholesale into every payload; de-duplicated by value.
    Anything else is a document-level scalar: taken from the first payload that
    has a non-empty value.

    Key order follows first appearance across the payloads, which is the order
    the schema module wrote them in — so the result diffs cleanly against the
    original file.
    """
    by_id = by_id or {}
    payloads = [p for p in payloads if isinstance(p, dict)]
    if not payloads:
        raise ValueError("no entry payloads to merge")

    order: list[str] = []
    for p in payloads:
        for k in p:
            if k not in order:
                order.append(k)

    out: dict[str, Any] = {}
    for key in order:
        values = [p[key] for p in payloads if key in p]
        if key in by_id:
            id_field, seen, merged = by_id[key], set(), []
            for value in values:
                for item in value or []:
                    ident = (item.get(id_field) if isinstance(item, dict) else None)
                    marker = f"#{ident}" if ident is not None else _key(item)
                    if marker not in seen:
                        seen.add(marker)
                        merged.append(item)
            out[key] = merged
        elif key in concat:
            out[key] = [item for value in values for item in (value or [])]
        elif key in unique:
            seen, merged = set(), []
            for value in values:
                for item in value or []:
                    marker = _key(item)
                    if marker not in seen:
                        seen.add(marker)
                        merged.append(item)
            out[key] = merged
        else:
            out[key] = next((v for v in values if not _empty(v)), values[0])
    return out
