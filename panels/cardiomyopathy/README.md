# Cardiomyopathy gene panel

This is the worked example panel used throughout this repo — see
[`panels/README.md`](../README.md) for the general panel pattern this fits into.

`cardiomyopathy_genes.txt` — the 26-gene panel carried over unchanged from the original
DRAGEN-based pipeline's clinical report generator.

`cardiomyopathy_genes_grch38.bed` — GRCh38 gene spans for **all 26 genes** in the list, with
+/-1 kb flanks, sourced from Ensembl REST gene lookups (GRCh38). Use this BED with
`RESTRICT_TO_PANEL=1` for real WGS/panel runs against a `chr`-style GRCh38 reference.

If you retarget GRCh37 or T2T, regenerate coordinates for that assembly — do not reuse this BED.
