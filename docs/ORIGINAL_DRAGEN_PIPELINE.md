# Reconstructed original pipeline (Illumina DRAGEN, FPGA-accelerated)

This document reconstructs the pipeline as it was actually run in production, based on
`/var/log/dragen.log`, the run scripts under the analysis directory, and the downstream
annotation/reporting scripts. It is kept here purely as a historical/technical reference —
**no real sample data or patient identifiers are included anywhere in this repository.**

This is one specific case study (a cardiomyopathy gene panel run on DRAGEN), not a description of
the pipeline architecture in general. For the broader, panel-agnostic picture of genomic data
types and workflows this repo's replacement pipeline fits into, see
[`DATA_TYPES_AND_WORKFLOWS.md`](DATA_TYPES_AND_WORKFLOWS.md).

## 1. Purpose

Whole-genome paired-end FASTQ from patients (cases) and unaffected individuals (controls)
were processed to identify variants in a curated panel of cardiomyopathy / channelopathy
genes, with a downstream case-vs-control comparison of pathogenic/likely-pathogenic calls.

## 2. Inputs

- Paired-end Illumina WGS FASTQ (`*_R1_001.fastq.gz` / `*_R2_001.fastq.gz`), one pair per
  sample, roughly a dozen "case" samples and a similar number of "healthy" controls.
- Reference: GRCh38 (`hg38.fa`), with a DRAGEN hash table built including the ALT-contig
  liftover (`bwa-kit_hs38DH_liftover.sam`). A DRAGEN **pangenome** graph reference was later
  also built and used for a subset of runs (`--ref-dir /staging/Genomes/Human/pangenome/`).
- Annotation resource: Illumina Nirvana data bundle (proprietary, licensed content).

## 3. Stage 1 — DRAGEN germline pipeline (FPGA-accelerated)

Per sample, one `dragen` invocation performed mapping, sorting, duplicate marking, small
variant calling, and annotation in a single accelerated job:

```bash
dragen -f \
  -r "$REF_DIR" \
  -1 "$R1" -2 "$R2" \
  --enable-variant-caller true \
  --RGID "$rgid" --RGSM "$sample_id" \
  --output-directory "$OUT_DIR" \
  --output-file-prefix "$sample_id" \
  --enable-duplicate-marking true \
  --enable-map-align-output true \
  --enable-sort true \
  --enable-bam-indexing true \
  --intermediate-results-dir "$TMP_DIR" \
  --enable-variant-annotation true \
  --variant-annotation-data "$NIRVANA_DIR" \
  --variant-annotation-assembly GRCh38 \
  --validate-pangenome-reference=false
```

This single call replaces what, in an open-source pipeline, would normally be four to five
separate tools (aligner, sorter, duplicate marker, variant caller, annotator) — DRAGEN's FPGA
bitstream accelerates the map/align and variant-calling stages specifically.

Outputs per sample:
- Sorted, duplicate-marked, indexed BAM
- `*.hard-filtered.vcf` (+ `.pass` = PASS-only subset)
- Full DRAGEN QC metrics (`*wgs_coverage_metrics.csv`, `*ploidy_estimation_metrics.csv`,
  `*roh_metrics.csv`, mapping/dedup/variant-calling metrics, etc.)
- Nirvana-annotated output: `*.hard-filtered.vcf.annotated.json.gz`,
  `*_annotated_report.html`, `*_annotated_variants.tsv`

Two orchestration variants of the same script existed (`run_dragen.sh` for cases, and a copy
under `healthy/` for controls) plus a "pangenome" variant that only changed `--ref-dir` to the
graph reference and the output directory (`results_pangenome_cases` / `_controls`). A couple of
smaller one-off scripts (`run_dragen_transplant.sh`, `run_dragen_undetermined.sh`) ran the exact
same command against a single extra sample and against unassigned ("Undetermined") reads,
respectively — side investigations riding on the same base script.

## 4. Stage 2 — Pathogenic-variant extraction & case/control aggregation

