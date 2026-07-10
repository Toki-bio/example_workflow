# Cardiomyopathy gene panel

This is the worked example panel used throughout this repo — see
[`panels/README.md`](../README.md) for the general panel pattern this fits into.

`cardiomyopathy_genes.txt` — the 26-gene panel carried over unchanged from the original
DRAGEN-based pipeline's clinical report generator.

`cardiomyopathy_genes_grch38.bed` — GRCh38 coordinates (+/-1kb flanking), **currently populated
only for the two genes used by the synthetic test case** (`MYBPC3`, `MYH7`), verified against
NCBI Gene / OMIM / Ensembl. If you extend the test case or run this pipeline against real WGS
data restricted to the full panel, add the remaining 24 genes' coordinates and re-verify all
of them against a current GRCh38 annotation release before relying on them for anything beyond
this technical demo.
