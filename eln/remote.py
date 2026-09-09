"""Read documents back out of a running eLabFTW instance over its REST API v2.

The counterpart to :mod:`eln.crate`: that module turns a document into a file
you carry to a lab notebook, this one fetches it back from the lab notebook it
was carried to. Both notebooks that talk to an instance share this module for
the same reason the export notebook shares :func:`eln.convert_document` — a
connection, an experiment and a document should mean one thing, not two.

``elabapi-python`` is eLabFTW's own generated client and is used as-is. Where
it is awkward we take its documented escape hatch rather than starting a second
HTTP stack: binary responses (an ``.eln``, an attachment) come back through
``_preload_content=False``, which hands over the raw urllib3 response instead of
trying to deserialise the bytes into a model object.

**This module only reads.** Every function here is a GET. Writing back to an
instance is a different kind of act — it changes somebody's record — and lives
in :mod:`eln.remote_write`, which asks before it sends.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Optional

from . import CONVERTERS, pick

#: Attachment names the exporter writes, one per schema. Looked for first when
#: fetching a document back, before falling back to sniffing every JSON upload.
DOCUMENT_NAMES = tuple(f"{schema}.json" for schema in CONVERTERS)

#: eLabFTW's advanced-search fields we use, for the notebook's help text. The
#: grammar lives in ``src/node/grammar/queryGrammar.pegjs`` upstream.
QUERY_EXAMPLES = (
    ("date:2026-09-01..2026-09-30", "everything from September"),
    ('extrafield:"Group ID":dilution_series_1', "one dilution series"),
    ('extrafield:"Organism":"Saccharomyces cerevisiae"', "by organism"),
    ("title:ADH", "title contains ADH"),
    ("author:muster", "by who wrote it"),
)


class RemoteError(RuntimeError):
    """An instance said no, in a way worth reading rather than a traceback."""


@dataclass(frozen=True)
class Session:
    """A configured connection, plus who it turned out to belong to.

    ``whoami`` is not decoration. A token identifies a person, and on a shared
    instance the difference between *your* entries and *everyone's* is the only
    thing standing between a correction and an accident.
    """
    client: Any
    url: str
    whoami: str
    userid: Optional[int] = None

    def __str__(self) -> str:
        who = f"{self.whoami} (user {self.userid})" if self.userid else self.whoami
        return f"{who} at {self.url}"


def _field(obj: Any, *names, default=None):
    """First of ``names`` that the object carries, from a model or a dict.

    Two spellings are needed because the generated client renames properties
    that collide with something in Python: an experiment's ``date`` arrives as
    ``_date``. Asking for both is cheaper than remembering which endpoint
    returns a model and which a plain dict.
    """
    for name in names:
        value = (obj.get(name) if isinstance(obj, dict)
                 else getattr(obj, name, None))
        if value is not None:
            return value
    return default


def _api():
    """Import the client lazily, with an explanation instead of an ImportError.

    The converter core has no business requiring an HTTP client: exporting an
    ``.eln`` never touches a network, and someone who only exports should not
    have to install one.
    """
    try:
        import elabapi_python
    except ImportError:  # pragma: no cover - depends on the install
        raise RemoteError(
            "elabapi-python is not installed, so no instance can be reached.\n"
            "  uv run --group api marimo edit notebooks/02_retrieve.py\n"
            "installs it. Exporting an .eln does not need it."
        ) from None
    return elabapi_python


class _NoPool:
    """Stands in for a thread pool that was shut down and is never used."""

    def close(self) -> None:
        pass

    def join(self) -> None:
        pass


def _drop_thread_pool(client: Any) -> None:
    """Shut down the worker threads ``ApiClient.__init__`` starts unasked.

    The generated client creates a ``multiprocessing.pool.ThreadPool`` — one
    worker per CPU — in its constructor, for the ``async_req=True`` code path.
    We never take that path: every call here is synchronous. Two costs follow
    from leaving it alone, and a notebook pays both repeatedly, because this
    cell re-runs on every keystroke in the token field:

    * a dozen threads per connection attempt, none of which ever get work;
    * ``ApiClient.__del__`` closes the pool, which raises ``OSError: Bad file
      descriptor`` when the collection happens during interpreter shutdown —
      an alarming traceback for something that is nothing at all.

    So the pool is stopped at construction and replaced by an object whose
    close and join do nothing, leaving ``__del__`` something harmless to call.
    """
    pool = getattr(client, "pool", None)
    if pool is None or isinstance(pool, _NoPool):
        return
    try:
        pool.terminate()
        pool.join()
    except Exception:  # pragma: no cover - shutdown races are not our problem
        pass
    client.pool = _NoPool()


def _fail_fast(client: Any, retries: int) -> None:
    """Stop urllib3 retrying a hostname that will not start existing.

    Its default is three retries with exponential backoff. Behind a script
    that is a kindness; in front of a person who mistyped a URL it is twelve
    seconds of nothing, followed by three warnings that read like a crash.
    A notebook is the second case: the URL is being typed, so getting it
    wrong is the normal state, and the answer needs to come back while the
    typo is still on screen.
    """
    try:
        import urllib3

        pool = client.rest_client.pool_manager
        pool.connection_pool_kw["retries"] = urllib3.util.Retry(
            total=retries, backoff_factor=0, respect_retry_after_header=False)
    except Exception:  # pragma: no cover - a slow failure is still a failure
        pass


def normalise_url(url: str) -> str:
    """Accept what people paste, return what the client needs.

    People paste the address from their browser bar. The client wants the API
    root. Both spellings are reasonable; only one of them works.
    """
    url = url.strip().rstrip("/")
    if not url:
        raise RemoteError("No instance URL given.")
    if "://" not in url:
        url = "https://" + url
    if not url.endswith("/api/v2"):
        url += "/api/v2"
    return url


def connect(url: str, token: str, *, verify_ssl: bool = True,
            timeout: int = 30, retries: int = 1) -> Session:
    """Configure a client and prove the token works before handing it back.

    The proof is a ``GET /users/me``: cheap, authenticated, and it answers the
    question the caller actually has — not "is the server up" but "who am I
    on it".
    """
    api = _api()
    if not token.strip():
        raise RemoteError(
            "No API key given. Create one in eLabFTW under User panel → API "
            "keys. Read-only is enough for this notebook.")

    config = api.Configuration()
    config.host = normalise_url(url)
    config.api_key["Authorization"] = token.strip()
    config.verify_ssl = verify_ssl
    config.debug = False

    client = api.ApiClient(config)
    client.set_default_header("Authorization", token.strip())
    _drop_thread_pool(client)
    _fail_fast(client, retries)

    try:
        me = api.UsersApi(client).read_user("me", _request_timeout=timeout)
    except Exception as exc:
        raise RemoteError(_explain(exc, config.host)) from None

    return Session(
        client=client,
        url=config.host,
        whoami=_field(me, "fullname", "email", default="?"),
        userid=_field(me, "userid"),
    )


def _explain(exc: Exception, url: str) -> str:
    """Turn a client exception into a sentence that says what to do."""
    status = getattr(exc, "status", None)
    if status == 401:
        return (f"{url} refused the API key. Check that it was copied whole "
                "and has not expired.")
    if status == 403:
        return f"{url} accepted the key but forbids this action."
    if status == 404:
        return (f"{url} has no such entry — or the URL is not an eLabFTW API "
                "root. It should end in /api/v2.")
    if status is not None:
        return f"{url} answered {status}: {getattr(exc, 'reason', '') or exc}"
    return f"{url} could not be reached: {exc}"


def _call(session: Session, fn, *args, **kwargs):
    """Run a client call, converting its exceptions into RemoteError."""
    try:
        return fn(*args, **kwargs)
    except RemoteError:
        raise
    except Exception as exc:
        raise RemoteError(_explain(exc, session.url)) from None


def _raw(session: Session, fn, *args, **kwargs) -> bytes:
    """A call whose response is a file rather than a model object.

    ``_preload_content=False`` is the generated client's own way of saying
    "hand me the response, do not try to parse it" — without it the client
    attempts to deserialise a ZIP into a dataclass.
    """
    response = _call(session, fn, *args, _preload_content=False, **kwargs)
    return response.data


def search(session: Session, *, q: str = "", extended: str = "",
           limit: int = 25, offset: int = 0, scope: Optional[int] = None,
           order: str = "", sort: str = "") -> list[dict]:
    """List experiments the token can see.

    ``q`` searches title, body and elabid; ``extended`` is eLabFTW's advanced
    query language, which is where dates and extra fields become searchable —
    see :data:`QUERY_EXAMPLES`.
    """
    api = _api()
    kwargs: dict[str, Any] = {"limit": limit, "offset": offset}
    if q.strip():
        kwargs["q"] = q.strip()
    if extended.strip():
        kwargs["extended"] = extended.strip()
    if scope is not None:
        kwargs["scope"] = scope
    if order:
        kwargs["order"] = order
    if sort:
        kwargs["sort"] = sort

    found = _call(session, api.ExperimentsApi(session.client).read_experiments,
                  **kwargs)
    return [_summary(e) for e in found or []]


def _summary(experiment: Any) -> dict:
    """The handful of columns a list view needs, from a model or a dict."""
    return {
        "id": _field(experiment, "id"),
        "title": _field(experiment, "title", default=""),
        # `_date` first: that is what the generated Experiment model calls it.
        "date": _field(experiment, "_date", "date", default=""),
        "created": _field(experiment, "created_at", default=""),
        "modified": _field(experiment, "modified_at", default=""),
        "owner": _field(experiment, "fullname", default=""),
        "category": _field(experiment, "category_title", default=""),
        "status": _field(experiment, "status_title", default=""),
    }


def uploads(session: Session, experiment_id: int) -> list[dict]:
    """The files attached to an experiment."""
    api = _api()
    found = _call(session, api.UploadsApi(session.client).read_uploads,
                  "experiments", experiment_id)
    return [{
        "id": _field(upload, "id"),
        "name": _field(upload, "real_name", default=""),
        # The name on disk, and therefore the only thing `app/download.php?f=`
        # resolves. An entry body that wants to show an image has to name it.
        "long_name": _field(upload, "long_name", default=""),
        "comment": _field(upload, "comment", default=""),
        "size": _field(upload, "filesize", default=0),
        "hash": _field(upload, "hash", default=""),
        # 1 Normal, 2 Archived, 3 Deleted (src/Enums/State.php). Replacing a
        # file archives the old one rather than overwriting it, so a list of
        # uploads accumulates versions and only the Normal one is current.
        "state": _field(upload, "state", default=1),
    } for upload in found or []]


#: The upload state that means "this is the current file".
STATE_NORMAL = 1


def download(session: Session, experiment_id: int, upload_id: int) -> bytes:
    """One attachment, as bytes."""
    api = _api()
    return _raw(session, api.UploadsApi(session.client).read_upload,
                "experiments", experiment_id, upload_id, format="binary")


def fetch_eln(session: Session, experiment_id: int) -> bytes:
    """The whole experiment as an ``.eln`` package, eLabFTW's own export.

    Note whose crate this is: eLabFTW built it, not us. It is the richer
    answer — body, comments, steps, every upload — but its layout is theirs.
    :func:`fetch_document` is the narrower and more certain route.
    """
    api = _api()
    return _raw(session, api.ExperimentsApi(session.client).get_experiment,
                experiment_id, format="eln")


def fetch_document(session: Session, experiment_id: int) -> tuple[dict, dict]:
    """The source document attached to an experiment. Returns (doc, upload).

    Deliberately *not* reconstructed from the extra fields. The fields are a
    projection built for humans to read and search; the attachment is the
    document itself, byte for byte as the export left it. Reading back what we
    know is there beats re-deriving it from a lossy view of itself.
    """
    attached = uploads(session, experiment_id)
    if not attached:
        raise RemoteError(
            f"Experiment {experiment_id} has no attachments, so it carries no "
            "document. Extra fields alone cannot be turned back into one — "
            "they are a summary, not the record.")

    by_name = {u["name"]: u for u in attached}
    candidates = [by_name[n] for n in DOCUMENT_NAMES if n in by_name]
    candidates += [u for u in attached
                   if u["name"].endswith(".json") and u not in candidates]

    problems = []
    for upload in candidates:
        try:
            doc = json.loads(download(session, experiment_id, upload["id"]))
            pick(doc)  # raises unless a converter recognises it
            return doc, upload
        except RemoteError:
            raise
        except Exception as exc:
            problems.append(f"{upload['name']}: {exc}")

    listed = ", ".join(u["name"] for u in attached) or "none"
    raise RemoteError(
        f"None of the attachments of experiment {experiment_id} is an "
        f"EnzymeML or FAIRFluids document.\n  attachments: {listed}"
        + ("\n  " + "\n  ".join(problems) if problems else ""))


def extra_field_keys(session: Session, q: str = "", limit: int = 0) -> list[dict]:
    """Which extra-field names exist on this instance, by frequency.

    The answer to "what can I actually filter on here", which is otherwise
    guesswork against somebody else's naming.
    """
    api = _api()
    found = _call(session, api.CustomFieldsKeysApi(session.client).custom_fields_keys,
                  q=q, limit=limit)
    return [{"key": _field(key, "extra_fields_key", "id", "key", default=""),
             "count": _field(key, "frequency", "cnt", "count", default=0)}
            for key in found or []]
