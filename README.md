# example_workflow — CPU-only germline variant-calling & clinical-panel pipeline

A CPU-only, license-free, open-source pipeline for germline variant calling and gene-panel
clinical reporting from sequencing (FASTQ) data — with the panel definition, reference, and
annotation sources all swappable via configuration rather than hardcoded. Originally built as a
drop-in replacement for an Illumina DRAGEN FPGA-accelerated pipeline that lost its
license/subscription; the DRAGEN case study is documented, but the pipeline itself is not
cardio-specific.

**No real patient data, sample identifiers, or licensed reference data are included anywhere
in this repository.** See [`docs/`](docs/) for details.

## Why this exists

DRAGEN (FPGA bitstream + a data-processing subscription) is one way to go from paired-end WGS
FASTQ to annotated, clinically-filtered variant calls for a gene panel. When a DRAGEN
subscription lapses — or was never available in the first place — you need a CPU-only
replacement that keeps the same inputs/outputs and clinical logic without specialized hardware or
a paid license. This repo documents that replacement, generalized so the same pipeline can serve
any gene panel or clinical/research goal, not just the one it was first built for.

See [`docs/DATA_TYPES_AND_WORKFLOWS.md`](docs/DATA_TYPES_AND_WORKFLOWS.md) for a broader,
tool-neutral introduction to the genomic data types and workflows this pipeline sits within —
useful background if you're new to this space.

## What's here

| Path | Contents |
|---|---|
| [`docs/DATA_TYPES_AND_WORKFLOWS.md`](docs/DATA_TYPES_AND_WORKFLOWS.md) | Introduction to genomic data types (sequencing vs. array), tool landscape (DRAGEN vs. samtools/GATK vs. PLINK, etc.), and goal/tier matrix — what's implemented here vs. roadmap |
| [`docs/ORIGINAL_DRAGEN_PIPELINE.md`](docs/ORIGINAL_DRAGEN_PIPELINE.md) | Case study: reconstruction of a real FPGA-accelerated DRAGEN pipeline, as run in production |
| [`docs/DRAGEN_TO_OSS_MAPPING.md`](docs/DRAGEN_TO_OSS_MAPPING.md) | Stage-by-stage table mapping each DRAGEN feature to its open-source replacement |
| [`panels/`](panels/) | Swappable gene-panel configs (gene list + BED region file); ships with a cardiomyopathy/channelopathy panel as the worked example |
| [`envs/environment.yml`](envs/environment.yml) | Conda environment: bwa, samtools, bcftools, GATK4, snpEff, fastp/fastqc |
| [`pipeline/`](pipeline/) | The pipeline itself: align → call variants (bcftools + GATK4) → annotate (snpEff/VEP + ClinVar) → filter pathogenic calls → case/control aggregate → HTML report |
| [`test_case/`](test_case/) | A small, synthetic, shareable 2-sample demo (1 case + 1 control) using the cardiomyopathy example panel, running the whole pipeline end-to-end |

## Quick start (synthetic demo)

```bash
conda env create -f envs/environment.yml
conda activate variant-pipeline

cd test_case
./run_demo.sh
python check_demo.py results
```

This aligns two small synthetic samples against a ~48kb slice of real GRCh38 sequence (MYBPC3
+ MYH7), calls variants, annotates against a real published ClinVar pathogenic variant, and
generates an interactive HTML clinical report per sample — end to end in well under a minute,
no FPGA or license required. See [`test_case/README.md`](test_case/README.md) for details.

## Running on real data, or with a different panel

```bash
export REF_FASTA=/path/to/hg38.fa
export CLINVAR_VCF=/path/to/clinvar_grch38.vcf.gz   # https://ftp.ncbi.nlm.nih.gov/pub/clinvar/vcf_GRCh38/
export PANEL_GENES=/path/to/your_panel_genes.txt    # defaults to panels/cardiomyopathy/...
export PANEL_BED=/path/to/your_panel_grch38.bed
export PANEL_NAME="Your Panel Name"
pipeline/run_pipeline.sh my_cohort_manifest.tsv
```

`my_cohort_manifest.tsv` is tab-separated: `sample_id  case|control  R1.fastq.gz  R2.fastq.gz`
(see `test_case/samples.tsv` for the format). See [`panels/README.md`](panels/README.md) for how
to define a new panel — no pipeline code changes needed.

## Known limitations / roadmap

- Only the sequencing (FASTQ) input path is implemented. The array/genotyping path (IDAT/CEL →
  PLINK → imputation) is documented as a design in
  [`docs/DATA_TYPES_AND_WORKFLOWS.md`](docs/DATA_TYPES_AND_WORKFLOWS.md) but not yet built here.
- No equivalent to DRAGEN's proprietary pangenome graph-reference mode is provided (linear
  GRCh38 only) — see `docs/DRAGEN_TO_OSS_MAPPING.md`.
- Exact variant calls and QC metrics will differ slightly from DRAGEN's output, as expected
  when comparing any two independently-implemented aligners/callers. Cross-validation against
  an original DRAGEN pipeline's pathogenic-variant calls on real samples (kept on the source
  infrastructure, never included here) is a recommended follow-up before relying on this
  pipeline for anything beyond technical demonstration.
- Annotation uses independently-downloaded public resources (ClinVar, and optionally
  snpEff/VEP), not Illumina's licensed Nirvana data bundle.
- Only two variant callers (bcftools, GATK4) are wired in; pluggable alternate callers (e.g.
  DeepVariant) and workflow-manager orchestration (Nextflow/Snakemake) are roadmap items.

## License

See [`LICENSE`](LICENSE). The example gene panel, pipeline logic, and clinical filtering rules
are provided as-is for technical/educational purposes and are **not validated for clinical use**.