Two near-duplicate `jq` scripts (`ann.sh` / `ann1.sh`) walked every sample's Nirvana
`*.json.gz`, kept only positions where any variant had a ClinVar significance matching
`pathogenic` (case-insensitively, covering "Pathogenic" and "Likely pathogenic"), tagged each
record with `sample_type` (`case`/`control`), and wrote one JSONL file per sample:

```
Cardio<N>.case.pathogenic.jsonl
Cardio<N>.control.pathogenic.jsonl
```

All per-sample JSONL files were then grouped by `(chromosome, position, refAllele, altAlleles)`
and aggregated into `aggregated_pathogenic_variants.json`, recording, for each distinct
pathogenic variant, how many case vs. control samples carried it — effectively a simple
case/control burden comparison for the pathogenic-variant set.

A second layer of scripts flattened the same JSONL into wide TSVs:
- `j2t.py` — flattens one Nirvana JSON record into a single TSV row, extracting ~70 fields:
  basic variant info, in-silico scores (PhyloP, GERP, DANN, REVEL implied via later report),
  ClinVar (ids/significance/phenotypes/review status/PubMed), MITOMAP, COSMIC, regulatory
  regions, population frequencies (gnomAD all + per-population, gnomAD-exome, 1000 Genomes
  per-population, TopMed), and canonical-transcript consequence/HGVS annotations.
- `jsonl2tsv.sh` — batch-runs `j2t.py` over all case/control JSONL files and concatenates them,
  with a sample-id header block per sample, into combined `cases.tsv` / `controls.tsv`.
- `table.sh` — a simpler flattening straight from the JSONL to one long TSV with
  `sample_id, sample_type, chromosome, position, refAllele, altAlleles, clinvar_id,
  clinvar_significance` — the "everything in one flat table" view.

## 5. Stage 3 — Clinical reporting

`single_sample_report.py` converts a sample's Nirvana JSON into an interactive, sortable,
filterable HTML report (DataTables.js), hard-coded around a **26-gene cardiomyopathy /
channelopathy panel**:

```
MYH7, TNNT2, LMNA, TPM1, MYBPC3, TNNI3, RYR2, PKP2, DSP, DSG2, DSC2, TMEM43,
SCN5A, PRDM16, PLN, DES, ACTC1, MYL2, MYL3, TNNC1, TTN, CASQ2, CALM1, CALM2, CALM3, TRDN
```

Clinical-relevance filter logic (default "clinical" mode):
- Always include: Pathogenic / Likely Pathogenic ClinVar calls
- Include: Variants of Uncertain Significance (VUS)
- Include: rare (gnomAD AF < 1%) coding variants **inside the panel genes**
- Include: HIGH-impact variants (frameshift, stop-gain, etc.) anywhere
- Include: MODERATE-impact variants with supporting evidence (REVEL > 0.5, etc.)
- Exclude: common variants (AF > 5%), Benign/Likely Benign, low quality
  (depth < 20, VAF < 0.2, quality < 30), MODIFIER-impact (intronic/UTR), synonymous

The report links out to dbSNP, ClinVar, and (optionally) a local IGV instance for each variant,
and supports CSV/Excel export. A companion `cardiopanel_visualizer.py` produces a panel-wide,
multi-sample (case vs. control) view over the same data.

## 6. Why this can no longer run as-is

- The DRAGEN CLI requires the FPGA bitstream board *and* an active Illumina DRAGEN software
  subscription/license; on the current server the `dragen` binary is no longer even resolvable
  on `PATH`, consistent with the subscription having lapsed.
- The variant-annotation step depends on Illumina's Nirvana data bundle, which is licensed
  content and not something that can be shipped in an open repository regardless of the FPGA
  question.

See [`OSS_PIPELINE.md`](./OSS_PIPELINE.md) for the CPU-only, license-free replacement and
[`DRAGEN_TO_OSS_MAPPING.md`](./DRAGEN_TO_OSS_MAPPING.md) for a stage-by-stage substitution table.
