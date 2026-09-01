# FY2570 Operational MVP — Post-Reduction Verification

## Goal

Use the real-format assembled Excel workbook as the operational artifact and verify that the final/post-reduction version remains correct relative to the Draft-Bill baseline.

The MVP is not a generic diff viewer. It is a **budget-document verification workflow**.

## Operational sequence

1. **Load Draft-Bill baseline**
   - use the already assembled/validated workbook as the expected starting state;
   - lock identity/provenance before comparison.

2. **Load final/post-reduction workbook**
   - preserve workbook structure for inspection;
   - do not mutate the input during verification.

3. **Compare at multiple levels**
   - workbook / sheet / cell;
   - labels and descriptive text;
   - indicators and targets;
   - numeric values;
   - formulas and formula residue;
   - roll-ups and cross-footing;
   - cross-sheet relationships;
   - layout/template invariants where operationally required.

4. **Classify changes**
   - expected approved reduction/increase;
   - consequential propagation of an approved change;
   - corrective/data-quality edit;
   - unexplained/unexpected difference;
   - cannot determine automatically → human review.

5. **Reconcile dependent totals**
   - item → project/output → program/plan → agency totals;
   - linked future-year/commitment values when represented in the workbook;
   - verify that intended adjustments propagate consistently.

6. **Human review UI**
   For each finding show:
   - finding ID;
   - source sheet/cell or semantic location;
   - Draft-Bill value;
   - final value;
   - difference;
   - expected/derived direction;
   - dependent totals affected;
   - evidence links;
   - machine classification;
   - human decision / confidence / note.

7. **Preflight before submission/publication**
   - remaining formulas;
   - value-only conversion checks if required;
   - post-conversion reconciliation;
   - missing/extra sheets or template regions;
   - unresolved findings;
   - final READY / REVIEW REQUIRED state.

## Seven-day scope

### Must have

- real-format workbook ingestion;
- deterministic sheet/cell mapping for the FY2570 template;
- amount + text/indicator comparison;
- roll-up/cross-sheet reconciliation;
- formula-residue detection;
- change classification;
- human-review web UI;
- evidence export / audit summary;
- regression tests using publication-safe/public fixtures.

### Should have

- template/layout invariants for high-risk cells/regions;
- future-year propagation rules where the workbook exposes those values;
- clear correction pointer (sheet/cell/field) for every actionable finding.

### Not required for this seven-day MVP

- full FY2571 RedBook generation from scratch;
- direct e-Budget write-back/API automation;
- full PDF workflow integration;
- OCR as the primary verification mechanism.

## Acceptance idea

The MVP is ready for real work only when it can take the FY2570 Draft-Bill baseline plus the final workbook and produce a reviewable finding set where:

- approved monetary changes reconcile to known totals;
- unexpected changes are surfaced separately;
- indicators/text changes are visible;
- no unresolved roll-up mismatch is hidden by a correct grand total;
- formula residue and preflight failures are explicit;
- every finding can be traced back to workbook evidence.
