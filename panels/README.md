# Panels

A "panel" in this pipeline is nothing more than **a gene list + a matching BED file of genomic
regions**. The pipeline itself has no built-in notion of "cardiomyopathy," "carrier screening," or
any other clinical purpose — it reads whichever panel config it's pointed at via the
`PANEL_GENES` / `PANEL_BED` variables in
[`pipeline/00_config.sh`](../pipeline/00_config.sh), and everything downstream (region-restricted
calling where applicable, clinical filtering, HTML report generation) follows that config.

This means the same pipeline can serve very different goals just by swapping the panel:

- A cardiomyopathy/channelopathy panel (shipped here as the worked example, see
  [`cardiomyopathy/`](cardiomyopathy/)).
- A lysosomal storage disorder panel (GBA1, GAA, GLA, GALC, IDUA, SMPD1; see
  [`lysosomal_storage/`](lysosomal_storage/)), shipped because every run on Uzbek samples must
  review these six genes on top of its main panel ([`docs/COHORT_NOTES.md`](../docs/COHORT_NOTES.md)).
- A carrier-screening panel.
- An oncology gene panel.
- Any other curated gene set relevant to a given clinical or research question.

## Directory layout

Each panel lives in its own subdirectory:

```
panels/
  <panel_name>/
    <panel_name>_genes.txt        # one gene per line: current HGNC symbol, then optional aliases
    <panel_name>_regions.bed       # coordinates for that build (e.g. _grch38.bed, _grch37.bed)
    README.md                     # provenance/notes specific to this panel
```

## Adding a new panel

1. Create `panels/<your_panel_name>/`.
2. Add a plain-text gene list: one gene per line, the current HGNC symbol first. Further
   whitespace-separated tokens on the same line are previous symbols or aliases that stage 07 also
   matches (e.g. `GBA1 GBA`), so an older snpEff database or ClinVar release is not missed. Lines
   starting with `#` are comments.
3. Add a BED file with coordinates for those genes **on the same assembly as your `REF_FASTA`**
   (verify against a current Ensembl/NCBI annotation for that build — coordinates differ between
   GRCh37, GRCh38, T2T, etc.).
4. Point `PANEL_GENES` and `PANEL_BED` (see
   [`pipeline/00_config.sh`](../pipeline/00_config.sh)) at your new files, either by exporting the
   environment variables before running the pipeline, or by editing the defaults.
5. No changes to pipeline code are required — panel selection is configuration, not logic.

## Attention genes on top of a panel

`ATTENTION_GENES` (same gene-list format) names genes that must be reviewed in every run of a
cohort whatever the panel is: their variants are always listed and marked `ATTENTION` in the stage 07
report, the report names those with no variant, stage 08 adds them to its gene set, and a
`RESTRICT_TO_PANEL=1` run refuses to start if `PANEL_BED` lacks their regions. Cohort rules are
recorded in [`docs/COHORT_NOTES.md`](../docs/COHORT_NOTES.md).

See [`docs/DATA_TYPES_AND_WORKFLOWS.md`](../docs/DATA_TYPES_AND_WORKFLOWS.md) for how a panel-based
clinical workflow fits alongside other goal tiers (population frequency, unrestricted WGS,
PRS/GWAS, pharmacogenomics) that this pipeline does not (yet) cover.
