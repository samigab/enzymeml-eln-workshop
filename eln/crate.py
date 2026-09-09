"""Shared ELN RO-Crate (``.eln``) assembly for eLabFTW.

Schema-agnostic plumbing only: the per-schema converters (``eln.fairfluids``,
``eln.enzymeml``) decide *what* becomes an entry and *which* fields it carries,
then hand ``Entry``/``Resource`` objects to :func:`build_crate` here.

Produces a two-layer package:

* **Presentation layer** — one ``Dataset`` node per entry, carrying a human HTML
  summary, tags and ``variableMeasured`` (schema.org ``PropertyValue``) fields
  that eLabFTW turns into native, searchable extra-fields.
* **Payload layer** — the machine-readable source JSON attached via ``hasPart``,
  so nothing is lost for FAIR consumers or the round-trip importer.

The graph is built with **ro-crate-py**, the reference implementation, rather
than assembled by hand. That is not merely tidier: the library enforces
flattened JSON-LD — every nested object must be an ``{"@id": …}`` reference into
the graph — and refuses to build anything else. Handing that rule to foreign
code found two nodes of ours that violated it and that eLabFTW had been quietly
skipping.

The ZIP step stays ours. ``.eln`` requires a single root folder inside the
archive; ``ROCrate.write_zip`` writes ``ro-crate-metadata.json`` at the archive
root, which the ELN Consortium's own conformance check rejects. The library
writes RO-Crate, not ``.eln`` — the two are not the same thing, and this module
is where the difference lives. See :func:`eln_bytes`.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from dataclasses import dataclass, field as dc_field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from rocrate.model import ContextEntity
from rocrate.rocrate import ROCrate


# eLabFTW stamps its own internal ELN version onto the ``./`` node and branches
# on it when importing. From 103 on it expects ``variableMeasured`` to be a list
# of ``{"@id": …}`` references into the graph — the flattened form its own
# exporter (``Make/MakeEln.php``) produces. Below 103 it expects the
# PropertyValue objects nested inline, which is not valid flattened JSON-LD and
# which ro-crate-py rejects outright with ``no @id in {...}``.
#
# We declare 103 rather than eLabFTW's current 107 because 103 is the lowest
# version whose semantics we actually implement. The importer's only other gate
# is at 104 and concerns ``step``, which we never emit; claiming a higher number
# would promise conformance we have not tested. The price is that eLabFTW
# releases predating this branch cannot read our extra-fields — a deliberate
# trade, taken because the flattened form is what eLabFTW itself writes today.
ELN_INTERNAL_VERSION = "103"


# Filename of the complete source document attached at the crate root. A reverse
# importer should prefer it: it is lossless even for entities not reachable from
# any single entry (orphan compounds, document-level references).
ROOT_DOCUMENT_NAME = "source.document.json"


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------

def slug(text: str, fallback: str = "item") -> str:
    s = re.sub(r"[^A-Za-z0-9._-]+", "_", (text or "").strip()).strip("_")
    return s or fallback


def sha256_and_size(data: bytes) -> tuple[str, str]:
    return hashlib.sha256(data).hexdigest(), str(len(data))


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def strip_ld(obj: Any) -> Any:
    """Drop ``ld_id``/``ld_type``/``ld_context`` noise for display purposes.

    The payload keeps them (they are part of the source document); this is only
    used when we render a compact preview.
    """
    if isinstance(obj, dict):
        return {k: strip_ld(v) for k, v in obj.items()
                if k not in ("ld_id", "ld_type", "ld_context")}
    if isinstance(obj, list):
        return [strip_ld(v) for v in obj]
    return obj


def fmt(value: Any) -> str:
    """Render a value for display without binary-float noise.

    Values like 3 * 0.0111 arrive as 0.033299999999999996; %.12g restores the
    decimal the source document meant without truncating genuine precision.
    """
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return f"{value:.12g}"
    return str(value)


def esc(text: Any) -> str:
    s = "" if text is None else str(text)
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


# ---------------------------------------------------------------------------
# extra-field model
# ---------------------------------------------------------------------------

# eLabFTW extra-field groups (native "Extra fields" UI sections)
GROUPS = [
    {"id": 1, "name": "Measurement"},
    {"id": 2, "name": "System"},
    {"id": 3, "name": "Conditions"},
    {"id": 4, "name": "Provenance"},
    {"id": 5, "name": "Identity"},
    {"id": 6, "name": "Sample"},
    {"id": 7, "name": "Model"},
]

MEASUREMENT, SYSTEM, CONDITIONS, PROVENANCE, IDENTITY, SAMPLE, MODEL = 1, 2, 3, 4, 5, 6, 7


class Fields(list):
    """Ordered eLabFTW extra-field specs.

    Each spec is a dict with keys name, type, value, group_id and optionally
    unit/units/description. ``type`` is an eLabFTW field type (text, number,
    url, date). Numeric fields with units become filterable in the UI.
    """

    def add(self, name: str, ftype: str, value: Any, group: int,
            *, unit: Optional[str] = None, description: Optional[str] = None) -> None:
        if value is None or value == "":
            return
        spec: dict[str, Any] = {"name": name, "type": ftype, "value": fmt(value),
                                "group_id": group}
        if unit:
            spec["unit"] = unit
            spec["units"] = [unit]
        if description:
            spec["description"] = description
        self.append(spec)

    def text(self, name: str, value: Any, group: int, **kw: Any) -> None:
        self.add(name, "text", value, group, **kw)

    def number(self, name: str, value: Any, group: int, **kw: Any) -> None:
        self.add(name, "number", value, group, **kw)

    def url(self, name: str, value: Any, group: int, **kw: Any) -> None:
        self.add(name, "url", value, group, **kw)


def elabftw_metadata_object(fields: list[dict]) -> dict:
    """Field specs as eLabFTW's native metadata structure.

    Two consumers need this and they need it to agree. The ``.eln`` route
    wants it serialised into a string (:func:`elabftw_metadata`), because that
    is what the importer parses; the REST route wants the object itself,
    because ``PATCH /experiments/{id}`` types ``metadata`` as an object. Same
    fields either way — an entry created by import and the same entry updated
    over the API must not end up with different extra fields.
    """
    extra: dict[str, Any] = {}
    used = {f["group_id"] for f in fields}
    for f in fields:
        entry: dict[str, Any] = {"type": f["type"], "value": f["value"],
                                 "group_id": f["group_id"]}
        if f.get("unit") is not None:
            entry["unit"] = f["unit"]
            entry["units"] = f.get("units", [f["unit"]])
        if f.get("description"):
            entry["description"] = f["description"]
        # duplicate names would silently overwrite; disambiguate instead
        name, n = f["name"], 2
        while name in extra:
            name, n = f"{f['name']} ({n})", n + 1
        extra[name] = entry
    return {
        "elabftw": {
            "display_main_text": True,
            "extra_fields_groups": [g for g in GROUPS if g["id"] in used],
        },
        "extra_fields": extra,
    }


def elabftw_metadata(fields: list[dict]) -> str:
    """The same structure as a JSON string.

    This is the ``value`` of the ``elabftw_metadata`` PropertyValue that
    eLabFTW parses on import into native, searchable extra-fields.
    """
    return json.dumps(elabftw_metadata_object(fields), ensure_ascii=False)


def property_values(owner_id: str, fields: list[dict]) -> list[tuple[str, dict]]:
    """Build the PropertyValue graph nodes behind an entry's extra-fields.

    Returns ``(@id, properties)`` pairs; the caller adds them to the crate and
    points the owner's ``variableMeasured`` at them. The first one is the
    ``elabftw_metadata`` blob — the whole extra-fields structure as a JSON
    string, which is what eLabFTW actually imports. The rest restate the same
    fields one node each, so a consumer that has never heard of eLabFTW can
    still read them.

    The ``@id``s are derived from owner and field name rather than randomised
    (eLabFTW uses ``pv://<uuid>``): exporting the same document twice then
    produces the same file, so a diff shows real changes instead of fresh UUIDs.
    """
    if not fields:
        return []
    prefix = f"#pv-{slug(owner_id)}"
    out: list[tuple[str, dict]] = [(f"{prefix}-elabftw_metadata", {
        "@type": "PropertyValue",
        "propertyID": "elabftw_metadata",
        "description": "eLabFTW metadata JSON as string",
        "value": elabftw_metadata(fields),
    })]
    used = {out[0][0]}
    for f in fields:
        node: dict[str, Any] = {
            "@type": "PropertyValue",
            "propertyID": f["name"],
            "valueReference": f["type"],
            "value": f["value"],
        }
        if f.get("unit"):
            node["unitText"] = f["unit"]
        if f.get("description"):
            node["description"] = f["description"]
        # two fields may legitimately share a name across groups; @ids may not
        pid, n = f"{prefix}-{slug(f['name'])}", 2
        while pid in used:
            pid, n = f"{prefix}-{slug(f['name'])}-{n}", n + 1
        used.add(pid)
        out.append((pid, node))
    return out


# ---------------------------------------------------------------------------
# what the schema converters produce
# ---------------------------------------------------------------------------

def resource_ref(res_id: str) -> str:
    """The ``@id`` under which a resource item appears in the graph.

    The one place that decides this. Entries name their resources in ``mentions``
    long before ``build_crate`` creates the nodes, so both ends must agree; when
    the two spellings lived apart, switching to ro-crate-py's normalised ``m0/``
    form left every ``mentions`` pointing at a ``./m0/`` that no longer existed.
    """
    return f"{res_id}/"


@dataclass
class Person:
    given_name: Optional[str] = None
    family_name: Optional[str] = None
    orcid: Optional[str] = None
    email: Optional[str] = None

    @property
    def name(self) -> str:
        return " ".join(p for p in (self.given_name, self.family_name) if p).strip()


@dataclass
class Attachment:
    """A file attached to an entry (payload, CSV, plot, original source …)."""
    name: str
    data: bytes
    description: str = ""
    encoding_format: str = ""
    #: render inside the entry body, not just as an upload — see `inline_token`
    image: bool = False


#: Fences around the part of an entry body this converter owns.
#:
#: An entry body is not ours. It is where somebody writes the method, a note
#: about the day the thermostat drifted, a photo of the setup. Regenerating it
#: wholesale on every update would throw all of that away, so the generated
#: part is fenced and only the inside of the fence is ever rewritten.
#:
#: The fences are plain text inside ``<p>`` because nothing subtler survives:
#: ``Filter::body`` runs HTMLPurifier, which drops comments outright, and its
#: ``Attr.AllowedClasses`` list has no room for a marker class. Text in an
#: allowed element is what is left, so the marker is visible — which is
#: arguably right, since it is telling a human not to type there.
GENERATED_BEGIN = ("=== BEGIN GENERATED SECTION - do not edit below, it is "
                   "rebuilt from the attached document ===")
GENERATED_END = "=== END GENERATED SECTION ==="

_BEGIN_RE = re.compile(r"<p[^>]*>\s*" + re.escape(GENERATED_BEGIN) + r"\s*</p>")
_END_RE = re.compile(r"<p[^>]*>\s*" + re.escape(GENERATED_END) + r"\s*</p>")


def generated_body(html: str) -> str:
    """Fence a generated body so a later update can find it again."""
    return f"<p>{GENERATED_BEGIN}</p>{html}<p>{GENERATED_END}</p>"


def splice_generated(existing: str, generated: str) -> tuple[str, bool]:
    """Put ``generated`` back inside the fence in ``existing``.

    Returns ``(body, found)``. When the fence is missing — an entry written by
    hand, or imported before this converter fenced anything — the generated
    block is *appended* rather than replacing the body. Losing somebody's notes
    is worse than leaving a stale block behind for them to delete once, and
    ``found=False`` lets the caller say so out loud instead of guessing.
    """
    begin = _BEGIN_RE.search(existing or "")
    end = _END_RE.search(existing or "")
    if begin and end and end.start() >= begin.end():
        return existing[:begin.start()] + generated + existing[end.end():], True
    return (existing or "") + generated, False


@dataclass
class Entry:
    """One eLabFTW experiment (or item) inside the crate."""
    id: str
    name: str
    html: str
    fields: list[dict] = dc_field(default_factory=list)
    keywords: list[str] = dc_field(default_factory=list)
    authors: list[Person] = dc_field(default_factory=list)
    attachments: list[Attachment] = dc_field(default_factory=list)
    mentions: list[str] = dc_field(default_factory=list)  # crate @ids
    date: Optional[str] = None
    genre: str = "experiment"

    def __post_init__(self) -> None:
        # Fenced here rather than at the four places entries are built, so that
        # a converter cannot produce an unfenced body by forgetting to ask.
        if self.html and GENERATED_BEGIN not in self.html:
            self.html = generated_body(self.html)


@dataclass
class Resource:
    """One eLabFTW resource item (compound, protein, vessel …).

    Deliberately *not* fenced the way :class:`Entry` is. The fence exists to
    protect writing from being overwritten by a later regeneration, and nothing
    regenerates a resource item: :mod:`eln.remote_write` updates experiments
    only. Stamping "do not edit below" on a record nothing rewrites would be a
    warning about a danger that does not exist. Should resources ever be
    updated too, they need the fence first.
    """
    id: str
    name: str
    html: str
    fields: list[dict] = dc_field(default_factory=list)
    keywords: list[str] = dc_field(default_factory=list)
    category: str = "Resource"

    @property
    def crate_id(self) -> str:
        return resource_ref(self.id)

    @property
    def url(self) -> str:
        """Required by eLabFTW's importer, which reads it *unguarded*.

        When an entry ``mentions`` this node, ``Import/Eln.php::import`` does
        ``'link_previous_url' => $linkNode['url']`` with no ``??`` fallback, so a
        node without the key raises an undefined-key error and the whole import
        fails. It must also stay free of a query string: the follow-up
        ``grabIdFromUrl`` reads ``$queryParams['id']`` unguarded as well, but
        returns early when ``parse_url`` finds no query — and a crate-relative
        path is not a valid absolute URL, so it bails out even earlier.
        """
        return self.crate_id


# ---------------------------------------------------------------------------
# crate assembly
# ---------------------------------------------------------------------------

def _person_nodes(people: list[Person]) -> list[tuple[str, dict]]:
    """Return ``(@id, properties)`` per author, in order, with stable local ids."""
    out, seen = [], set()
    for p in people:
        name = p.name
        if not name:
            continue
        pid = "#person-" + slug(name.lower(), "anon")
        if pid in seen:
            continue
        seen.add(pid)
        node: dict[str, Any] = {"@type": "Person", "name": name}
        if p.given_name:
            node["givenName"] = p.given_name
        if p.family_name:
            node["familyName"] = p.family_name
        if p.orcid:
            node["identifier"] = p.orcid
        if p.email:
            node["email"] = p.email
        out.append((pid, node))
    return out


def inline_token(entry_id: str, name: str) -> str:
    """Placeholder filename that eLabFTW rewrites to the real upload on import.

    ``Import/Eln.php::importFile`` does, for every File node carrying an
    ``alternateName``::

        str_replace($file['alternateName'], $upload['long_name'], $body)

    — a literal replacement over the whole entry body. So an ``<img>`` in the
    body pointing at this token becomes a working reference to the uploaded
    file. The token must therefore appear *only* inside that ``src``: it is
    deliberately unlike the display name (``plot.png``) so a mention of the
    filename in the prose is not rewritten too.
    """
    return f"eln-{slug(entry_id)}-{slug(name)}"


def inline_image(entry_id: str, name: str, *, caption: str = "") -> str:
    """An ``<img>`` for an attachment, in the URL shape eLabFTW serves uploads.

    ``app/download.php?f=<long_name>`` — deliberately **without** a ``storage``
    parameter. That parameter names which backend holds the file (1 = local
    disk, 2 = S3, …), and we are writing this link offline, for a file the
    receiving instance has not yet created, on storage we cannot know. Naming
    one is a guess about somebody else's deployment: an S3-backed instance
    (demo.elabftw.net among them) would look for the upload on local disk, not
    find it, and serve a broken image — while ``web/app/download.php`` catches
    the miss and pushes a generic "an error occurred" flash into the session,
    which then surfaces on the next page as an unexplained import failure.

    Omitting it is not a workaround but the documented path: download.php reads
    ``$storage = query->getInt('storage')`` and, on 0, falls back to the
    instance's own ``uploads_storage`` config — its comment says "the download
    links in body won't have the storage param".

    Should the reference not resolve anyway, the file is still attached to the
    entry as an upload; only the inline rendering is lost.
    """
    src = f"app/download.php?f={inline_token(entry_id, name)}"
    fig = f'<img src="{src}" alt="{esc(caption or name)}" style="max-width:100%">'
    return f"<figure>{fig}<figcaption>{esc(caption)}</figcaption></figure>" if caption else fig


def _license_entity(crate: ROCrate, license: str):
    """The root's ``license``, which RO-Crate requires and neither source has.

    Not defaulting to a real licence is the point. Neither ``enzymeML.xsd`` nor
    ``fairfluids.xsd`` carries a licence field, so the converter cannot know one,
    and stamping CC-BY on someone's measurements because a validator wants a
    value would be granting rights we were never given. The spec allows the
    licence to be "a textual description of how the RO-Crate may be used", so an
    unset licence says exactly that: nobody stated one, ask before reusing.

    Pass ``license=`` with a URL (or a sentence) as soon as the real one is known.
    """
    if license.startswith("http"):
        return crate.add(ContextEntity(crate, license, properties={
            "@type": "CreativeWork", "name": license,
            "description": "Licence declared for this export.",
        }))
    return crate.add(ContextEntity(crate, "#license", properties={
        "@type": "CreativeWork",
        "name": license or "No licence stated",
        "description": license or (
            "The source document declares no licence, and this converter will "
            "not invent one. Ask the depositor before reusing this data."),
    }))


def _add_file(crate: ROCrate, arc: str, att: Attachment,
              token: Optional[str] = None):
    """Attach one payload file, sourced from memory rather than from disk."""
    sha, size = sha256_and_size(att.data)
    props: dict[str, Any] = {
        # Plain "File", never ["File", "ImageObject"]: eLabFTW's importer
        # switches on $part['@type'] against the string 'File', and in PHP an
        # array never equals a string — a list-typed node is silently dropped.
        # eLabFTW's own exporter (Make/MakeEln.php) emits the bare string too.
        "@type": "File",
        "name": att.name,
        "contentSize": size,
        "sha256": sha,
    }
    if token:
        props["alternateName"] = token
    if att.description:
        props["description"] = att.description
    if att.encoding_format:
        props["encodingFormat"] = att.encoding_format
    # A BytesIO source keeps the whole pipeline off the filesystem: the notebook
    # builds plots and payloads in memory and never writes a temporary file.
    return crate.add_file(source=io.BytesIO(att.data), dest_path=arc,
                          properties=props)


def build_crate(
    entries: list[Entry],
    *,
    resources: Optional[list[Resource]] = None,
    source_document: Optional[dict] = None,
    title: str = "ELN export",
    description: str = "Exported as an ELN RO-Crate.",
    category: str = "",
    license: str = "",
    publisher_name: str = "eln converter",
    publisher_url: str = "",
) -> ROCrate:
    """Assemble the crate. ``category`` becomes the eLabFTW category.

    Payload bytes travel inside the crate as in-memory file sources, so the
    result is self-contained: :func:`eln_bytes` needs nothing else to write the
    package.
    """
    now = now_iso()
    crate = ROCrate(gen_preview=False)
    crate.name = title
    crate.description = description
    # Two different `version` keys, two different specifications — worth naming
    # rather than leaving to be discovered. On ./ it is eLabFTW's internal ELN
    # version (see ELN_INTERNAL_VERSION); on ro-crate-metadata.json below it is
    # the crate's own version, which the ELN File Format lists as mandatory.
    crate.root_dataset["version"] = ELN_INTERNAL_VERSION
    crate.root_dataset["datePublished"] = now
    crate.root_dataset["license"] = _license_entity(crate, license)

    publisher = crate.add(ContextEntity(crate, "#publisher", properties={
        "@type": "Organization", "name": publisher_name,
        **({"url": publisher_url} if publisher_url else {}),
    }))
    crate.metadata["sdPublisher"] = publisher
    crate.metadata["dateCreated"] = now
    crate.metadata["version"] = "1.0"

    categories: dict[str, Any] = {}

    def category_entity(name: str):
        if not name:
            return None
        if name not in categories:
            categories[name] = crate.add(ContextEntity(
                crate, f"#category-{slug(name)}",
                properties={"@type": "Thing", "name": name, "color": "29A6A3"}))
        return categories[name]

    def attach_fields(owner, owner_id: str, fields: list[dict]) -> None:
        pvs = property_values(owner_id, fields)
        if pvs:
            owner["variableMeasured"] = [
                crate.add(ContextEntity(crate, pid, properties=props))
                for pid, props in pvs
            ]

    people: dict[str, Any] = {}

    def person_entities(persons: list[Person]) -> list[Any]:
        out = []
        for pid, props in _person_nodes(persons):
            if pid not in people:
                people[pid] = crate.add(ContextEntity(crate, pid, properties=props))
            out.append(people[pid])
        return out

    for entry in entries:
        parts = [
            _add_file(crate, f"{entry.id}/{att.name}", att,
                      inline_token(entry.id, att.name) if att.image else None)
            for att in entry.attachments
        ]
        node = crate.add_dataset(dest_path=entry.id, properties={
            "name": entry.name,
            "genre": entry.genre,
            "dateCreated": entry.date or now,
            "text": entry.html,
        })
        if parts:
            node["hasPart"] = parts
        cat = category_entity(category)
        if cat is not None:
            node["about"] = cat
        authors = person_entities(entry.authors)
        if authors:
            node["author"] = authors if len(authors) > 1 else authors[0]
        kw = [k for k in entry.keywords if k]
        if kw:
            node["keywords"] = ", ".join(dict.fromkeys(kw))
        attach_fields(node, entry.id, entry.fields)
        if entry.mentions:
            node["mentions"] = [{"@id": m} for m in dict.fromkeys(entry.mentions)]

    # Complete source document attached once at the crate root — the
    # authoritative, lossless round-trip payload.
    if source_document is not None:
        data = json.dumps(source_document, indent=2, ensure_ascii=False).encode("utf-8")
        _add_file(crate, ROOT_DOCUMENT_NAME, Attachment(
            name=ROOT_DOCUMENT_NAME, data=data,
            description="Complete source document as JSON (authoritative round-trip payload).",
            encoding_format="application/json"))

    # Resource items (referenced from entries via `mentions`). Added after the
    # entries so link targets exist by the time anything resolves them.
    for res in resources or []:
        node = crate.add_dataset(dest_path=res.id, properties={
            "name": res.name,
            "genre": "item",
            "dateCreated": now,
            "url": res.url,      # see Resource.url — eLabFTW reads it unguarded
            "text": res.html,
        })
        cat = category_entity(res.category)
        if cat is not None:
            node["about"] = cat
        attach_fields(node, res.id, res.fields)
        kw = [k for k in res.keywords if k]
        if kw:
            node["keywords"] = ", ".join(dict.fromkeys(kw))

    return crate


def eln_bytes(crate: ROCrate, *, root_name: str) -> bytes:
    """Build the ``.eln`` ZIP in memory.

    ``ROCrate.write_zip`` cannot be used: it places ``ro-crate-metadata.json``
    at the archive root, while an ``.eln`` must hold everything inside exactly
    one root folder — the first thing the ELN Consortium's conformance suite
    checks. So the entities still stream themselves through the library; only
    the path prefix is ours.

    Building in memory rather than via :func:`write_eln` lets callers that never
    touch the filesystem — a notebook offering a download button, a web service —
    skip the temporary file. :func:`eln.read.read_eln` takes the same bytes back.
    """
    root = slug(root_name, "crate")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for entity in crate.data_entities + crate.default_entities:
            # A Dataset the crate lists in hasPart must exist in the payload, so
            # it gets its directory entry even when nothing lives in it. Resource
            # items are exactly that case: they are inventory entries for
            # eLabFTW, not folders of files, and without this the RO-Crate SHACL
            # profile reports each one as a Data Entity missing from the crate.
            # eLabFTW's own exporter writes a real folder per entity too.
            # ("./" is the crate root itself, which the root folder already is.)
            if entity.id.endswith("/") and entity.id != "./":
                zf.writestr(f"{root}/{entity.id}", b"")
            chunks: dict[str, bytearray] = {}
            for path, chunk in entity.stream():
                chunks.setdefault(path, bytearray()).extend(chunk)
            for path, data in chunks.items():
                zf.writestr(f"{root}/{path}", bytes(data))
    return buf.getvalue()


def write_eln(crate: ROCrate, out_path: Path, *, root_name: str) -> Path:
    """Zip a crate into an ``.eln`` package on disk."""
    out_path = Path(out_path).with_suffix(".eln")
    out_path.write_bytes(eln_bytes(crate, root_name=root_name))
    return out_path
