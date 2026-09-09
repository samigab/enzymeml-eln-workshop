"""Write a corrected document back onto the entry it came from.

The read side lives in :mod:`eln.remote`; this is the half that changes
somebody's record, and it is separate for that reason alone. Two ideas shape
it:

**Nothing is sent by accident.** :func:`prepare` computes the whole request —
every field, both bodies, which attachments differ — and sends none of it.
:func:`apply` is a second, explicit call. A notebook can therefore show the
plan and let a person read it before anything leaves the machine.

**The document is the source, the entry is the projection.** So the extra
fields are regenerated wholesale from the document rather than patched field by
field. eLabFTW offers ``metadatamerge`` for the patching approach — it keeps
existing fields and updates only their values — and we deliberately do not use
it: a field that vanished from the document (a species removed, a reaction
corrected) must vanish from the entry too, and a merge would leave it behind
looking authoritative.

That choice has a cost worth naming: anything typed into these extra fields
inside eLabFTW is overwritten. :func:`prepare` therefore looks for exactly that
before writing — see ``Plan.drift``.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass, field as dc_field
from typing import Any, Optional

from . import convert_document, pick
from .crate import (Attachment, Entry, elabftw_metadata_object, inline_token,
                    splice_generated)
from .remote import (DOCUMENT_NAMES, STATE_NORMAL, RemoteError, Session, _api,
                     _call, _raw)
from .remote import uploads as _uploads


@dataclass(frozen=True)
class Change:
    """One difference between what the entry holds and what it would hold."""
    where: str
    before: Any
    after: Any

    def __str__(self) -> str:
        def show(value):
            if value is None:
                return "—"
            text = str(value)
            return text if len(text) <= 60 else text[:59] + "…"
        return f"{self.where}: {show(self.before)} → {show(self.after)}"


@dataclass(frozen=True)
class Plan:
    """Everything :func:`apply` would send, computed and not sent."""
    experiment_id: int
    title: str
    body: str
    metadata: dict
    attachments: list[tuple[Attachment, Optional[int]]] = dc_field(default_factory=list)
    changes: list[Change] = dc_field(default_factory=list)
    drift: list[Change] = dc_field(default_factory=list)
    entry: Optional[Entry] = None
    #: whether the generated fence was found in the entry's current body. False
    #: means the block will be appended and an older one may need removing by
    #: hand — true for entries imported before the fence existed.
    fenced: bool = True
    #: attachment names the body points at but which have no upload yet. They
    #: resolve after :func:`apply` uploads them, which is why it uploads first.
    unresolved_images: list[str] = dc_field(default_factory=list)

    @property
    def empty(self) -> bool:
        return not self.changes

    def summary(self) -> str:
        if self.empty:
            return "nothing to send — the entry already matches the document"
        files = len(self.attachments)
        return (f"{len(self.changes)} change(s)"
                + (f", {files} file(s) to upload" if files else ""))


def _entry_for(document: dict, **convert_kw) -> Entry:
    """The single lab-notebook entry a document maps to.

    Writing a document back onto *an* entry only means something when the
    document maps to exactly one. EnzymeML does, by default — the whole
    document is one experiment. A multi-fluid FAIRFluids document does not,
    and silently updating the first of six would be worse than refusing.
    """
    _, entries, _ = convert_document(document, **convert_kw)
    if len(entries) != 1:
        raise RemoteError(
            f"This document maps to {len(entries)} lab notebook entries, not "
            "one, so there is no single entry to write it back to.\n"
            "  Entries fetched from eLabFTW carry the fragment of the document "
            "that belongs to them, and that fragment is what to update.")
    return entries[0]


def _current(session: Session, experiment_id: int) -> dict:
    """Title, body and metadata as the instance holds them right now.

    Read from the raw response rather than the generated model, because the
    model cannot represent what eLabFTW sends. ``metadata`` is a JSON *string*
    on the wire — it is a string column in the database — while the client
    types it as an object and hands it to ``__deserialize_model``. That
    function only copies attributes ``if isinstance(data, (list, dict))``, so a
    string yields ``Metadata(elabftw=None, extra_fields=None)`` with no error
    and no warning: every extra field on the instance silently reads as absent,
    and a drift check would then report the whole entry as hand-edited.

    Nothing here needs the model anyway. Three columns, two of them strings.
    """
    api = _api()
    payload = json.loads(
        _raw(session, api.ExperimentsApi(session.client).get_experiment,
             experiment_id) or b"{}")

    metadata = payload.get("metadata")
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except ValueError:
            metadata = None
    if not isinstance(metadata, dict):
        metadata = {}

    return {
        "title": payload.get("title") or "",
        "body": payload.get("body") or "",
        "metadata": metadata,
    }


def _current_uploads(session: Session, experiment_id: int) -> dict:
    """Current attachments by name — archived versions excluded.

    Replacing a file archives the old one and adds a new one, so the list an
    entry returns grows with every update. Only the Normal ones are the
    entry's files; an archived one is a previous version, and replacing *that*
    would add a third copy rather than update the second.
    """
    current: dict[str, dict] = {}
    for upload in _uploads(session, experiment_id):
        if upload.get("state") != STATE_NORMAL or not upload["name"]:
            continue
        seen = current.get(upload["name"])
        if seen is None or (upload["id"] or 0) > (seen["id"] or 0):
            current[upload["name"]] = upload
    return current


def _resolve_images(html: str, entry_id: str, current: dict) -> tuple[str, list[str]]:
    """Point the body's ``<img>`` tags at the files as this instance names them.

    The exporter writes a placeholder token, and eLabFTW's ``.eln`` importer
    swaps it for the upload's real ``long_name`` on the way in. Over the REST
    API nothing does that swap: a body PATCHed with the token names a file that
    does not exist, and the image the entry used to show goes blank. So the
    swap happens here instead, from the upload list the instance just gave us.

    Returns the rewritten HTML and the names that had no upload to point at.
    """
    unresolved = []
    for name, upload in current.items():
        token = inline_token(entry_id, name)
        if token not in html:
            continue
        if upload.get("long_name"):
            html = html.replace(token, upload["long_name"])
        else:
            unresolved.append(name)
    return html, unresolved


def _field_values(metadata: dict) -> dict:
    """``{field name: value}`` out of an eLabFTW metadata blob."""
    return {name: spec.get("value") if isinstance(spec, dict) else spec
            for name, spec in (metadata.get("extra_fields") or {}).items()}


def _compare_fields(before: dict, after: dict, label: str) -> list[Change]:
    """Differences between two metadata blobs, by field name."""
    old, new = _field_values(before), _field_values(after)
    changes = []
    for name in sorted(set(old) | set(new)):
        if old.get(name) != new.get(name):
            kind = ("added" if name not in old else
                    "removed" if name not in new else "changed")
            changes.append(Change(f"{label} {name!r} ({kind})",
                                  old.get(name), new.get(name)))
    return changes


def prepare(session: Session, experiment_id: int, document: dict, *,
            original: Optional[dict] = None, links: bool = False,
            plots: bool = True, csv: bool = True) -> Plan:
    """Work out what updating ``experiment_id`` to ``document`` would take.

    ``original`` is the document as it was fetched, before editing. Given it,
    the plan can also report *drift*: fields whose value on the instance is not
    what the unmodified document would produce, which means somebody typed into
    the entry directly. Those are the values this update would silently
    destroy, so they are worth seeing first.
    """
    entry = _entry_for(document, links=links, plots=plots, csv=csv)
    metadata = elabftw_metadata_object(entry.fields)
    current = _current(session, experiment_id)
    current_files = _current_uploads(session, experiment_id)

    # Only the fenced region is ours; anything a person wrote around it stays.
    body, fenced = splice_generated(current["body"], entry.html)
    body, unresolved = _resolve_images(body, entry.id, current_files)

    changes: list[Change] = []
    if entry.name and entry.name != current["title"]:
        changes.append(Change("title", current["title"], entry.name))
    if body != current["body"]:
        changes.append(Change(
            "body (generated section only)" if fenced else "body (appended)",
            f"{len(current['body'])} characters", f"{len(body)} characters"))
    changes += _compare_fields(current["metadata"], metadata, "field")

    # Which files actually differ, decided by hash rather than by uploading
    # everything and hoping. eLabFTW reports a sha256 per upload, and the
    # exporter has the bytes, so the question is answerable without a download.
    pending: list[tuple[Attachment, Optional[int]]] = []
    for attachment in entry.attachments:
        existing = current_files.get(attachment.name)
        digest = hashlib.sha256(attachment.data).hexdigest()
        if existing is None:
            pending.append((attachment, None))
            changes.append(Change(f"file {attachment.name!r} (new)",
                                  None, f"{len(attachment.data)} bytes"))
        elif existing.get("hash") and existing["hash"] != digest:
            pending.append((attachment, existing["id"]))
            changes.append(Change(f"file {attachment.name!r} (replaced)",
                                  f"{existing.get('size')} bytes",
                                  f"{len(attachment.data)} bytes"))
        elif not existing.get("hash"):
            # No hash to compare against: replace rather than assume equal.
            pending.append((attachment, existing["id"]))
            changes.append(Change(f"file {attachment.name!r} (replaced, "
                                  "no hash to compare)",
                                  f"{existing.get('size')} bytes",
                                  f"{len(attachment.data)} bytes"))

    drift: list[Change] = []
    if original is not None:
        expected = elabftw_metadata_object(
            _entry_for(original, links=links, plots=plots, csv=csv).fields)
        drift = _compare_fields(expected, current["metadata"], "field")

    return Plan(experiment_id=experiment_id, title=entry.name, body=body,
                metadata=metadata, attachments=pending, changes=changes,
                drift=drift, entry=entry, fenced=fenced,
                unresolved_images=unresolved)


def apply(session: Session, plan: Plan, *, patch: bool = True,
          upload: bool = True) -> list[str]:
    """Send the plan. Returns a line per request made.

    Kept separate from :func:`prepare` on purpose: by the time this is called
    there is nothing left to decide, so a caller can put a person between the
    two.
    """
    api = _api()
    done: list[str] = []

    # Uploads go first. The body names its images by the instance's `long_name`,
    # which a file that does not exist yet does not have — so patching before
    # uploading would write a reference to nothing and blank the image. After
    # the uploads, the list is read once more and the body resolved against it.
    if upload and plan.attachments:
        uploads_api = api.UploadsApi(session.client)
        # The generated client takes a *path* and uses its basename as the
        # upload's name, so the bytes have to reach the disk under the name
        # they should keep — a NamedTemporaryFile would upload as "tmpab12cd".
        with tempfile.TemporaryDirectory() as tmp:
            for attachment, upload_id in plan.attachments:
                path = os.path.join(tmp, attachment.name)
                with open(path, "wb") as handle:
                    handle.write(attachment.data)
                comment = attachment.description or ""
                if upload_id is None:
                    _call(session, uploads_api.post_upload, "experiments",
                          plan.experiment_id, file=path, comment=comment)
                    done.append(f"POST   uploads — {attachment.name} added")
                else:
                    _call(session, uploads_api.post_upload_replace,
                          "experiments", plan.experiment_id, upload_id,
                          file=path, comment=comment)
                    done.append(f"POST   uploads/{upload_id} — "
                                f"{attachment.name} replaced, previous version "
                                "archived")

    if patch:
        body_html = plan.body
        if plan.attachments:
            # Read the uploads back: the ones just created have `long_name`s
            # now, and the ones just replaced have new ones — eLabFTW stores
            # each version under its own name, so a body still pointing at the
            # previous version would show the file from before the update.
            body_html, missing = _resolve_images(
                body_html, plan.entry.id if plan.entry else "document",
                _current_uploads(session, plan.experiment_id))
            if missing:
                done.append("note   images without an upload to point at: "
                            + ", ".join(missing))

        # `metadata` goes over the wire as a JSON *string*, not as an object,
        # even though openapi.yaml types it as an object. The server does
        #     'metadata' => $this->getUnfilteredContent()
        # which ends in `(string) $this->content` (src/Params/ContentParams.php).
        # Hand PHP a decoded array there and the cast yields the literal string
        # "Array", which is then stored as the entry's metadata — every extra
        # field replaced by four characters. The spec is aspirational; the cast
        # is what runs.
        payload: dict[str, Any] = {"body": body_html,
                                   "metadata": json.dumps(plan.metadata,
                                                          ensure_ascii=False)}
        if plan.title:
            payload["title"] = plan.title
        _call(session, api.ExperimentsApi(session.client).patch_experiment,
              payload, plan.experiment_id)
        done.append(f"PATCH /experiments/{plan.experiment_id} — title, body "
                    f"and {len(plan.metadata.get('extra_fields') or {})} "
                    "extra fields")
    return done


def describe(plan: Plan) -> str:
    """The plan as text, for a notebook or a terminal to print verbatim."""
    lines = [f"PATCH /experiments/{plan.experiment_id}",
             f"  title    {plan.title}",
             f"  body     {len(plan.body)} characters",
             f"  metadata {len(plan.metadata.get('extra_fields') or {})} "
             "extra fields (replaced wholesale)"]
    for attachment, upload_id in plan.attachments:
        target = (f"uploads/{upload_id}" if upload_id is not None else "uploads")
        lines.append(f"POST  /experiments/{plan.experiment_id}/{target}"
                     f"  {attachment.name}  {len(attachment.data)} bytes")
    if not plan.attachments:
        lines.append("(no file uploads: every attachment already matches by "
                     "sha256)")
    return "\n".join(lines)


__all__ = ["Change", "Plan", "prepare", "apply", "describe", "DOCUMENT_NAMES",
           "pick"]
