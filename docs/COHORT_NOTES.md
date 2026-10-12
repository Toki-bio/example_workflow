# Cohort-specific run notes

Rules that apply to every run on a given cohort, in addition to whatever panel the referral asks
for. They are enforced through `ATTENTION_GENES` (see [`pipeline/00_config.sh`](../pipeline/00_config.sh))
rather than through memory: a gene on this list is reviewed, highlighted and accounted for in
every report, and a run whose configuration could never call it does not start.

Add a section per cohort. Record the date and who set the rule.

## Uzbek samples: lysosomal storage disorder genes

**Rule (set 2026-10-12 by the project owner):** in every run on Uzbek samples pay specific attention
to **GBA1, GAA, GLA, GALC, IDUA, SMPD1**, whatever the main panel of the run.

The six genes and their GRCh38 regions are shipped as
[`panels/lysosomal_storage/`](../panels/lysosomal_storage/) (gene list, BED, and per-gene
interpretation notes: GBA1/GBAP1 pseudogene mapping, GAA and IDUA pseudodeficiency alleles,
X-linked GLA, the GALC 30 kb deletion this pipeline cannot see, the SMPD1 exon 1 repeat).

### How to run

```bash
# main panel of the run as usual (PANEL_GENES / PANEL_BED / PANEL_NAME), plus:
export ATTENTION_GENES="$PWD/panels/lysosomal_storage/lysosomal_storage_genes.txt"

# With RESTRICT_TO_PANEL=1 the six regions must be in PANEL_BED, or run_pipeline.sh refuses to start:
cat panels/<main_panel>/<main_panel>_genes_grch38.bed \
    <(grep -v '^#' panels/lysosomal_storage/lysosomal_storage_genes_grch38.bed) \
    > /path/to/combined_grch38.bed
export PANEL_BED=/path/to/combined_grch38.bed
export RESTRICT_TO_PANEL=1

pipeline/run_pipeline.sh my_uzbek_cohort_manifest.tsv
```

If the run is only about these six genes, use the panel directly instead:
`PANEL_GENES=panels/lysosomal_storage/lysosomal_storage_genes.txt`,
`PANEL_BED=panels/lysosomal_storage/lysosomal_storage_genes_grch38.bed`, `PANEL_NAME="Lysosomal storage"`.

For stage 08 triage the same file is picked up automatically (`TRIAGE_REQUIRE_GENES` defaults to
`ATTENTION_GENES`), so the six genes are in the phenotype gene set even when the HPO terms and
PanelApp keywords of the referral do not point at them. Add `lysosomal` to `TRIAGE_KEYWORDS` when
the phenotype allows it: PanelApp then supplies the mode of inheritance and the green rating, which
the ranking uses (single heterozygotes in recessive genes are scored as carriers).

### What the pipeline does with the rule

| Stage | Effect of `ATTENTION_GENES` |
|---|---|
| `run_pipeline.sh` | Fails before alignment when `RESTRICT_TO_PANEL=1` and `PANEL_BED` has no region for one of the genes (column 4 of the BED). The README warns that a narrow BED silently drops variants; for these genes that is now an error, not a warning. |
| 07 report | Every variant in the six genes is listed whatever its ClinVar label, marked **ATTENTION**, and sorted above other rows of the same significance. A paragraph names the attention genes and, explicitly, those with **no variant listed**. Previous symbols are matched (`GBA1 GBA`). |
| 08 triage | The genes join `genes.tsv` with source `required` and are recorded in `manifest.json` under `genes.required`; their variants are ranked with the phenotype genes, not in `outside_phenotype.tsv`. |

### What to check by hand on every Uzbek report

1. The report's attention paragraph. A gene listed under "No variant listed for" needs a coverage
   check of its exons (and of the BED when calling was restricted) before "no finding" is written.
2. All six are recessive or X-linked: a single heterozygous variant is a carrier result unless a
   second variant is found in the same gene. The pipeline sees SNVs and small indels only; GALC in
   particular has a common 30 kb deletion that needs a CNV assay.
3. GBA1 calls: inspect the pileup for GBAP1 mis-mapping (MAPQ, allele balance) before reporting.
4. GAA, IDUA, GLA: recognise the pseudodeficiency / reduced-activity alleles listed in
   [`panels/lysosomal_storage/README.md`](../panels/lysosomal_storage/README.md) and label them as such.
5. GLA genotypes on chrX against the sample's sex (no sex is passed to `bcftools call`).

Final classification stays with the clinical geneticist (ACMG/AMP from primary evidence, enzyme
assay where available, family testing).
