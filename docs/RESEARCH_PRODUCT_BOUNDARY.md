# Research / Product Boundary

## Principle

The research artifact and the operational product share a verification core, but they are not the same scope.

> **Research asks: what has been demonstrated with evidence?**
>
> **Product asks: what must the practitioner be able to do safely in real work?**

## Research track

Research claims must be limited to the evidence frozen in the research repository and its authorized forward-only supplements.

The research track may demonstrate that a verification mechanism works within a defined scope without claiming that the complete operational workflow is finished.

## Operational product track

The product may continue beyond the frozen research scope to solve real workflow needs, including new rules, UI, generation, preflight and later PDF integration.

New operational work must not be written retrospectively as if it existed during the frozen research evaluation.

## Shared verification core

Capabilities that can serve both tracks include:

- deterministic source identity;
- structured comparison;
- numeric reconciliation;
- semantic/field-level change detection;
- evidence traceability;
- human-in-the-loop review;
- regression testing;
- reproducible evidence packaging.

## Public repository rule

The integration repository may contain public or publication-safe material, tests, synthetic fixtures and public-source examples.

Do not publish material merely because it exists in an operational workflow. Publication requires that the source and the resulting artifact are appropriate for public release.

## Writing rule

When describing the project publicly, use language such as:

- `research-validated verification core` for the demonstrated research scope;
- `operational MVP` for the FY2570 practical verifier;
- `future operational workflow` for FY2571+ builder/generator capabilities.

Avoid language implying that the thesis has already validated every capability in the broader product vision.
