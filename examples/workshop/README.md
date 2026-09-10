# Hands-on: from EnzymeML to a lab notebook entry

| File | Contents |
|---|---|
| `data/ethanol_*mM.csv` | the raw time series — the source of truth |
| `kinetics.skeleton.json` | data blocks complete, metadata blocks empty — **work on this one** |
| `kinetics.solution.json` | the same file with the metadata filled in — reference solution |

## The experiment

Alcohol dehydrogenase 1 from *Saccharomyces cerevisiae* oxidises ethanol to
acetaldehyde while reducing NAD⁺ to NADH. NADH formation is followed
photometrically at 340 nm and the ethanol decrease is derived from it. Three
runs with different starting concentrations of ethanol (2, 8 and 18 mmol/l),
eleven time points each over 20 minutes.

The numbers come from a Michaelis–Menten simulation with a little measurement
noise — a teaching dataset, not real bench values. The chemical and biological
identifiers, on the other hand, are real and verified against PubChem and
UniProt.

## Two routes

**Notebooks** — click-driven, with a live preview. Recommended:

```bash
uv run marimo edit notebooks/00_build_document.py            # step 0
uv run marimo edit notebooks/01_export_eln.py                # step 1
uv run --group api marimo edit notebooks/02_retrieve.py      # step 2
uv run --group api marimo edit notebooks/03_update.py        # step 3
```

**Step 0** starts with the three CSV files and builds an EnzymeML v2 document
around them. It opens by counting what is actually in those files — 33 rows,
three column headings, 99 numbers — and then names the seven things they cannot
say. One step per question, and a checklist at the top that counts them down as
you answer them:

1. **the files** — drop your own CSVs here, or use the three bundled ones
2. **the gap** — the seven questions, live
3. **what the columns are** — `RHEA:25290` yields the whole reaction with all
   five molecules and their InChIKeys, `P00330` the enzyme with EC number,
   organism and sequence. A switch turns the fetchers off and shows the
   alternative: the same information typed out by hand, which is also the
   fallback when the wifi gives up. Then every column is bound to one species,
   with a unit — `nadh_mmol_per_l → nadh_2` is the whole exercise in one line
4. **where, and under what conditions** — the vessel (and why `ml` comes back as
   *litre, exponent 1, scale −3*), pH, temperature, and the series ID that turns
   three files into one experiment
5. **what was in the vessel but never measured** — the enzyme has no column, and
   leaving it out reads as *there was no enzyme in the cuvette*
6. **what reaction this is** — one row per participant, including the one row no
   database gave you: *this* protein catalyses *this* reaction. Delete it and
   look at what is left
7. **who measured it, and by what method**
8. **the document** — assembled, reviewed, and checked against the same seven
   questions it opened with

Every table grows, so the same notebook works for this experiment and for one of
your own.

There is **no kinetic model**. Rate laws, parameters and fits are a session of
their own; leaving them out here keeps *what did you measure* apart from *what
do you think it means*.

It ends with a download button for `kinetics.json`.

**Step 1** takes that file — or any EnzymeML or FAIRFluids document — and turns
it into the `.eln`. It **starts empty**: until you drop a file on it there is
nothing to see, because every number, table and preview in it is derived from
your document rather than from a built-in example.

Once a document is in, the **provenance stays editable**: title, description,
references, creators — for FAIRFluids the citation and its authors. Those are
the fields no instrument produces and no converter can infer, so they are the
ones that tend to be missing, and the export is the last moment before they are
frozen into an entry somebody else will search. Whatever you change is what gets
exported; the uploaded file is never written to, and the notebook shows you the
list of what you changed. If anything did change, `modified` is stamped with the
current time — a modification timestamp that survives being edited around is
worth nothing.

Extra fields and the entry body are then previewed exactly as eLabFTW will show
them, and the round trip is checked before you download. Two downloads come out:
the `.eln` for the lab notebook and the corrected JSON for you, so the fixed
provenance does not only live inside the package.

