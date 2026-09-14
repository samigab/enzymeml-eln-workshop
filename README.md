# JSON ⇄ `.eln` converter (FAIRFluids / EnzymeML v2)

Turns schema-typed JSON documents into ELN RO-Crates (`.eln`) that eLabFTW
imports as experiments with native, searchable *extra fields* — and back again.

Two dedicated converters share the crate plumbing:

| Module | Schema | Default granularity |
|---|---|---|
| `eln.fairfluids` | `fairfluids.xsd` | one entry per `Fluid` |
| `eln.enzymeml` | `enzymeML.xsd` (**v2**) | one entry per document |

## Install

Four steps, the same on Windows, macOS and Linux, and **neither Python nor
git has to be on the machine already**. Everything is driven by
[uv](https://docs.astral.sh/uv/): one tool, one command, no virtualenv to
activate by hand.

**1. Install uv**, once per machine. Copy the line for your system into a
terminal (on Windows: press the Start key, type `powershell`, press Enter):

```powershell
# Windows, in PowerShell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# Windows, if that one is refused with "running scripts is disabled"
powershell -ExecutionPolicy Bypass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

```bash
# macOS, in Terminal          (Applications > Utilities > Terminal)
# Linux, in your terminal
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Then close that window and open a new one.** The installer puts `uv` on your
PATH, and a terminal that was already running does not know about it yet. This
single step is the one that eats workshop time.

```bash
uv --version        # any 0.5.4 or newer is fine
```

**2. Get the project.** Two ways, and **git is not required**. If you have it:

```bash
git clone https://github.com/samigab/enzymeml-eln-workshop.git
cd enzymeml-eln-workshop
```

If you do not, take the ZIP instead. On
[the repository page](https://github.com/samigab/enzymeml-eln-workshop) the
blue **Code** button offers **Download ZIP**; unpack it the way you unpack
anything, and go into the folder, which will be called
`enzymeml-eln-workshop-master`. The same thing without leaving the terminal:

```powershell
# Windows, in PowerShell
iwr https://github.com/samigab/enzymeml-eln-workshop/archive/refs/heads/master.zip -OutFile workshop.zip
Expand-Archive workshop.zip -DestinationPath .
cd enzymeml-eln-workshop-master
```

```bash
# macOS / Linux
curl -L https://github.com/samigab/enzymeml-eln-workshop/archive/refs/heads/master.zip -o workshop.zip
unzip workshop.zip
cd enzymeml-eln-workshop-master
```

No `unzip` either? uv brought a Python with it, so this works anywhere:
`uv run --no-project python -m zipfile -e workshop.zip .`

Nothing in the project uses git at runtime. The only thing the ZIP costs you is
`git pull` for updates; to update, download it again.

**3. Install everything:**

```bash
uv sync
```

That is the whole installation. It creates `.venv/`, installs the exact
versions pinned in `uv.lock`, and fetches **Python 3.12** for the project,
whatever the machine happens to have. The project asks for that one minor
version rather than a floor, so the environment is the same everywhere: a
laptop carrying a very new Python, 3.14 say, would otherwise get an
untested one, and find out through a wheel that does not exist yet, halfway
through the install. There is nothing optional to remember either: one list of
dependencies covers the converter, all four notebooks, the graph widget, the
eLabFTW client and the conformance suite. Every command in this README works
from here on.

**4. Check that it worked:**

```bash
uv run python -m eln examples/workshop/kinetics.solution.json -o out/kinetics.eln
uv run test/verify_eln.py out/kinetics.eln
```

```
wrote out/kinetics.eln  (1 entry, 0 resource item(s), 5 attachment(s))
kinetics.eln: OK
```

If both lines appear, the laptop is ready. Do this the day before, not in the
room: the first `uv sync` downloads a few hundred megabytes, and a whole room
doing that at once is what conference wifi is worst at.

### Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `uv: command not found`, or PowerShell says `uv` is not recognised | The terminal predates the installer. Close it, open a new one. |
| `git: command not found` | You do not need git. Take the ZIP route in step 2. |
| Windows: `running scripts is disabled on this system` | PowerShell's execution policy. Use the second install line above, the one with `-ExecutionPolicy Bypass`. It applies to that one command and changes nothing about the machine. |
| Windows: the unpacked folder contains one folder of the same name | Windows Explorer nests an extra level. Keep going down until you see `pyproject.toml`, and run `uv sync` there. |
| macOS: `curl: command not found` | Install Apple's command line tools once: `xcode-select --install`. |
| Anything about the interpreter version | The project pins Python 3.12 and uv fetches it. If it complains anyway: `uv python install 3.12`, then `uv sync` again. |
| `ModuleNotFoundError` for anything at all | The command was run outside the project folder, or without `uv run`. Both are required: `cd` into the folder holding `pyproject.toml`, then `uv run ...`. |
| The graph panel stays blank | Reload the tab once. The view mounts before its first data arrives, and a restored session can leave it waiting. |
| Port already in use | Another notebook is still running. Close its tab and stop it with `Ctrl-C`, or pass `--port 2799`. |
| A notebook opens but shows nothing | Correct for steps 1 to 3. They stay empty until you upload a file or connect to an instance. |
| `error: No such file or directory (os error 2)` on `uv sync` | You are not in the project folder. `cd` into the one holding `pyproject.toml`. |

## Run

Each notebook is one step of the loop and starts on its own:

```bash
uv run marimo edit notebooks/00_build_document.py     # build a document
uv run marimo edit notebooks/01_export_eln.py         # document to .eln
uv run marimo edit notebooks/02_retrieve.py           # eLabFTW to document
uv run marimo edit notebooks/03_update.py             # write a correction back
```

marimo prints a `http://localhost:2718` URL and opens the browser itself.
`Ctrl-C` in the terminal stops it. Swap `edit` for `run` to present a notebook
as an app without its code cells, which is the better way to show step 0 to a
room: the graph gets the whole width.

```bash
uv run marimo run test/00_model_graph_toy.py          # the toy model, for the demo
uv run marimo run notebooks/00_build_document.py      # the same machinery, on EnzymeML
```

The command line does the same conversion without a browser. The direction
follows from the input suffix: `.json` in means export, `.eln` in means read
back.

```bash
uv run python -m eln --help

uv run python -m eln sourcefiles/fairfluids.json -o out/urea_water.eln --links
uv run python -m eln examples/enzymeml_v2.example.json -o out/kinetics.eln --links
uv run test/verify_eln.py out/urea_water.eln

uv run python -m eln out/kinetics.eln -o back.json --from entries \
    --against examples/enzymeml_v2.example.json
uv run test/roundtrip_eln.py examples/enzymeml_v2.example.json
uv run test/conformance.py out/kinetics.eln
```

Export (`.json` in):

| Flag | Effect |
|---|---|
| `--schema auto\|fairfluids\|enzymeml` | source schema (default: detected from the top-level keys) |
| `--grain auto\|fluid\|measurement\|document` | what becomes one eLabFTW entry |
| `--links` | also emit compounds/species as linked resource items |
| `--category NAME` | eLabFTW category (default: the schema name) |
| `--license URL\|TEXT` | licence at the crate root (default: "none stated", see below) |
| `--no-plots` / `--no-csv` | do not attach plots / CSV tables |
| `--no-source` | do not place the complete document at the crate root |

Import (`.eln` in):

| Flag | Effect |
|---|---|
| `--from auto\|source\|entries` | reconstruction route (default: `source`, else `entries`) |
| `--against ORIGINAL.json` | diff the result against the original |
| `--strict` | with `--against`, also count reordering and null filler as errors |

## What is in the package

An `.eln` is a ZIP with exactly one root folder:

```
urea_water/
  ro-crate-metadata.json      RO-Crate 1.2
  fluid_1/
    fairfluids.json           payload: the document, reduced to this fluid
    measurements.csv          flat data table (parameters + properties)
    plot.png                  property vs. temperature, split by composition
  fluid_2/ …
  source.document.json        complete source document (lossless round-trip)
```

Every entry is a `Dataset` node with

* `text` — an HTML summary (system, condition table, source, attachments),
* `variableMeasured` — the eLabFTW extra fields, grouped into *Measurement*,
  *System*, *Conditions*, *Provenance*, *Sample*, *Model*, *Identity*,
* `author`, `keywords`, `hasPart`, optionally `mentions` pointing at resource
  items.

The extra fields are their own `PropertyValue` nodes in the graph;
`variableMeasured` points at them with `{"@id": …}`. The important one is
`propertyID: elabftw_metadata` — the whole extra-field structure as a JSON
string, and that is what eLabFTW actually imports. The others say the same
thing again, one by one, so that a reader who does not know eLabFTW can still
make sense of them.

The `./` node also declares `version: "103"`. That is eLabFTW's internal ELN
version, and the importer branches on it: from 103 on it resolves references,
below that it expects the objects nested inline. We write 103 rather than
eLabFTW's current 107 because 103 is the lowest version whose semantics we
really implement — the only other gate sits at 104 and concerns `step`, which
we never emit.

The price: eLabFTW versions older than that branch no longer read the extra
fields. What we get for it: the nested form is not valid flattened JSON-LD,
ro-crate-py refuses to write it, and eLabFTW itself emits the reference form
today.

## Workshop material

Four steps, one notebook each, in the order the loop runs. They are separate
notebooks because the steps teach different things, and because each stays
useful on its own:

| Step | Notebook | What it does | What it does *not* know |
|---|---|---|---|
| 0 | `00_build_document.py` | build an EnzymeML document one entity at a time, next to a live graph of it | that lab notebooks exist |
| 1 | `01_export_eln.py` | upload a document, edit its provenance, get an `.eln` with extra fields, preview and round-trip | where the document came from |
| 2 | `02_retrieve.py` | connect to an instance, search it, turn entries back into documents, compare them side by side | how the entries got there |
| 3 | `03_update.py` | write a corrected document back onto the **same** entry: show the plan, check for drift, send on a button press | what was changed in the document |

That indifference is the point: the adapter hangs off a *format*, not a tool.
Whoever already has an EnzymeML or FAIRFluids document starts at step 1;
whoever has none builds one in step 0.

`test/00_model_graph_toy.py` is the same machinery as step 0 on a five-class
toy model, a company with departments and employees. It knows nothing about
enzymes, which is exactly what makes it the right thing to show first.

### Step 0, the document as a graph

Step 0 starts from nothing and asks **what a scientific data model is actually
made of**, then answers it by drawing the document while you build it.

```
your input  ──►  pyenzyme object  ──┬──►  JSON preview + download
                                    └──►  graph  ──►  layout  ──►  live view
```

Everything to the right of the object is **derived**. The graph is read off the
pydantic model with `model_fields` every time it changes, so there is no second
copy of the data to keep in step, which is also why a bug in the drawing can
never corrupt a document.

Nine steps, in the order the model wants them, because a species has to exist
before a reaction can name it and a measurement has to exist before its numbers
can hang off it:

1. **the document**, one object to hang everything else on
2. **the vessel**, where the experiment happened
3. **proteins**, the enzyme, with an EC number and a taxonomy ID
4. **small molecules**, substrate, product, cofactors, buffer
5. **the reaction**, on its own an empty box
6. **participants**, the link no database can give you: *this* protein
   catalyses *this* reaction
7. **measurements**, one run and the conditions it ran under
8. **the numbers**, bound to a species, in a unit, against a time axis
9. **who measured it**

Three kinds of edge come out of the walk over the model, and the difference
between them is most of what the notebook is for:

| line | means | example |
|---|---|---|
| solid | **contains**, a field holds an object | `EnzymeMLDocument` → `Protein` |
| dashed, amber | **references**, a field holds another object's `id` | `SmallMolecule.vessel_id` → `Vessel` |
| dotted, faint | **is a**, an instance and its type | *Lipase* → `Protein` |

The amber ones are the payload. Nothing in the JSON's nesting shows them: they
exist only because two strings match, and they are what makes the document a
graph rather than a tree. Types are separate nodes from instances, so four
small molecules are four nodes pointing at one `SmallMolecule`, and for
pyenzyme that type node carries the real JSON-LD class, `enzml:Protein`,
`OBO:PR_000000001`.

Every edit is appended to a **step log**, and the document is folded out of the
whole log rather than mutated. Undo is `log[:-1]`; the history slider is
`log[:n]`; both come free. Click a node to see its properties, edit them in
place, and watch the change travel object to JSON to graph.

Step **8, the numbers**, is the only step that adds data, and the only one that
opens an input box for it: drop a CSV on it, first column the time axis and one
column per species after it, or paste two columns in by hand. The file is read
when you press *Add SpeciesData*, not before, so filling in the form and
choosing a column never disturb each other, and it is emptied afterwards so the
next entry cannot silently inherit the previous one's series. Rows that do not
parse are skipped **and counted**, because a file quietly losing three points on
the way into a document is the failure this whole workshop is about.

There is **no kinetic model** in step 0. Rate laws and fits have a session of
their own, and the question *what did you measure* stays cleaner when it is not
mixed with *what does it mean*.

Step 1 starts **empty** — without an upload there is nothing to see, because
every number in it comes from the uploaded document rather than from a built-in
example. After that the **provenance stays editable**: title, description,
references, creators, and for FAIRFluids the citation with its authors. Those
are exactly the fields no instrument delivers and no converter can guess; the
export is the last moment before they freeze inside a lab notebook entry. What
gets exported is the edited version, the uploaded file is never written to, and
if anything changed, `modified` is stamped anew.

Step 2 goes the other way and also starts empty: nothing happens until an
instance and an API key are given. It searches through eLabFTW's query
language — `date:A..B` and `extrafield:"Group ID":…` reach exactly the fields
step 1 wrote — and turns the entries it finds back into documents. The document
comes **out of the attachment**, not computed back from the extra fields: the
fields are a projection for humans, the attachment is byte for byte what the
export put there. Everything in it is a `GET`.

Step 3 closes the loop: the same document, corrected, back onto the **same**
entry instead of beside it as a duplicate. Download-correct-reimport produced a
second entry with the same title, and nobody could say afterwards which one
counted. Instead: `PATCH /experiments/{id}` with `metadata` and `body`, plus
`POST …/uploads/{id}`, which **archives** the previous file rather than
deleting it.

Two properties of it are chosen deliberately:

* **Extra fields are replaced, not merged.** eLabFTW would offer
  `metadatamerge`; we take `metadata`. If a species leaves the document, its
  field has to leave the entry — a merge would leave it standing, looking just
  as authoritative as the rest.
* **Hence the drift check.** Before sending, what is on the instance is
  compared against what the *unmodified* document would produce. Every
  difference is something a person typed directly into the ELN — and exactly
  what the push would overwrite. It is shown, not blocked.

`prepare()` computes the complete request and sends nothing; `apply()` is a
second, explicit call. A human fits in between.

```bash
uv run marimo edit notebooks/00_build_document.py
uv run marimo edit notebooks/01_export_eln.py
uv run marimo edit notebooks/02_retrieve.py
uv run marimo edit notebooks/03_update.py
```

`notebooks/data/` holds the three raw CSVs to drop into step 0, next to the
notebooks themselves because that is where anyone looks first.
`examples/workshop/` keeps the finished document to compare against or to start
from, and `examples/seed/` four contrasting documents for step 2 to compare.
Sequence and didactics: [notebooks/README.md](notebooks/README.md).

## Round-trip

Metadata in the ELN is only worth something if the data comes back out. That
can be checked rather than claimed:

```
$ uv run test/roundtrip_eln.py examples/enzymeml_v2.example.json sourcefiles/fairfluids.json

=== enzymeml_v2.example.json ===
  source   identical
  entries  identical

=== fairfluids.json ===
  source   identical
  entries  moved    $.compound[compoundID=compound_3]: index 2 -> 3
           moved    $.compound[compoundID=compound_4]: index 3 -> 2
           2 moved
           no information lost
           (3 declared in fairfluids.EXPECTED_LOSS, not counted)
```

There are three ways back, in decreasing fidelity:

| Route | Source | Fidelity |
|---|---|---|
| `source` | `source.document.json` at the crate root | identical |
| `entries` | merge of the per-entry payloads | lossless for everything reachable from an entry |
| — | the extra fields alone | lossy in principle; reachable as `CrateEntry.fields` in order to *measure* the loss |

`source` is the comfortable route, but the uninteresting one: it reads back the
file we just copied in. `entries` is the honest test — what granularity cut
apart has to fit together again. And it is the route that still holds when a
foreign ELN has rewritten the crate, as long as it kept the attachments.

The diff classifies rather than merely compares, because the cases mean
different things: `lost` is real information loss and the only error, `changed`
is corruption, `added` are null fillers, `moved` is reordering inside an
ID-keyed list. The last two let the check pass — with `--strict` they do not.

Known, structurally unavoidable losses are declared by the schema module as
`EXPECTED_LOSS`; `roundtrip_eln.py` does not count them, so that a *new* loss
still stands out. For FAIRFluids that is the JSON-LD envelope
(`ld_id`/`ld_type`/`ld_context`): `ld_id` names the document as a whole, and a
per-fluid payload is a fragment of it — stamping it with the same identifier
would be a false claim, not a preserved one. `python -m eln --against` shows
the unfiltered diff, those three included.

## Granularity: what is *one* entry?

The most important decision in the whole tool, and not a technical one. For
EnzymeML the default is **one entry per document**. Measured on the workshop
dataset (three measurements of one dilution series):

| | one entry | one per measurement |
|---|---|---|
| lab notebook entries | 1 | 3 |
| extra field instances | 35 | 120 |
| of those, verbatim copies | 0 | 74 (61 %) |

(Counted on `examples/workshop/kinetics.solution.json`: a field instance is one
name/value pair on one entry, a verbatim copy is the same name carrying the
same value on a second entry.)

Redundancy alone would only be ugly. The real objection is that splitting
falsifies provenance: `K_m` and `k_cat` are fitted **across** the measurements —
a single measurement at 8 mM determines no `K_m`. The measurement mode writes
both into every entry anyway, so a later search for "which experiments
determined K_m" returns three hits for one determination.

The document entry lists conditions once, the varied quantity as a range
(`Ethanol — initial: 2 – 18 mmol / l`, as a text field, because a flat extra
field cannot hold a series), the parameters exactly once, all time series as
CSV, and one shared plot — only laid on top of each other do three series show
their saturation.

`--grain measurement` stays right when the document is an **aggregate**: runs
from different sessions, by different people, under genuinely different
conditions, sharing nothing but a file. Rule of thumb: granularity follows what
a human would write as *one* lab notebook entry.

## What eLabFTW actually does on import

Read against `src/Import/Eln.php` from **6.0.0-rc**, the version of the public
demo. The things that make the difference between "arrives" and "vanishes
silently":

* **`@type` has to be the string `"File"`.** The importer does
  `switch ($part['@type']) { case 'File': … }`, and in PHP an array never
  equals a string — a node typed `["File", "ImageObject"]` is skipped without
  comment. eLabFTW's own exporter writes the bare string too.
* **A wrong `sha256` means the file is dropped silently.** `verifyChecksum` and
  `checksumErrorSkip` both default to `true`.
* **Inline images go through `alternateName`.** The importer replaces that
  value literally in the entry text with the real `long_name` of the upload. We
  therefore emit a unique token as `alternateName` and reference it in the body
  as `app/download.php?f=<token>`. If the reference unexpectedly fails to
  resolve, the file is still attached to the entry, it is just not shown
  inline.
* **No `storage` parameter in the body link.** The parameter names the backend
  (1 = local disk, 2 = S3, …). We write the link offline, for a file the target
  instance has not even created yet — which backend it uses is not something we
  can know. `web/app/download.php` reads it with `getInt` and falls back to the
  instance's own `uploads_storage` configuration at 0; the comment there says
  explicitly "the download links in body won't have the storage param". A
  guessed `storage=1` cost both things on an S3 instance: the image does not
  render, and the `catch` branch of `download.php` puts a generic "an error
  occurred" into the session, which then shows up on the next page load as an
  apparently failed import.
* **`alt` does not survive filtering.** `Filter::body` allows only
  `img[src|class|style|width|height]`; HTMLPurifier removes `alt` and then sets
  it itself to `basename(src)`. The image title therefore belongs in a
  `<figcaption>`, which passes the allowlist — and that is where it is.
* **The entry text is not ours.** That is where the method goes, a note, a
  photo of the setup. The generated part is therefore wrapped in visible
  markers (`=== BEGIN GENERATED SECTION … ===`), and an update replaces only
  what is between them. Visible text rather than an HTML comment, because
  `Filter::body` runs HTMLPurifier: comments are deleted, and
  `Attr.AllowedClasses` lets no marker class through. If the marker is missing
  (entry written by hand, or imported before this change), the update appends
  instead of replacing — losing someone else's text would be worse than an old
  block that has to be deleted by hand once.
* **Image references have to be resolved by us on an API update.** The `.eln`
  importer swaps our token for the upload's real `long_name`; over the REST API
  nobody does that. A body written by PATCH with the token in it points at a
  file that does not exist — the image comes out blank. `apply()` therefore
  uploads the attachments **first**, re-reads the upload list, and only then
  resolves the body.
* **`replace` does not overwrite, it archives.** `Uploads::replace()` is
  `archive()` plus `create()` — *"attached files are immutable (change history
  is kept)"*. After an update the entry lists the previous version as archived
  next to the current one. We therefore filter on `state == 1` — on **both**
  sides. Writing without the filter replaces an archived copy and creates a
  third; *reading* without it is worse, because asking an updated entry for
  "the document" can hand back last week's version, whose extra fields no
  longer match the entry's, and step 3 then reports drift nobody caused. One
  helper, `remote.newest_by_name`, answers both: `state == 1`, highest `id` per
  name.
* **`metadata` is a string, not an object — in both directions.**
  `openapi.yaml` types the field as an object, the implementation does not:
  `EntityParams` maps `'metadata' => $this->getUnfilteredContent()`, which ends
  in `(string) $this->content`. A decoded object becomes the literal `Array`
  there — the entry's extra fields are then four characters long. We therefore
  send `json.dumps(...)`. In the other direction the API returns the string
  while the generated client expects an object and hands it to
  `__deserialize_model`; that function only copies attributes
  `if isinstance(data, (list, dict))`, so a string silently yields
  `Metadata(elabftw=None, extra_fields=None)`. We therefore read the response
  raw and parse it ourselves.
* **Not every field access is guarded.** `'link_previous_url' => $linkNode['url']`
  stands there without `??` and is reached through `mentions`. A resource node
  without `url` aborts the entire import with "An error occurred". Every
  resource item therefore carries a `url` — and one without a query string,
  because the downstream `grabIdFromUrl` reads `$queryParams['id']`
  unguarded as well.

## Why a foreign library

The graph is no longer assembled by hand but built with ro-crate-py. The gain
is not convenience but contradiction: the library enforces flattened JSON-LD —
every nested object has to be an `{"@id": …}` reference — and on the first run
it rejected two nodes of ours that eLabFTW had been quietly skipping
(`sdPublisher` as an anonymous object; `if (!array_key_exists('@id', ...)) continue;`).

The ZIP step stays here nonetheless. `ROCrate.write_zip` puts
`ro-crate-metadata.json` at the archive root, while an `.eln` must have exactly
one root folder — the first thing the consortium's conformance check tests.
**The library writes RO-Crate, not `.eln`**; those are not the same thing, and
`eln/crate.py` is where the difference lives.

### Being graded by someone else

`vendor/elnconsortium/` contains the ELN Consortium's test suite, verbatim and
pinned to a commit (MIT). It is the same code that runs behind their CI and
their web checker:

```bash
uv run test/conformance.py out/kinetics.eln
```

```
=== kinetics.eln
  ok    Archive structure
  ok    Pypi RO-Crate
  ok    Parameters metadata json
  ok    Schema
  note  Validator  (declared deviation)
```

An export that only passes `verify_eln.py` has been graded by whoever wrote the
exam. The foreign suite found three things we had missed: the `sdPublisher`
node, a missing `license` at the crate root (RO-Crate requires it), and
resource items sitting in `hasPart` as `Dataset` without the folder existing in
the archive.

Two findings remain and are justified in `conformance.py` as `DECLARED` rather
than pushed away: the consortium's schema types `author` as an object with no
array variant (an entry with two authors fails), and their SHACL validator is
pinned to the 1.1 profile while we, like eLabFTW, declare 1.2. A check whose
messages do *not* all match a justification still fails — the declaration
cannot swallow a regression.

### Licence

RO-Crate requires a `license` at the root, and neither `enzymeML.xsd` nor
`fairfluids.xsd` has a field for one. Without `--license` the export therefore
writes *no* invented licence, but the statement that none was named and that
one should ask before reuse — the specification explicitly allows a textual
description in that place. Stamping CC-BY onto someone else's measurements
because a validator wants to see a value would be granting rights that were
never granted to us.

## EnzymeML: v2 only

The EnzymeML converter assumes the v2 model from `enzymeML.xsd`
(`small_molecules`, `creators` as a list, `species_data` in the measurements).
A v1 document is rejected with an explicit message instead of silently
producing empty entries:

```
$ uv run python -m eln sourcefiles/enzymeML.json -o out.eln
error: This looks like an EnzymeML v1 document, but this converter targets
EnzymeML v2 as defined by enzymeML.xsd.
  v1 markers found: creators (object instead of list), level, pubmedid, reactants, …
  Convert it first, e.g. with pyenzyme v2, then re-run.
```

The bundled `enzymeML.json` is exactly such a v1 document. For testing the v2
path there is a hand-written v2 version of it under
`examples/enzymeml_v2.example.json`.

## Modules

```
eln/crate.py       schema-agnostic: Entry/Resource/Attachment, extra fields,
                   RO-Crate graph (via ro-crate-py), ZIP output
eln/read.py        the other direction: .eln → crate/entries/payloads, merge
eln/diff.py        classifying JSON comparison for the round-trip
eln/util.py        unit rendering (UnitDefinition → label), CSV, plots
eln/fairfluids.py  FAIRFluids mapping
eln/enzymeml.py    EnzymeML v2 mapping
eln/remote.py      read-only eLabFTW API: connect, search, fetch (notebook 2)
eln/remote_write.py  plan/apply an update of an existing entry (notebook 3)
eln/__main__.py    CLI

modelgraph/store.py    the append-only step log, and the entities it replays into
modelgraph/graph.py    a pydantic object → nodes and edges, by reflection
modelgraph/layout.py   where every node goes; deterministic, so nothing jumps
modelgraph/widget.py   the anywidget wrapper
modelgraph/static/     ~300 lines of ES module that imports nothing
modelgraph/forms.py    marimo inputs generated from the field declarations
modelgraph/toy.py      the five-class demo model (phase 1)
modelgraph/enzymeml.py the same declarations against pyenzyme (phase 2)

test/verify_eln.py     structural check of a generated .eln (our expectations)
test/conformance.py    the same file, graded by the ELN Consortium's suite
test/roundtrip_eln.py  export → import → diff, per route
test/workshop_todo.py  which metadata fields of a document are still open
test/seed_demo.py      builds examples/seed/ and pushes it to an instance
test/00_model_graph_toy.py  step 0's machinery on a five-class toy model

notebooks/README.md    the workshop handbook: four steps, install, demo instance
notebooks/data/        the three CSVs step 0 reads
examples/workshop/     the finished document and a metadata-free skeleton of it
examples/seed/         four contrasting documents, so step 2 has something to
                       compare. See its README
sourcefiles/           the upstream schemas and the documents bundled with them
vendor/                foreign code, verbatim and pinned — do not edit
```

Wiring up a new schema means: write a module with `SCHEMA`, `PUBLISHER`,
`detect(doc)`, `title(doc)` and `convert(doc, …) -> (entries, resources)`, and
register it in `CONVERTERS`. For the way back, `reassemble(payloads)` and
`EXPECTED_LOSS` are added — both schema modules build `reassemble` out of
`merge_documents()` by declaring only which lists are merged by ID, appended,
or deduplicated.

`matplotlib` is needed only for the plots and is optional — without it,
`plot.png` is silently omitted and the rest of the export is untouched.
