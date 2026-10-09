# Changelog

## Unreleased (branch v2)

### Fixed
- **A ClinVar aggregate label no longer removes a variant.** Stage 05 used to keep only
  `CLNSIG = Pathogenic / Likely_pathogenic`, so a variant with e.g. 9 P/LP submissions and one old
  VUS (aggregate "Conflicting classifications of pathogenicity") was dropped without a trace and the
  report could say nothing was found. Stage 05 now emits two tiers: **T1a** (aggregate P/LP) and
  **T1b** (aggregate Conflicting with at least one P/LP submission, from `CLNSIGCONF`). Each record
  carries `tier` and the per-class submission counts.
- Calls failing the caller's FILTER are kept and marked `filter_pass: false` (stage 05) and listed
  with their FILTER value (stage 07), instead of being dropped.
- Stage 07 no longer hides ClinVar Benign / Likely benign variants inside the panel genes; they are
  shown with their label. Benign variants outside the panel stay out.
- Stage 05 no longer skips a record when an INFO key (for example `ANN`, when snpEff was skipped) is
  not declared in the VCF header.

### Added
- `CLNSIGCONF` is transferred by stage 04 when the ClinVar VCF defines it.
- Stage 07 report carries a "Scope and limits" paragraph.
- `tests/`: offline unit tests for the tier logic and an end-to-end 05 -> 07 test on a tiny annotated
  VCF; run in CI.

### Known gaps (see PLAN_example_workflow_revision_v2.md)
- Gene sets are still the shipped panel list, not PanelApp/HPO-derived; no ClinVar-blind candidate tier
  (T2) in the pipeline yet; annotation provenance (`versions.json`) and the sarek path are not yet
  part of the repo; no GIAB benchmark.
