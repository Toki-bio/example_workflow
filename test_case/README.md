# Technical demo: 2-sample synthetic cardiomyopathy panel test case

A minimal, fully synthetic, shareable example of the FPGA-free replacement pipeline —
safe to hand to colleagues, run on a laptop, and use as a teaching example. **Contains no
real patient data.**

## What's in here

- `refs/panel_region.fa` — a small "mini genome" (~48 kb) built from **real GRCh38 sequence**
  for two cardiomyopathy panel genes (MYBPC3, MYH7). See `refs/README.md` for exact coordinates.
- `refs/clinvar_panel_subset.vcf` — a single, real, publicly documented ClinVar Pathogenic
  variant (MYBPC3 p.Arg502Trp / rs375882485 / VCV000042540), used to make the demo clinically
  meaningful without needing the full ClinVar database.
- `simulate_reads.py` — generates the two synthetic samples from the mini genome, no external
  tools required (pure Python).
- `fastq/` — the generated synthetic reads (already committed, ~1.2 MB total; regenerate any
  time with `python simulate_reads.py`):
  - `case1` — simulated as a **heterozygous carrier** of the MYBPC3 pathogenic variant
  - `control1` — simulated from the unmodified reference (no variant)
- `samples.tsv` — the manifest fed to `pipeline/run_pipeline.sh`
- `run_demo.sh` — runs the whole pipeline end-to-end on these two samples
- `check_demo.py` — asserts the pipeline correctly finds the pathogenic variant in `case1`
  and correctly does *not* find it in `control1`

## Running it

Requires the conda environment from `../envs/environment.yml` (or just `bwa`, `samtools`,
`bcftools`, `htslib`/`tabix`, and Python 3 on `PATH` — `snpEff`/`gatk`/`vep` are optional for
this minimal demo and are skipped automatically if not installed):

```bash
conda env create -f ../envs/environment.yml
conda activate variant-pipeline

./run_demo.sh
python check_demo.py results
```

Expected result: `case1.report.html` shows one Pathogenic hit at `demo_chr11_MYBPC3:12292`
(real-world equivalent: GRCh38 chr11:47,342,698 G>A, MYBPC3 p.Arg502Trp); `control1.report.html`
does not. `aggregated_pathogenic_variants.json` shows `case_count: 1, control_count: 0` for
that variant.

Note: if `snpEff` isn't installed (or has no database for the custom demo contigs), the
pipeline automatically falls back to ClinVar-only annotation — the pathogenic call and
case/control comparison still work correctly, but the report's gene-symbol/consequence/impact
columns and the "PANEL" badge will be blank for the demo (they rely on snpEff's gene
annotation). Install snpEff's `GRCh38.mane.1.2.ensembl` database and use the real hg38
reference for full gene-level annotation on real data.

## Why this is safe to share

- No real sequencing reads, sample IDs, or patient information anywhere in this directory.
- The only "real" biological content is (a) public GRCh38 reference sequence and (b) a single
  variant's public ClinVar/dbSNP identifiers and clinical classification — both freely
  redistributable, well-published facts, not derived from any patient's data.
- Runtime is seconds to low minutes on a laptop; no FPGA, no DRAGEN license, no cloud costs.
