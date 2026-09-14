# Four documents to compare

Notebook 2's best moment is the species matrix: several documents side by side,
one row per species, and the rows line up because the identifiers came from a
registry rather than from each experimenter's habits. That moment needs more
than one experiment to compare, and on a workshop instance where everybody
imported the same dataset, the matrix is one column of ticks and the
two-document diff says *identical*.

These four are the contrast. They were built by
[`test/seed_demo.py`](../../test/seed_demo.py) and are checked in so the
exercise works without network access to Rhea, ChEBI and UniProt.

| File | Enzyme | Reaction | pH | T | Date |
|---|---|---|---|---|---|
| `adh_yeast.json` | yeast ADH1 · `P00330` | ethanol + NAD⁺ → acetaldehyde + NADH | 8.8 | 25 °C | day 0 |
| `adh_horse.json` | horse liver ADH · `P00327` | ethanol + NAD⁺ → acetaldehyde + NADH | 7.5 | 25 °C | day 7 |
| `aldh_human.json` | human ALDH2 · `P05091` | acetaldehyde + NAD⁺ + H₂O → acetate + NADH | 8.0 | 30 °C | day 14 |
| `ldh_human.json` | human LDH-A · `P00338` | (S)-lactate + NAD⁺ → pyruvate + NADH | 9.0 | 25 °C | day 21 |

Three runs each, eleven time points over 20 minutes, the starting
concentrations spanning the enzyme's K<sub>m</sub>, which for ALDH2 is
micromolar, so that document is the one whose data unit is `umol / l` while its
cofactor stays in `mmol / l`. Two units in one experiment is not a mistake;
it is what a real measurement looks like.

The dates are not in the documents. They are applied to the **entries** when
the script pushes them, counted from `--start` (default: 28 days ago), so the
four always land a week apart in the recent past.

## What the matrix shows

Every degree of overlap appears exactly once, which is the point:

| Species | In | Because |
|---|---|---|
| NAD⁺, NADH, H⁺ | all four | the cofactor nobody escapes |
| acetaldehyde | ADH ×2, ALDH | **ALDH2 oxidises what the ADHs produced** |
| ethanol | ADH ×2 | the same reaction on two enzymes |
| (S)-lactate, pyruvate | LDH | a different reaction entirely |
| acetate, water | ALDH | |

The two ADH documents are the same reaction measured on two enzymes, so they
differ in organism and in nothing else structural. The ALDH document is the
next step of that pathway, and the matrix says so without anybody having
written it down anywhere, because `acetaldehyde` is one id with one InChIKey in
all three documents that contain it. Had each experiment invented its own
names, the table would be a diagonal of ones.

## Using them

**In a notebook**: upload one in [step 1](../../notebooks/01_export_eln.py)
and export it, or drop one into step 3 as a corrected document.

**Into an instance**, which is what makes the step 2 exercise work:

```bash
uv run python test/seed_demo.py --url https://demo.elabftw.net --key $ELAB_KEY --commit
```

That creates four dated entries. Then, in
[step 2](../../notebooks/02_retrieve.py):

```
extrafield:"EC number":1.1.1.1              the two ADH documents
extrafield:"Organism":"Homo sapiens"        LDH and ALDH
extrafield:"Group ID":dilution_series_adh_yeast    one series, three runs
date:…..…                                   all four
```

The script prints those four lines with the dates filled in when it runs, so
the range is the one it actually wrote rather than one to guess at.

Select two entries **from different days**, fetch them, and read the matrix.

## What is real and what is not

The measured values are **synthetic**: a Michaelis–Menten simulation with a
fixed seed and 1.5 % noise, reproducible across runs, and every document says
so in its own description. `k_cat` and `K_m` are round numbers of the right
order of magnitude, not measurements.

The identifiers are **real**: the reactions come from Rhea, the enzymes from
UniProt, and the small molecules with them from ChEBI. Nothing about the
comparison would mean anything if they were invented, so they are not.