**Step 2** goes the other way: it connects to a running eLabFTW, searches it,
and turns entries back into the documents they were made from. It too starts
empty — nothing happens until you give it an instance and an API key, and
**read-only permission is enough**, so nothing you do there can damage
anything.

The search is where step 1 pays off. eLabFTW's advanced query language reaches
the extra fields, so `extrafield:"Group ID":dilution_series_1` finds a dilution
series and `date:2026-09-01..2026-09-30` finds a month — neither of which works
on information buried in the prose of an entry body. Fetch two entries from
different days and the notebook puts them side by side, including a table of
which species occur in which document. That table is only readable because the
identifiers came from registries rather than from each experimenter's habits;
had everyone invented their own names it would be a diagonal of ones.

The document comes out of the **attachment**, not out of the extra fields. The
fields are a projection built for people to read and search; the attachment is
byte for byte what the export put there. An entry written by hand in eLabFTW
therefore has fields but no document, and the notebook says so rather than
inventing one.

**Step 3** closes the loop. You notice the organism is wrong, or an analysis
handed you a document with fitted parameters in it. Downloading, fixing and
importing again would give you a *second* entry with the same title and no way
to tell which one counts. Step 3 updates the entry you already have — same ID,
same links, same comments — replacing the extra fields and the attachment
together, so the searchable summary and the document it summarises cannot drift
apart.

It needs an API key with **write** permission; the read-only one from step 2 is
refused. Two things about it are worth understanding rather than clicking
through:

*Nothing is sent until you press the red button.* The notebook computes the
entire request — every field, both bodies, which files differ — and shows it to
you first. Only attachments whose sha256 differs from what the instance reports
are uploaded, so correcting an organism re-sends the document and leaves the
plot and the CSVs alone.

*Your own writing is left alone.* The generated part of the entry body sits
between two visible markers, and only what is between them is rewritten. Put
the method, your notes, a photo of the setup **outside** the markers and they
survive every update. (The markers are visible text rather than HTML comments
because eLabFTW's body filter deletes comments and allows no marker class
through — and since the markers address a human, being visible is arguably
right.)

*Old versions of the files are kept, not overwritten.* eLabFTW archives the
previous upload and adds a new one, by design: attached files are immutable and
their history is kept. So after an update the entry lists the earlier
`enzymeml.json` as archived beside the current one. The notebook makes sure
exactly one is current.

*The extra fields are replaced, not merged.* The document is the source and the
fields are its projection, so a species that leaves the document has to leave
the entry too. The price is that anything typed into those fields inside
eLabFTW is overwritten — which is why the notebook compares the instance
against what the unmodified document would produce and warns you, by name,
about every value your update is about to destroy.

On the shared demo: **only update an entry you created yourself in step 1.**
Everyone is in the same account, and nothing stops you from patching somebody
else's work except reading the ID twice.

One switch is worth understanding rather than flipping: **resource items**
(`--links` on the command line). eLabFTW keeps experiments, which happen once,
separately from resources — its database of compounds, enzymes and equipment
that persist across experiments. With the switch on, every species also becomes
a resource item that the entry links to. The species are exported either way, as
extra fields, in the body and inside the attached JSON; the switch only decides
whether they *also* get their own database entries. Leave it off on the shared
demo — fifteen participants importing at once would leave fifteen copies of
ethanol behind — and turn it on at home, where a compound really is worth having
once and referring to many times.

The split is deliberate. Step 0 does not know that lab notebooks exist, and step
1 does not know that pyenzyme wrote the file it was given. Neither is a stage of
the other; a structured document is worth having even where no ELN is involved.

Step 1 builds **one** lab notebook entry for the whole document — the three runs
are one dilution series, hence one experiment. Why that is not merely a matter of
taste (90 % verbatim copies and a threefold-attributed `K_m` if you split it) is
explained under *Granularität* in the [main README](../../README.md). Good
lecture material, but nothing the participants need to decide.

