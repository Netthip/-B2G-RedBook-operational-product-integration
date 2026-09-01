# FY2571+ Product Vision — Build, Verify, Correct, Publish

## Goal

Move from a post-hoc comparison tool to a full operational RedBook workflow that helps construct, verify, correct and publish a valid budget artifact.

## Mode A — Draft / Pre-Bill Builder

Starting from earlier-cycle source material:

- prior-year workbook/baseline;
- current-year e-Budget exports;
- RedBook report components;
- BlueBook components;
- approved template rules.

The system should:

1. assemble a new-year RedBook workbook from the real source structure;
2. preserve required layout/template invariants;
3. compare prior-year and current-year semantics at cell/field level;
4. detect added/removed programs, projects, indicators, targets, labels and amounts;
5. reconcile totals across sheets and hierarchy levels;
6. surface differences for human decision rather than guessing;
7. identify the likely correction target in the source workflow/e-Budget export;
8. produce a validated working artifact;
9. prepare downstream PDF/publication QA.

## Mode B — Post-Reduction Verifier

After parliamentary adjustment / final approved changes:

1. use the validated Draft-Bill workbook as baseline;
2. compare the final/post-reduction workbook;
3. distinguish approved adjustments from unrelated corrective edits;
4. trace propagation into totals and linked future-year/commitment values;
5. re-check indicators, descriptions and structural fields;
6. run formula/value-only/template preflight;
7. require human resolution of unexplained differences;
8. produce a final validated artifact plus evidence package.

## UI concept

The operational UI should not be organized around a raw diff list alone.

The central review unit should answer:

- What changed?
- Where did it change?
- Is the change expected?
- What totals/fields depend on it?
- Does the dependent structure still reconcile?
- What evidence supports the finding?
- What must the practitioner correct before release?

Suggested finding view:

`context → baseline → current → difference → dependent checks → evidence → machine assessment → human decision → correction target`

## PDF relationship

PDF is a downstream validated artifact, not a substitute for structured spreadsheet verification.

The existing B2G Thai PDF Repair & Evidence Pipeline can later serve as:

- rendered-artifact comparison;
- Thai typography/visual QA;
- page-level issue evidence;
- publication preflight.

## Long-term outcome

The target is an end-to-end quality-control layer for RedBook work:

`source data → build → structured verification → human review → correction → final workbook → PDF/publication QA → evidence package`
