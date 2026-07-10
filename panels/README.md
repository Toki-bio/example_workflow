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
- A carrier-screening panel.
- An oncology gene panel.
- Any other curated gene set relevant to a given clinical or research question.

## Directory layout

Each panel lives in its own subdirectory:

```
panels/
  <panel_name>/
    <panel_name>_genes.txt        # one gene symbol per line
    <panel_name>_grch38.bed       # matching GRCh38 coordinates (chrom, start, end, gene, source)
    README.md                     # provenance/notes specific to this panel
```

## Adding a new panel

1. Create `panels/<your_panel_name>/`.
2. Add a plain-text gene list (one HGNC gene symbol per line).
3. Add a BED file with GRCh38 coordinates for those genes (verify against a current Ensembl/NCBI
   annotation release — coordinates drift between genome annotation versions).
4. Point `PANEL_GENES` and `PANEL_BED` (see
   [`pipeline/00_config.sh`](../pipeline/00_config.sh)) at your new files, either by exporting the
   environment variables before running the pipeline, or by editing the defaults.
5. No changes to pipeline code are required — panel selection is configuration, not logic.

See [`docs/DATA_TYPES_AND_WORKFLOWS.md`](../docs/DATA_TYPES_AND_WORKFLOWS.md) for how a panel-based
clinical workflow fits alongside other goal tiers (population frequency, unrestricted WGS,
PRS/GWAS, pharmacogenomics) that this pipeline does not (yet) cover.
