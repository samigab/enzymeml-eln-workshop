# Talk: data and metadata belong together — in structured form

Slide-by-slide notes for the lecture part of the workshop. Roughly **50–60
minutes**, followed by the hands-on session with the notebooks.

These notes are written in English to match the rest of the repository; deliver
them in whatever language the room speaks. Each slide has **On the slide**
(what the audience sees) and **Say** (the argument). Where a claim is checkable,
the source is named — the point of the whole talk is that claims should be
checkable, so it would be poor form not to.

Everything stated here as fact was verified against a source: eLabFTW behaviour
against its PHP source at 6.0.0-rc, format support against the ELN Consortium's
own support table, numbers against a run of this repository. Two claims are
marked **check before the talk** because they describe other people's roadmaps,
which move.

| Part | Slides | Minutes |
|---|---|---|
| A — Why | 1–5 | 10 |
| B — RO-Crate and `.eln` | 6–11 | 12 |
| C — The two schemas and the mapping | 12–17 | 13 |
| D — Install and run | 18–19 | 5 |
| E — The three scenarios | 20–24 | 12 |
| F — Other ELNs, limits, outlook | 25–29 | 10 |

---

## Part A — Why

### Slide 1 — Title

**On the slide**
Title, your name, affiliation, date. Underneath, one sentence:
*"Your data and your metadata are in two different places. This is about
putting them in one — without typing anything twice."*

**Say**
Set the promise for the three hours: by the end, everyone will have taken a
structured document, pushed it into a lab notebook as a searchable entry, and
got the document back out unchanged. Not a demo — their own file, on their own
machine.

---

### Slide 2 — What an ELN actually is

**On the slide**
Three bullets, no logos:
* a lab notebook that is searchable, timestamped and shareable
* a database of *entries* (experiments) and *resources* (compounds, devices,
  protocols)
* an access-control and audit layer around both

**Say**
Start from what people have: a paper notebook, or a folder of `final_v3.xlsx`.
An ELN is not a better text editor — the thing it adds is that entries have
*structure*: fields, links, timestamps, permissions, an audit trail.

Name the honest failure mode: most ELN adoption produces a *digital paper
notebook*. People paste a screenshot and write a paragraph. Everything is
findable by full-text search and nothing is findable by query. You can grep for
"pH 8.8" but you cannot ask for "every measurement between pH 8 and 9".

That gap — between text about an experiment and structure describing it — is
the subject of the whole workshop.

---

### Slide 3 — Data vs. metadata

**On the slide**
A two-column split of the same experiment:

| Data | Metadata |
|---|---|
| `t = 0, 2, 4, … min` | measured in a 1 cm quartz cuvette |
| `A₃₄₀ = 0.00, 0.19, 0.34 …` | pH 8.8, 25 °C |
| 11 time points × 3 runs | enzyme: ADH1, EC 1.1.1.1, *S. cerevisiae*, UniProt P00330 |
| | ethanol, InChIKey `LFQSCWFLJHTTHZ-UHFFFAOYSA-N` |
| | measured by …, on …, method DOI … |

**Say**
Data is what the instrument produced. Metadata is everything you need in order
to know what the data means.

The asymmetry worth pointing out: the instrument gives you the left column for
free, and nothing at all in the right column. Every single line on the right is
something a human knows and has to record. That is why the right column is the
one that goes missing — not because it is unimportant, but because it is the
only part that is *work*.

And it is the column that determines whether the data is reusable. A time
series without the right column is a list of numbers. The `F` in FAIR is not
about the data.

---

### Slide 4 — The second axis: structured vs. prose

**On the slide**
The same metadata, twice:

> *Left:* "The reaction was carried out in 50 mM phosphate buffer at pH 8.8 and
> 25 °C in a 1 cm quartz cuvette, using alcohol dehydrogenase from baker's
> yeast."

> *Right:*
> `pH = 8.8` · `Temperature = 25 °C` · `Vessel = quartz cuvette 1 cm` ·
> `Enzyme = ADH1` · `EC number = 1.1.1.1` · `Organism = Saccharomyces cerevisiae`