**Editor** — the same exercise directly in the JSON file, for anyone who would
rather see where the values actually land. The walkthrough below describes that
route.

## About the demo instance

We work on <https://demo.elabftw.net>. Three of its properties you need to know
before uploading anything:

* **Everyone shares one account.** Your entries sit next to everyone else's and
  all of them are visible to all. Append your initials to the document title
  (`name`), or fifteen entries will have the same name.
* **It is public.** No real research data, no private e-mail addresses. The
  dataset here is synthetic; a placeholder is fine for `creators`.
* **It is reset every 24 h.** What you take home is not the lab notebook entry
  but your `.eln` file and your JSON on your own machine. Step 5 is therefore
  not an afterthought — it is the backup.

## Walkthrough

**1. See what is missing**

```bash
uv run workshop_todo.py examples/workshop/kinetics.skeleton.json
```

36 open metadata fields, grouped by section, each with a hint about what belongs
there. JSON has no comments — which is why the task description lives in that
script rather than in the file.

**2. Export once, before filling anything in**

```bash
uv run python -m eln examples/workshop/kinetics.skeleton.json -o raw.eln
```

Import the result into eLabFTW and look at it. It works — but the entry is
called `EnzymeML document`, the enzyme is `p_adh`, and under *Species* you find

```
s_etoh, NAD+, s_acetald, NADH, p_adh
```

The two pre-annotated cofactors show their names while your compounds show bare
IDs. The difference sits side by side in a single field. Structured, and still
useless to a human.

**3. Add the metadata**

Fill in the open fields in the skeleton. What needs looking up:

* **Enzyme** — [UniProt P00330](https://www.uniprot.org/uniprotkb/P00330):
  EC number, organism, NCBI taxonomy ID, sequence.
* **Ethanol and acetaldehyde** — [PubChem](https://pubchem.ncbi.nlm.nih.gov):
  InChI, InChIKey, SMILES. NAD⁺ and NADH are already filled in and serve as a
  template for the format.
* **Conditions** — pH 8.8, 25 °C, cuvette volume 1.0 ml. The `group_id` is the
  same for all three measurements: that is how you tell later that they are one
  dilution series and not three independent experiments.

Re-run `workshop_todo.py` as you go — the counter climbs.

**4. Export again and compare**

```bash
uv run python -m eln examples/workshop/kinetics.skeleton.json -o done.eln
```

More interesting than the count of new fields is *which* ones appeared: EC
number, organism, pH, temperature, InChIKey, authors. Those are the fields that
let you find "all measurements at pH 8.8 with *S. cerevisiae* ADH" in two years.
The ones that were already there only describe this one experiment.

**5. Get it back out**

```bash
uv run python -m eln done.eln -o back.json --from entries \
    --against examples/workshop/kinetics.skeleton.json
```

```
round-trip vs. kinetics.skeleton.json: identical
```

That is the point of the whole exercise: the metadata now sits structured and
searchable in the lab notebook — and the EnzymeML document comes back out
unchanged. Nothing had to be maintained twice.

**6. Have someone else grade it**

```bash
uv run --group checks conformance.py done.eln
```

This runs the ELN Consortium's own conformance suite — the same code behind
their CI and their web checker — against your file. It is worth doing once even
though the export already passes: "our tool says our output is fine" is not
evidence, and the difference between the two claims is most of what FAIR means
in practice.

## What you never touch

The data blocks. `time`, `data`, `initial`, the unit definitions and the IDs
that hold everything together are given. That is deliberate: typing out time
series teaches nothing, and the line between "numbers from the instrument" and
"context only a human knows" is exactly the subject.

Also given are the reaction equation, the ODE and the kinetic parameters
(`k_cat`, `K_m`) — they land in the *Model* field group and show that an
EnzymeML document carries more than raw data.
