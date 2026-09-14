# Hands-on: from a measurement to a lab notebook entry and back

Four steps, one notebook each, in the order the loop runs:

| Step | Notebook | Direction |
|---|---|---|
| 0 | `00_build_document.py` | what you measured becomes an EnzymeML document |
| 1 | `01_export_eln.py` | document becomes an `.eln` package |
| 2 | `02_retrieve.py` | lab notebook entry becomes a document again |
| 3 | `03_update.py` | corrected document goes back onto the *same* entry |

Nothing in this folder is a prerequisite for any other part of it. Step 0 does
not know that lab notebooks exist. Step 1 does not know where its document came
from. Step 2 does not know how the entries got there. That is deliberate, and
it is most of the argument: the adapter hangs off a **format**, not off a tool.

The files you will need, all paths from the top of the project:

| File | Contents |
|---|---|
| `notebooks/data/ethanol_*mM.csv` | the raw time series, three runs, the source of truth |
| `examples/workshop/kinetics.solution.json` | the finished document, to skip ahead or to compare against |
| `examples/seed/*.json` | four contrasting documents, so that step 2 has something to compare |

## Install

One installer, one sync. See
[the main README](../README.md#install) for the per-platform detail and the
troubleshooting table; the short version is:

```powershell
# Windows, in PowerShell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then **close that terminal and open a new one**, so it picks up `uv`, and get
the project. With git:

```bash
git clone https://github.com/samigab/enzymeml-eln-workshop.git
cd enzymeml-eln-workshop
```

**Without git, which nobody needs to install for this:** open
<https://github.com/samigab/enzymeml-eln-workshop>, press the green **Code**
button, choose **Download ZIP**, unpack it, and go into the folder called
`enzymeml-eln-workshop-master`. The main README has the terminal version of the
same thing.

Either way, one command installs the rest:

```bash
uv sync
```

That is everything: the converter, the four notebooks, the graph widget, the
eLabFTW client and the conformance checker. There are no optional groups to
remember and no virtualenv to activate. If the laptop has no suitable Python,
uv fetches one.

Check it

```bash
uv run python -m eln examples/workshop/kinetics.solution.json -o out/kinetics.eln
uv run test/verify_eln.py out/kinetics.eln
```

Two lines of output and you are ready.

## The experiment

Alcohol dehydrogenase 1 from *Saccharomyces cerevisiae* oxidises ethanol to
acetaldehyde while reducing NAD⁺ to NADH. NADH formation is followed
photometrically at 340 nm and the ethanol decrease is derived from it. Three
runs with different starting concentrations of ethanol (2, 8 and 18 mmol/l),
eleven time points each over 20 minutes.

The numbers come from a Michaelis–Menten simulation with a little measurement
noise. They are a teaching dataset, not bench values. The chemical and
biological identifiers, on the other hand, are real and verified against
PubChem, Rhea and UniProt, which matters more than it sounds: identifiers are
the only part of this that lets two experiments be compared at all.

## Step 0: build the document

```bash
uv run marimo edit notebooks/00_build_document.py
```

You start with nothing, and the notebook asks one question: **what is a
scientific data model actually made of?** The answer it gives, over and over,
is entities and the links between them. Every record you add appears as a node
in a live graph; every reference you make appears as an edge you can follow.

Nine steps, in the order the model wants them, because a species has to exist
before a reaction can name it and a measurement has to exist before its numbers
can hang off it:

1. **the document**, one object to hang everything else on
2. **the vessel**, where the experiment happened
3. **proteins**, the enzyme, with its EC number and its taxonomy ID
4. **small molecules**, substrate, product, cofactors, buffer
5. **the reaction**, which on its own is an empty box
6. **participants**, the link no database can give you: *this* protein
   catalyses *this* reaction
7. **measurements**, one run with the conditions it ran under
8. **the numbers**, bound to a species, in a unit, against a time axis
9. **who measured it**

Three kinds of line appear in the picture and the difference between them is
the lesson:

| line | means | example |
|---|---|---|
| solid, grey | **contains**, a field holds an object | `EnzymeMLDocument` → `Protein` |
| dashed, amber | **references**, a field holds another object's `id` | `SmallMolecule.vessel_id` → `Vessel` |
| dotted, faint | **is a**, an instance and its type | *Lipase* → `Protein` |

The amber ones are the point. Nothing in the JSON's nesting shows them. They
exist only because two strings match, and they are what turns the document from
a tree into a graph. A reference that points at nothing is drawn as nothing,
and the notebook says so in a warning box: a document like that is still valid
JSON, it simply means nothing.

**Step 8 is where your data goes in.** Drop `notebooks/data/ethanol_2mM.csv` on the box
that appears there: first column the time axis, one column per species after
it, and a picker for which column belongs to the species you are adding. The
file is read when you press *Add SpeciesData*, not before, and it is emptied
afterwards so the next entry cannot silently inherit the previous one's series.
Rows that do not parse are skipped and counted. You can also paste two columns
of numbers by hand, and you can leave the box empty, which records a starting
concentration and nothing else. That is still data: you pipetted it, you just
did not follow it.

Every edit is appended to a step log and the document is folded out of the
whole log rather than mutated in place. Undo is the log without its last entry;
the history slider is the log up to *n*. Click any node to edit it, and watch
the change travel from the object through the JSON to the graph. Load the
worked example from the history panel if you want sixteen steps of somebody
else's experiment to replay.

There is **no kinetic model** here. Rate laws, parameters and fits are a
session of their own, and leaving them out keeps *what did you measure* apart
from *what do you think it means*.

It ends with a download button for `kinetics.json`.

## Step 1: export the `.eln`

```bash
uv run marimo edit notebooks/01_export_eln.py
```

This takes the file from step 0, or any other EnzymeML or FAIRFluids document,
and turns it into the package eLabFTW imports. It **starts empty**: until you
drop a file on it there is nothing to see, because every number, table and
preview in it is derived from your document rather than from a built-in
example.

Once a document is in, the **provenance stays editable**: title, description,
references, creators, and for FAIRFluids the citation with its authors. Those
are the fields no instrument produces and no converter can infer, which is
exactly why they tend to be missing, and the export is the last moment before
they freeze inside an entry somebody else will search. What you change is what
gets exported. The uploaded file is never written to, the notebook lists what
you changed, and if anything did change, `modified` is stamped with the current
time. A modification timestamp that survives being edited around is worth
nothing.

Extra fields and the entry body are previewed exactly as eLabFTW will show
them, and the round trip is checked before you download: the document is read
back out of the package it just went into and compared with what you uploaded.
Two downloads come out, the `.eln` for the lab notebook and the corrected JSON
for you, so the fixed provenance does not live only inside the package.

One switch is worth understanding rather than flipping. **Resource items**
(`--links` on the command line) make every species its own entry in eLabFTW's
database of compounds and equipment, which the experiment then links to. The
species are exported either way, as extra fields, in the body and inside the
attached JSON. The switch only decides whether they *also* get their own
database entries. Leave it off on the shared demo, where everyone
importing at once would leave one copy of ethanol per participant, and turn it on
at home, where a compound really is worth having once and referring to many
times.

Step 1 builds **one** entry for the whole document, because the three runs are
one dilution series and therefore one experiment. Why that is not merely a
matter of taste is under *Granularity* in the
[main README](../README.md#granularity-what-is-one-entry): split it and you
get 90 % verbatim copies and a `K_m` attributed three times.

When you have the file, hand it to somebody who did not write the converter:

```bash
uv run test/conformance.py your-download.eln
```

That is the ELN Consortium's own suite, the same code behind their CI and their
web checker. It is worth running once even though the export already passes,
because "our tool says our output is fine" is not evidence, and the difference
between those two claims is most of what FAIR means in practice.

## Step 2: get the documents back out

```bash
uv run marimo edit notebooks/02_retrieve.py
```

This connects to a running eLabFTW, searches it, and turns entries back into
the documents they were made from. It also starts empty, since nothing happens
until you give it an instance and an API key, and **read-only permission is
enough**, so nothing you do here can damage anything.

The search is where step 1 pays off. eLabFTW's advanced query language reaches
the extra fields, so `extrafield:"Group ID":dilution_series_1` finds one
dilution series and `date:2026-09-01..2026-09-30` finds a month. Neither works
on information buried in the prose of an entry body. If the instance was seeded
with `test/seed_demo.py`, `extrafield:"EC number":1.1.1.1` finds the two ADH
experiments and `extrafield:"Organism":"Homo sapiens"` the other two.

Select several entries, fetch them, and read the table that appears. One row
per species, one column per document, a tick where it occurs. The rows line up
only because the identifiers came from registries rather than from each
experimenter's habits. Had everyone invented their own names, the table would
be a diagonal of ones: every row present in exactly one column, nothing
comparable with anything. That is what identifiers buy, and it stays invisible
until the moment you put two experiments next to each other.

Several documents in hand is also where this stops being a viewer. They are
machine-readable input to whatever comes next: pooled time courses as the
likelihood of a Bayesian fit, `k_cat` and `K_M` estimated per enzyme and
compared across organisms, a performance evaluation that ranks candidates for a
process. None of it needs a number to be retyped, because none of it starts
from a PDF.

The document comes out of the **attachment**, not out of the extra fields. The
fields are a projection built for people to read and search; the attachment is
byte for byte what the export put there. An entry written by hand in eLabFTW
therefore has fields but no document, and the notebook says so rather than
inventing one. Only the current version of an attachment is read, never one of
the archived earlier versions beside it.

## Step 3: write a correction back

```bash
uv run marimo edit notebooks/03_update.py
```

You notice the organism is wrong, or an analysis hands you a document with
fitted parameters in it. Downloading, fixing and importing again would give you
a *second* entry with the same title and no way to tell which one counts. Step
3 updates the entry you already have, same ID, same links, same comments,
replacing the extra fields and the attachment together, so that the searchable
summary and the document it summarises cannot drift apart.

It needs an API key with **write** permission. The read-only one from step 2 is
refused. Four things about it are worth understanding rather than clicking
through:

*Nothing is sent until you press the button.* The notebook computes the entire
request, every field, both bodies, which files differ, and shows it to you
first. Only attachments whose sha256 differs from what the instance reports are
uploaded, so correcting an organism re-sends the document and leaves the plot
and the CSVs alone.

*Your own writing is left alone.* The generated part of the entry body sits
between two visible markers and only what is between them is rewritten. Put the
method, your notes, a photo of the setup **outside** the markers and they
survive every update. The markers are visible text rather than HTML comments
because eLabFTW's body filter deletes comments and allows no marker class
through, and since they address a human, being visible is arguably right.

*Old versions of the files are kept, not overwritten.* eLabFTW archives the
previous upload and adds a new one, by design, because attached files are
immutable and their history is kept. After an update the entry therefore lists
the earlier `enzymeml.json` as archived beside the current one. Both directions
here name the one they mean, so a re-read never picks up last week's document.

*The extra fields are replaced, not merged.* The document is the source and the
fields are its projection, so a species that leaves the document has to leave
the entry too. The price is that anything typed into those fields inside
eLabFTW is overwritten, which is why the notebook compares the instance against
what the *unmodified* document would produce and warns you, by name, about
every value your update is about to destroy.

On the shared demo: **only update an entry you created yourself in step 1.**
Everyone is in the same account, and nothing stops you from patching somebody
else's work except reading the ID twice.

## About the demo instance

We work on <https://demo.elabftw.net>. Three of its properties you need to know
before uploading anything:

* **Everyone shares one account.** Your entries sit next to everyone else's and
  all of them are visible to all. Append your initials to the document title
  (`name`), or every entry will have the same name.
* **It is public.** No real research data, no private e-mail addresses. The
  dataset here is synthetic and a placeholder is fine for `creators`.
* **It is reset every 24 h.** What you take home is not the lab notebook entry
  but your `.eln` file and your JSON, on your own machine. The downloads in
  step 1 are therefore not an afterthought, they are the backup.

## Before the room fills up

Two things are worth doing on the presenting machine while the wifi still
works:

```bash
uv run marimo run test/00_model_graph_toy.py
```

The toy model is a company, its departments and its employees. Five classes, no
chemistry in the way, the same engine as step 0 underneath. Ten minutes on it
first and step 0 needs no explaining at all.

```bash
uv run python test/seed_demo.py --url https://demo.elabftw.net --key $ELAB_KEY --commit
```

This puts the four documents from [`examples/seed/`](../examples/seed/README.md) on the
instance as dated entries, which is what gives step 2 something to compare. It
fetches from Rhea, ChEBI and UniProt, so run it the day before rather than
during.
