# B2G RedBook — Operational Product Integration

Public integration repository for turning the research-validated RedBook verification core into a practical workflow for real budget-document work.

## What this repository is

This repository connects three tracks that must remain distinct:

1. **Research evidence** — what has already been demonstrated and frozen for the master's research.
2. **FY2570 operational MVP** — a practical verifier for the current post-reduction / final-act workflow.
3. **FY2571+ product vision** — a fuller RedBook builder-and-validator workflow beginning earlier in the budget cycle.

> **The research prototype validates a verification core; it is not the complete operational RedBook workflow.**

## Immediate priority — FY2570 operational MVP

The next seven-day priority is not to rebuild the entire system. It is to make the current real-format Excel workflow safer before final submission/publication.

### Input

- a validated Draft-Bill baseline workbook assembled from the real RedBook/BlueBook source structure;
- the later/final workbook reflecting approved reductions or increases.

### Verify

- cell-level changes;
- numeric differences and roll-ups;
- indicators, names and descriptive fields;
- cross-sheet consistency;
- current-year and linked future-year effects where represented in the workbook;
- remaining formulas / value-only preflight;
- unexpected template/layout changes;
- intentional budget adjustments vs corrective/data-quality edits.

### Human review

Every finding must remain reviewable. The UI should show:

`baseline → current value → difference → location/evidence → classification → human decision`

The goal is not merely to say that two files differ. The goal is to help a practitioner determine **what changed, whether the change is expected, whether all dependent totals and fields remain consistent, and what must be corrected before the artifact is submitted or published**.

### Output

- verified working workbook;
- structured finding list;
- reconciliation summary;
- evidence/audit package;
- clear READY / REVIEW REQUIRED status.

## Why OCR is not enough

OCR or text extraction can help recover visible text, but it does not by itself verify structured budget-document consistency. The operational problem also includes spreadsheet structure, formulas, cross-sheet relationships, numeric roll-ups, indicators, and propagation of approved budget changes.

## Public-data principle

This repository is intended for public, reproducible work using public or publication-safe source material. Do not commit private working notes, credentials, personal paths, unpublished internal documents, or sensitive metadata.

## Relationship to existing B2G work

The existing `Netthip/b2g-thai-pdf-repair` repository remains the PDF repair / QA evidence pipeline. Its concepts — baseline locking, issue registry, human review, reproducible QA and evidence packaging — are reusable here as downstream artifact-validation capabilities.

## Working documents

- [`docs/CURRENT_STATE.md`](docs/CURRENT_STATE.md)
- [`docs/FY2570_OPERATIONAL_MVP.md`](docs/FY2570_OPERATIONAL_MVP.md)
- [`docs/FY2571_PRODUCT_VISION.md`](docs/FY2571_PRODUCT_VISION.md)
- [`docs/RESEARCH_PRODUCT_BOUNDARY.md`](docs/RESEARCH_PRODUCT_BOUNDARY.md)

## Collaboration

This repository is also the shared handoff space for Gift × Bo × Giho. Technical observations, research interpretation, product requirements, evidence, risks and decisions should be separated explicitly rather than mixed into one narrative.