Under it: **Both are metadata. Only one is queryable.**

**Say**
This is the slide the whole talk turns on. Most people think the problem is
*missing* metadata. Usually the metadata is there — it is in the method
paragraph. The problem is that it is in a form only a human can read.

Three consequences, in increasing order of annoyance:
1. You cannot query it. "All measurements at pH 8.8 with *S. cerevisiae* ADH"
   is not a search you can run over prose.
2. You cannot aggregate it. Twenty entries in twenty phrasings do not become a
   table.
3. You cannot check it. Nothing notices that one entry says 8.8 and another
   says 8,8 and a third says "slightly alkaline".

The right-hand form costs no more work than the left-hand one. It costs
*different* work: a decision about which fields exist, made once.

---

### Slide 5 — And the third thing: they have to stay together

**On the slide**
Three boxes with arrows, each labelled with its failure:

* `data only` → **uninterpretable** in two years
* `metadata only, in prose` → **unsearchable**, and it drifts from the data
* `data + structured metadata, in one package` → the target

**Say**
The usual state of affairs is not "no metadata". It is that the numbers live in
a CSV on a share, the interpretation lives in an ELN entry, and the two are
connected by a filename that somebody renamed in 2024.

The point of the format we are about to look at is precisely this: one package,
one checksum, both halves. If you move it, both move. If somebody hands it to
you, you got both.

Transition: *so what does such a package look like?*

---

## Part B — RO-Crate and the `.eln` file format

### Slide 6 — RO-Crate in one slide

**On the slide**
```
my-crate/
  ro-crate-metadata.json     ← the description
  data.csv                   ← the things being described
  plot.png
```
Under it: **A folder + one JSON-LD file that describes everything in it.**

