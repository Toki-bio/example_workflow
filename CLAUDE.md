# Notes for Claude sessions in this repository

- **Cohort rules live in `docs/COHORT_NOTES.md` and are enforced via `ATTENTION_GENES`**, not from
  memory. Before configuring or running the pipeline on real samples, read that file and set
  `ATTENTION_GENES` for the cohort.
- **Uzbek samples:** pay specific attention to **GBA1, GAA, GLA, GALC, IDUA, SMPD1** in every run.
  Set `ATTENTION_GENES="$REPO/panels/lysosomal_storage/lysosomal_storage_genes.txt"`; with
  `RESTRICT_TO_PANEL=1` also append `panels/lysosomal_storage/lysosomal_storage_genes_grch38.bed`
  to `PANEL_BED`. Read `panels/lysosomal_storage/README.md` before interpreting calls in these genes.
- `docs/assets/scripts/` must stay byte-identical to the matching files in `pipeline/` (CI diffs
  them). After editing a pipeline script, copy it over.
- Validate before pushing: `python3 -X utf8 -m unittest discover -s tests -v` and
  `shellcheck pipeline/*.sh test_case/*.sh`.
