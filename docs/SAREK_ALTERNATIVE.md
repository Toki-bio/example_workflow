# nf-core/sarek as an alternative sequencing engine

This repo ships a **minimal bash pipeline** (`pipeline/`) for learning, demos, and DRAGEN
replacement. For production-scale germline (or somatic) variant calling, **[nf-core/sarek](https://nf-co.re/sarek/3.9.0/)**
is a documented **alternative pathway** — same starting point (FASTQ), same convergence point
(annotated VCF), different engine in the middle.

The **clinical layer in this repo** (pathogenic filter, case/control aggregate, HTML report —
stages 05–07) is **shared** regardless of which engine produced the VCF.

## When to use which

| | Bash pipeline (`pipeline/`) | nf-core/sarek |
|---|---|---|
| **Best for** | Demo, teaching, small cohorts, DRAGEN migration story | Production WGS/WES, HPC/cloud, multi-caller QC |
| **Orchestration** | Bash + conda | Nextflow + Docker/Singularity |
| **Setup complexity** | Low | Medium (Nextflow + containers + reference cache) |
| **QC / provenance** | Minimal | MultiQC, restart/resume, CI-tested releases |
| **Callers** | bcftools + GATK4 HC | Many (`--tools haplotypecaller,deepvariant,strelka,...`) |
| **Preprocessing** | fastp + bwa + samtools markdup | GATK BQSR path (best practice) |
| **Clinical report** | Built in (stages 05–07) | **Not included** — use this repo's Python scripts on sarek VCFs |
| **Runnable in this repo** | Yes (`test_case/run_demo.sh`) | Documented only — run sarek externally |

## Hybrid architecture (recommended for production)

```
FASTQ
  │
  ├─► pipeline/run_pipeline.sh          ──► annotated VCF ──┐
  │                                                         │
  └─► nextflow run nf-core/sarek ...    ──► annotated VCF ──┤
                                                              ▼
                                    pipeline/05_filter_pathogenic.py
                                    pipeline/07_generate_report.py
                                    pipeline/06_aggregate_case_control.py
```

## Running sarek (outline)

Prerequisites: [Nextflow](https://www.nextflow.io/), Docker or Singularity, reference genome
cache (iGenomes or custom).

**1. Samplesheet** (CSV, one row per FASTQ pair) — see
[sarek usage docs](https://nf-co.re/sarek/3.9.0/docs/usage):

```csv
patient,sample,lane,fastq_1,fastq_2
case1,case1,L001,/data/fastq/case1_R1.fastq.gz,/data/fastq/case1_R2.fastq.gz
control1,control1,L001,/data/fastq/control1_R1.fastq.gz,/data/fastq/control1_R2.fastq.gz
```

**2. Run** (germline example):

```bash
nextflow run nf-core/sarek -r 3.9.0 \
  -profile docker \
  --input samplesheet.csv \
  --outdir sarek_results \
  --genome GRCh38 \
  --tools haplotypecaller,snpeff
```

Test your setup first with sarek's built-in test profile:

```bash
nextflow run nf-core/sarek -r 3.9.0 -profile test,docker --outdir sarek_test
```

**3. Clinical handoff** — point this repo's scripts at sarek's annotated VCF per sample
(typical path under `--outdir`, varies by `--tools`):

```bash
# Example paths — adjust to your sarek version and --tools selection
SAREK_VCF="sarek_results/variant_calling/haplotypecaller/case1/case1.haplotypecaller.vcf.gz"

python3 pipeline/05_filter_pathogenic.py \
  "$SAREK_VCF" case1 case \
  results/case1.case.pathogenic.jsonl

python3 pipeline/07_generate_report.py \
  "$SAREK_VCF" case1 panels/cardiomyopathy/cardiomyopathy_genes.txt \
  results/case1.report.html "Cardiomyopathy"
```

Repeat per sample, then aggregate:

```bash
python3 pipeline/06_aggregate_case_control.py \
  "results/*.pathogenic.jsonl" \
  results/aggregated_pathogenic_variants.json
```

## What sarek does not replace

- **Panel clinical logic** (Pathogenic/Likely pathogenic filter, panel gene highlighting, VUS rules)
- **Case vs control aggregation** (`aggregated_pathogenic_variants.json`)
- **HTML reports** (`*.report.html`)
- **DRAGEN migration documentation** in this repo

## References

- [nf-core/sarek 3.9.0](https://nf-co.re/sarek/3.9.0/) — pipeline docs, parameters, outputs
- [Sarek usage](https://nf-co.re/sarek/3.9.0/docs/usage) — samplesheet format, profiles
- [Nextflow setup](https://www.nextflow.io/docs/latest/getstarted.html) — install Nextflow