**Say**
RO-Crate is deliberately unambitious, and that is its strength. It is a folder
of files plus one metadata file, `ro-crate-metadata.json`, written in JSON-LD
using [schema.org](https://schema.org) vocabulary.

It is not a database, not a server, not a standard you have to join. If you can
make a ZIP and write JSON, you can make an RO-Crate. It is readable by a human
in a text editor and by a machine as a graph.

What it gives you: every file in the package has a node saying what it is, who
made it, what it belongs to, and what its checksum is. Nothing is implicit in a
filename.

---

### Slide 7 — What is actually inside ours

**On the slide**
Real numbers from `out/kinetics.eln`, generated in the workshop:

```
kinetics/
  ro-crate-metadata.json          49 nodes
  document/
    enzymeml.json                 the source document
    timecourse_m0.csv             one flat table per measurement
    timecourse_m1.csv
    timecourse_m2.csv
    plot.png                      all three runs, overlaid
  source.document.json            the complete original, byte for byte
```
Node types: `Dataset` 2 · `File` 6 · `PropertyValue` 36 · `Person` 1 ·
`Organization` 1 · `CreativeWork` 2 · `Thing` 1

**Say**
Walk them through the numbers rather than the concept. 36 of the 49 nodes are
`PropertyValue` — that is the structured metadata from slide 4, one node per
field. Those become native searchable fields in the lab notebook.

Two things worth pointing at explicitly:

* **`source.document.json`** — the complete original, unmodified. That is what
  makes the round-trip exact rather than approximate. Cheap insurance: one more
  file in a ZIP.
* **the CSVs and the plot** — derived, not authoritative. They exist so that a
  human opening the entry sees something, and so that a tool that does not
  speak EnzymeML still gets a table.

---

### Slide 8 — `.eln` = RO-Crate in a ZIP, with one rule

**On the slide**
> An `.eln` file is a ZIP containing **exactly one root folder**, which is an
> RO-Crate.
>
> IANA media type: `application/vnd.eln+zip`

**Say**
That is the entire specification difference. One root folder — not the crate at
the archive root.

Worth a moment because it is the first thing the consortium's conformance
checker tests, and because it is the one place where a general-purpose RO-Crate
library will let you down: `ro-crate-py` writes the metadata file at the archive
root. The library writes RO-Crate; it does not write `.eln`. In this repository
that difference lives in exactly one file, `eln/crate.py`, and it is commented
as such.

Small point, general lesson: "we used the standard library for it" is not the
same as "we conform".

---

### Slide 9 — Who supports it

**On the slide**
The support table, copied from the consortium (as of the check date):

| ELN | import | export |
|---|---|---|
| eLabFTW | ✅ | ✅ |
| Kadi4Mat | ✅ | ✅ |
| PASTA | ✅ | ✅ |
| SampleDB | ✅ | ✅ |
| RSpace | ✅ | ✅ |
| OpenSemanticLab | ✅ | ✅ |
| SciLog | ✅ | ✅ |
| NOMAD | ✅ | — |
| LinkAhead | ✅ | — |
| datalab | — | ✅ |

Source: <https://github.com/TheELNConsortium/TheELNFileFormat>

**Say**
Ten implementations, seven of them both ways. That is a small number and an
honest one — say so. It is not a universal standard; it is a working agreement
among the people who showed up.

But note what the shape of the table means for a user: **your exit door is
already built**. Five ELNs can both read and write it, so moving from one to
another is an export and an import rather than a migration project. That
argument is worth more to a lab head than any feature.

---

### Slide 10 — Which part of what we built is universal

**On the slide**
Two columns:

| Works in any `.eln` reader | eLabFTW-specific |
|---|---|
| the ZIP + single-root-folder layout | the `elabftw_metadata` field blob |
| the RO-Crate graph, schema.org vocabulary | `version: "103"` (their importer's branch point) |
| one `Dataset` node per entry | inline images via `alternateName` tokens |
| attachments + sha256 checksums | `app/download.php?f=…` links in the body |
| the HTML summary in `text` | resource items via `mentions` + `url` |
| **`variableMeasured` — every field as a `PropertyValue`** | the whole REST API layer (`eln/remote*.py`) |
| `source.document.json` and the round-trip | |

**Say**
This is the slide to be scrupulous on, because it is where a talk like this
usually oversells.

Every field is emitted **twice**: once as a standard schema.org `PropertyValue`
in `variableMeasured`, which any RO-Crate reader can walk, and once packed into
a single `elabftw_metadata` property, which is the form eLabFTW's importer
actually consumes to build native fields.

So: import our file into Kadi4Mat or SampleDB and you get the entry, the
attachments, the summary and the source document. What you do *not*
automatically get is that ELN's native typed fields — because each ELN has its
own notion of what a field is, and no one has standardised that yet. The
information is there in a readable form; the last-mile mapping is per-ELN.

Being clear about this is the difference between a tool and a claim.

---

### Slide 11 — Which routes exist, and what each costs

**On the slide**
```
        ┌──────────────────┐
        │ structured doc   │  EnzymeML v2 / FAIRFluids JSON
        └────────┬─────────┘
                 │
      ┌──────────┴──────────┐
      │                     │
  (1) .eln file        (2) REST API
   any consortium ELN    eLabFTW only
   no credentials        needs a key
   new entry each time   updates in place
      │                     │
      └──────────┬──────────┘
                 ▼
          ┌─────────────┐
          │ ELN entry   │
          └──────┬──────┘
                 │  (3) read back — from the attachment, exact
                 │  (4) read back — from the extra fields, lossy
                 ▼
        ┌──────────────────┐
        │ structured doc   │
        └──────────────────┘
```

**Say**
Four routes; the interesting thing is what each one is *for*.

1. **File.** Works everywhere, needs no account, no network, no trust. This is
   the route for handing data to a collaborator or an archive.
2. **API.** eLabFTW only, but it can hit an entry that already exists. That is
   the difference between "correct the record" and "add another version of the
   record beside it".
3. **Back from the attachment.** Exact, because it is the file we put there.
4. **Back from the extra fields.** Structurally lossy — a flat field cannot
   hold a time series. We keep this route anyway, not to use it, but to
   *measure* the loss: it is how you find out what the projection to fields
   actually throws away.

Route 4 is the honest one. Most tools that summarise into fields never check
what the summary dropped.

---

## Part C — The two schemas, and the mapping

### Slide 12 — EnzymeML v2 and FAIRFluids

**On the slide**

| | EnzymeML v2 | FAIRFluids |
|---|---|---|
| domain | enzyme kinetics | thermophysical properties of fluids |
| the unit of interest | a document: vessel, species, reaction, measurements | a `Fluid`: composition + property series |
| identifiers it carries | InChIKey, UniProt, EC, NCBI taxon, Rhea | compound identifiers, citation |
| default granularity here | one entry per document | one entry per fluid |

**Say**
Two schemas from different communities, chosen deliberately to make the point
that the adapter is not about one of them.

Both are *typed*: they have a schema (`enzymeML.xsd`, `fairfluids.xsd`) that
says what a document may contain. That is the property the whole thing rests
on — not that it is JSON, but that the JSON has a known shape, so a converter
can be written once instead of per file.

If you have a third schema, wiring it in means one module with five functions.
Named on the last slide.

---

### Slide 13 — How the mapping works

**On the slide**
One example field, traced end to end:

```
  document:  measurements[0].ph = 8.8
                    │
                    ▼
  crate:     PropertyValue { name: "pH", value: "8.8", propertyID: … }
             + packed into elabftw_metadata, group "Conditions"
                    │
                    ▼
  eLabFTW:   extra field  [Conditions] pH = 8.8   (type: number)
                    │
                    ▼
  search:    extrafield:"pH":8.8
```

**Say**
The mapping is a set of decisions, not an algorithm, and that is why it is a
human-written module per schema rather than a generic flattener.

Three kinds of decision it makes:
* **which fields exist at all** — 35 for our workshop document. Not 400; the
  document has more leaves than that. A field earns its place by being
  something someone would search for.
* **which group it belongs to** — Measurement, System, Conditions, Provenance,
  Sample, Model, Identity. Groups are what make 35 fields readable instead of a
  wall.
* **how to render a value a flat field cannot hold.** Three runs at 2, 8 and
  18 mM become one text field: `Ethanol — initial: 2 – 18 mmol / l`. A range,
  as prose, deliberately — because the alternative is three fields that look
  like three experiments.

That last one is the honest edge of the approach, and worth saying out loud:
the field layer is a *projection for humans and search*. The attachment stays
authoritative.

---

### Slide 14 — Identifiers are what make the fields worth having

**On the slide**
Before and after, both real output of `eln.enzymeml` on the workshop dataset:

```
skeleton  →  23 fields, entry titled "EnzymeML document"
             Species = s_etoh, NAD+, s_acetald, NADH, p_adh

solution  →  35 fields, entry titled "ADH-Kinetik: Ethanoloxidation …"
             Species     = Ethanol, NAD+, Acetaldehyd, NADH, Alkoholdehydrogenase 1
             Enzyme      = Alkoholdehydrogenase 1
             EC number   = 1.1.1.1
             Organism    = Saccharomyces cerevisiae
             Taxonomy ID = 559292
             Ethanol — InChIKey = LFQSCWFLJHTTHZ-UHFFFAOYSA-N
```

**Say**
This is the moment in the hands-on where the point lands, so seed it here.

The participants will export once *before* filling anything in. The entry works.
It is structured. It has 23 fields. And it is useless — the entry is called
"EnzymeML document" and half the species show their internal IDs, right next to
the two cofactors that came pre-annotated. The difference sits side by side in a
single field. Structure without identifiers is just tidier noise.

Then the same field after two lookups: `RHEA:25290` returns the whole reaction
with five molecules and their InChIKeys, `P00330` returns the enzyme with EC
number, organism and sequence. Two identifiers typed; forty values filled.

And the payoff is not this entry. It is that in slide 22 we put two entries side
by side and the species line up — because they came from a registry rather than
from each experimenter's habits. Had everyone invented their own names, that
comparison table would be a diagonal of ones.

---

### Slide 15 — Why not just maintain the ELN entry?

**On the slide**
> "The entry has all the fields. Why keep a document too?"

Three answers:
* the entry is a **projection**; the document is the **source**
* a flat field cannot hold a time series — the numbers would have nowhere to go
* you cannot feed an ELN entry to a model fitter

**Say**
This is the objection you will get, and it is a reasonable one. Answer it in
that order.

**Projection.** 35 fields came out of a document with hundreds of leaves. That
is a feature — but it means the entry cannot be the source, because rebuilding
the document from the entry loses whatever did not earn a field. We can prove
this rather than assert it: route 4 on slide 11 exists precisely to measure it.

**Structure.** The time series is 11 points × 3 runs × 2 species. There is no
flat field that holds that. Maintain only the entry and the numbers live
somewhere else again — which is exactly the split from slide 5 that we set out
to close.

**Reuse.** The next session in this workshop fits a kinetic model. That needs a
document, not an entry. If the entry is the only artefact, every downstream
analysis begins with re-typing.

The shape to aim for: **the document is the source of truth, the entry is how
humans and search find it, and one command keeps them in sync.**

---

### Slide 16 — And why not one entry per measurement?

**On the slide**
Measured on `examples/workshop/kinetics.solution.json`:

| | one entry per document | one per measurement |
|---|---|---|
| lab notebook entries | 1 | 3 |
| extra field instances | 35 | 120 |
| of those, verbatim copies | 0 | 74 (61 %) |

**Say**
The redundancy is the small problem. The real one is provenance.

`K_m` and `k_cat` are fitted **across** the three runs — a single measurement at
8 mM determines no `K_m`. Split into three entries, and both parameters get
written into each. Now search for "which experiments determined K_m" and you get
three hits for one determination. The tool has manufactured evidence.

So the rule is not "fewer entries is better". It is: **granularity follows what
a human would write as one lab notebook entry.** Three runs of one dilution
series on one afternoon are one entry. Runs from different sessions by different
people that happen to share a file are an aggregate — and for those,
`--grain measurement` is right.

The tool has a flag. The decision is not technical.

---

### Slide 17 — What eLabFTW actually does with the file

**On the slide**
Four findings, each with its source line:

* `@type` must be the **string** `"File"` — a `["File","ImageObject"]` array is
  skipped silently (`switch` on a string, in PHP)
* wrong `sha256` → file dropped silently (`checksumErrorSkip` defaults true)
* `alt` on an image does not survive the HTML filter — the caption has to be a
  `<figcaption>`
* `metadata` is a **string** on the wire, in both directions, although the
  OpenAPI spec types it as an object

**Say**
Two minutes, and it is not a digression — it is the methodological point of the
whole project.

Every one of these was found by reading eLabFTW's PHP source, not by guessing
and retrying against the server. Each of them fails *silently*: the import
succeeds, and something is quietly missing.

The last one is worth telling as a story if you have time. Sending `metadata`
as a decoded object looks correct against the API spec. In the implementation it
lands in `(string) $this->content` — a PHP array cast to a string, which yields
the literal `Array`. Four characters, where 35 fields used to be. That would
have silently destroyed the entry it was supposed to update. It was caught by an
offline mock built from the source, before it ever touched a real instance.

Lesson to name explicitly: **read the implementation, not only the spec, and
build the mock from the implementation.** The full list of these is in the
README under *What eLabFTW actually does on import*.

---

## Part D — Install and run

### Slide 18 — Install

**On the slide**
```bash
# once per machine
curl -LsSf https://astral.sh/uv/install.sh | sh

# in the repository
uv sync --all-groups --extra plots

# check
uv run python -m eln examples/workshop/kinetics.solution.json -o out/kinetics.eln
uv run verify_eln.py out/kinetics.eln
```
Expected:
```
wrote out/kinetics.eln  (1 entry, 0 resource item(s), 5 attachment(s))
kinetics.eln: OK
```

**Say**
One tool, one command. `uv` fetches a matching Python itself if the system one
is too old, so "which Python do I have" never comes up.

Do this live, or better: have everyone do it now and read out the two expected
lines. Getting fifteen laptops to the same state is the actual risk in the next
three hours, not the material.

Point at the troubleshooting table in the README rather than reading it out.

---

### Slide 19 — Run

**On the slide**
```bash
uv run marimo edit notebooks/00_build_document.py            # build a document
uv run marimo edit notebooks/01_export_eln.py                # document → .eln
uv run --group api marimo edit notebooks/02_retrieve.py      # eLabFTW → document
uv run --group api marimo edit notebooks/03_update.py        # write back
```
Plus the ground rules for the shared demo:
* **append your initials** to the entry title
* **no real data, no private e-mail addresses** — it is public
* it **resets every 24 h** — what you take home is your `.eln`, not the entry

**Say**
Four notebooks, one per step, each starting on its own. Notebooks 1–3 start
**empty** on purpose — nothing until you upload a file or connect. If a screen
looks blank, that is the notebook working.

Read the three demo rules out loud and mean them. Everyone shares one account;
entries are visible to all; only update an entry you created yourself.

---

## Part E — The three scenarios

### Slide 20 — Scenario 0 (the baseline): document → entry

**On the slide**
`notebook 0` → `kinetics.json` → `notebook 1` → `kinetics.eln` → import in the
browser

**Say**
The path everyone walks first. Notebook 0 starts from the three CSV files and
asks, seven times, *what can this file not tell you?* — and note that it does
not know lab notebooks exist. Notebook 1 does not know pyenzyme wrote the file
it was handed. Neither is a stage of the other.

If you are short on time, the one thing to show in notebook 0 is its opening
count: **99 numbers, three column headings, and not one statement about what any
of it is.** Then scroll to the checklist and let it fill in. That is slide 3
(data vs. metadata) demonstrated rather than asserted, so if you show this you
can shorten slide 3.

Two things to point out while notebook 1 is on screen:

* Notebook 1 keeps the **provenance editable**: title, description, references,
  creators. Those are the fields no instrument produces and no converter can
  infer, so they are the ones that go missing — and the export is the last
  moment before they freeze into something someone else will search. If
  anything changed, `modified` is re-stamped, because a modification timestamp
  you can edit around is worth nothing.
* It produces **two** downloads: the `.eln` for the notebook and the corrected
  JSON for you. The fixed provenance should not only exist inside the package.

---

### Slide 21 — Scenario 1: the organism was wrong

**On the slide**
> You notice the organism is wrong. Downloading, fixing and re-importing gives
> you a **second** entry with the same title — and no way to tell which one
> counts.

`notebook 3`: same entry ID, same links, same comments — fields and attachment
replaced together.

**Say**
This is the scenario that justifies the API route existing at all.

Three properties to walk through, because each is a decision:

**Nothing is sent until you press the button.** The notebook computes the whole
request — every field, both bodies, which files differ — and shows it to you
first. `prepare()` sends nothing; `apply()` is a second, explicit call. A human
fits in between.

**Your own writing is left alone.** The generated part of the entry body sits
between two visible markers. Only what is between them is rewritten. Method,
notes, a photo of the setup go *outside* the markers and survive every update.
Visible text rather than an HTML comment, because eLabFTW's filter deletes
comments — and since the marker addresses a human, being visible is arguably
right anyway.

**You are warned about what you are about to destroy.** Extra fields are
replaced, not merged — if a species leaves the document its field has to leave
the entry. The price is that anything typed into those fields inside eLabFTW is
overwritten. So before sending, the notebook compares the instance against what
the *unmodified* document would produce, and names every value the update would
overwrite. It shows it; it does not block. The person knows things the tool does
not.

---

### Slide 22 — Scenario 2: fetch several entries and compare

**On the slide**
```
extrafield:"Group ID":dilution_series_1
date:2026-09-01..2026-09-30
```
→ two entries, side by side, with a species matrix

**Say**
This is where the work from slide 4 pays off, and it is worth being explicit
about the causality: **you can run these queries only because the metadata was
structured on the way in.** Neither query works against prose.

Then the species matrix: two documents from different days, one row per species,
a tick where it occurs. It is readable because the identifiers came from
registries. Had each experimenter named things their own way, it would be a
diagonal of ones — every species unique to its own document, no comparison
possible. Show that as the counterfactual; it makes the registry lookup in
notebook 0 retroactively obvious.

Note also: the document comes out of the **attachment**, not reverse-engineered
from the fields. So an entry written by hand in eLabFTW has fields but no
document, and the notebook says so rather than inventing one.

---

### Slide 23 — Scenario 3: retrieve, fit, push back

**On the slide**
```
notebook 2  →  document  →  [ model fitting — separate session ]
                              ↓
                          document + fitted parameters
                              ↓
notebook 3  →  the same entry, now carrying the model
```

**Say**
The loop closing. Retrieve the document, fit a kinetic model to the data, push
the enriched document back onto the same entry — same ID, one history.

Two things this makes true that were not true before:
* the fit and the data it came from are in one place, and stay in one place
* the entry's fields now include the model, so `k_cat` and `K_m` become
  searchable across the group's experiments

Say clearly that the fitting itself is a separate session — this workshop
deliberately leaves the kinetic model out of notebook 0, because *what did you
measure* stays cleaner when it is not mixed with *what do you think it means*.

---

### Slide 24 — What else this opens up

**On the slide**
* instrument → document → entry, unattended (the converter never needs a UI)
* one document, many ELNs — the `.eln` is not eLabFTW-shaped
* nightly consistency check: does every entry still match its attachment?
* bulk correction: fix a wrong taxonomy ID across 40 entries in one loop
* archive/publish: the same crate goes to Zenodo without rework

**Say**
Keep this short and concrete. The theme: once the document is the source of
truth and the entry is a computed projection, everything that was a manual
editing job becomes a loop.

The nightly check is the one people underestimate. Drift detection already
exists in notebook 3 — running it read-only across a whole team answers "has
anyone hand-edited a generated field?", which is otherwise unanswerable.

---

## Part F — Other ELNs, limits, outlook

### Slide 25 — Chemotion, openBIS, Sciformation

**On the slide**

| | consortium member | ships `.eln` | today's route |
|---|---|---|---|
| **Chemotion** / labIMotion | ✅ yes | not in the support table | crate is valid — import when they ship it |
| **openBIS** | no | no; RO-Crate export announced as in progress | PDF/XLSX out of the UI; API + our JSON |
| **Sciformation** | no | no | JSON/ZIP/CSV export; API + our JSON |

**Say**
Answer the question people will actually ask — "we don't use eLabFTW, is this
useless to us?" — with a clear no, and then be precise about why.

**Chemotion** is a member of the ELN Consortium; the support table does not yet
list it as shipping import or export. So the file we produce is already the
right file for them; what is missing is on their side, and it is a roadmap item
rather than a design gap. *(check before the talk — this moves)*

**openBIS** is not a consortium member. Its documented UI export is PDF and
XLSX, and RO-Crate export is described as in progress; there is a branch in
their public GitLab. Today the practical route is their API plus our source
document. *(check before the talk)*

**Sciformation** is not a member either and does not mention `.eln` or RO-Crate
among its formats — it exports PDF, XLS(X), CSV, JSON, ZIP, DOCX, HTML. The
route there is also API plus JSON.

Then the general point, which is the reassuring one: **the structured document
is the asset, not the adapter.** `eln/crate.py` is a few hundred lines. If your
ELN changes, or you change ELNs, you rewrite the adapter and keep the documents.
That is exactly backwards from the usual situation, where the tool holds the
data hostage.

---

### Slide 26 — Limits, honestly

**On the slide**
* foreign ELNs get the entry and the files, **not** native typed fields
  (`variableMeasured` is readable; the last-mile mapping is per ELN)
* extra fields are **flat** — no nesting, no series; ranges become text
* the body fence protects your text only **outside** the markers
* eLabFTW **archives** replaced attachments rather than overwriting — old
  versions accumulate by design
* protocol **steps** are not emitted (hence we declare ELN version 103, not 104)
* an entry with **two authors** fails the consortium's own JSON schema
* the SHACL validator is pinned to **RO-Crate 1.1**; we declare 1.2, as eLabFTW
  does
* **last write wins** — drift is shown, not prevented
* EnzymeML **v1 is rejected**, on purpose, rather than silently half-converted

**Say**
Put the limits on one slide and read them. A talk that lists no limits gets
believed less, not more, by exactly the people you want to convince.

Two are worth a sentence each. The **flat fields** limit is why the attachment
stays authoritative — the projection is for finding things, not for holding
them. The **last write wins** limit is a deliberate choice: the tool shows you
every value your push would overwrite and then lets you decide, because a person
knows things the tool does not.

The bottom two are findings about *other people's* tools that we chose to
declare rather than work around — both are written down with reasons in
`conformance.py`.

---

### Slide 27 — Why this route rather than the alternatives

**On the slide**

| Alternative | What it costs |
|---|---|
| type the metadata into the ELN by hand | done twice, drifts, unsearchable prose |
| ELN's own bulk import (CSV/XLSX) | no attachments, no graph, no way back |
| a custom in-house integration | one ELN, one schema, one maintainer, no exit |
| **document + `.eln` + adapter** | one source of truth, checkable round-trip, exit door built in |

**Say**
The comparison, in one slide.

The distinguishing property is the fourth row's second half: **checkable**. This
repository can run `roundtrip_eln.py` and print `identical`. That is not a
promise about the mapping, it is a test of it — and it runs in CI, on your own
documents, before you trust anything to it.

And the exit: because the document is the artefact and the `.eln` is a
consortium format, nothing here creates a dependency on this tool. Delete the
adapter and you still have your documents and your packages.

---

### Slide 28 — Outlook

**On the slide**
* a **second ELN** wired up end to end (Kadi4Mat or SampleDB) — the real test of
  the universality claim on slide 10
* **more schemas** through the same five-function interface
* native-field mapping proposed **back to the consortium** — the one gap that is
  standardisable
* openBIS RO-Crate export, when it lands
* the model-fitting loop from slide 23, as a routine rather than a session
* the eLabFTW findings from slide 17, filed **upstream** as documentation issues

**Say**
End on the one that matters: slide 10 draws a line between universal and
eLabFTW-specific, and right now that line is an argument, not a demonstration.
Wiring up a second ELN end to end is what would turn it into one — and it is the
next thing worth doing.

---

### Slide 29 — Close

**On the slide**
> Data and metadata belong together — **in structured form**.
>
> The document is the source of truth.
> The lab notebook entry is how people find it.
> One command keeps them in sync — and you can check that it did.

Repository URL, licence, your contact.

**Say**
Three sentences, then hands on keyboards. The rest of the workshop is them doing
it to their own data.

---

## Appendix — things to have ready

**Have open in tabs**
* the ELN Consortium support table — someone always asks whether their ELN is on
  it: <https://github.com/TheELNConsortium/TheELNFileFormat>
* the demo instance, already logged in: <https://demo.elabftw.net>
* one imported entry from a *previous* run, so slide 14's before/after can be
  shown rather than described

**Have on disk**
* `out/kinetics.eln` already generated, in case the network is gone
* the entry body with the `=== BEGIN GENERATED SECTION ===` markers visible —
  it explains itself better on screen than in words

**Questions you will get**
* *"Does this work with our ELN?"* → slide 9 for the shipped list, slide 25 for
  the three named ones, slide 10 for what "works" means.
* *"Do we have to use EnzymeML?"* → no; slide 12's last paragraph. One module,
  five functions.
* *"What if someone edits the entry in eLabFTW?"* → slide 21, third property.
  Shown by name before overwriting, never silently.
* *"How is this different from just attaching the JSON?"* → an attachment is not
  searchable. Slides 4 and 22 together are the answer: the fields are what make
  the attachment findable.
* *"What happens when the schema changes?"* → the round-trip test fails loudly,
  which is the point of having it.
