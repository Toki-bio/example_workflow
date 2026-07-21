# example_workflow — CPU-only germline variant-calling & clinical-panel pipeline

A CPU-only, license-free, open-source pipeline for germline variant calling and gene-panel
clinical reporting from sequencing (FASTQ) data — with the panel definition, reference, and
annotation sources all swappable via configuration rather than hardcoded. Originally built as a
drop-in replacement for an Illumina DRAGEN FPGA-accelerated pipeline that lost its
license/subscription; the DRAGEN case study is documented, but the pipeline itself is not
cardio-specific.

**No real patient data, sample identifiers, or licensed reference data are included anywhere
in this repository.** See [`docs/`](docs/) for details.

## Interactive guide (GitHub Pages)

**[toki-bio.github.io/example_workflow](https://toki-bio.github.io/example_workflow/)** — a
step-by-step walkthrough with live-updating, copy-pasteable commands. Adjust paths, panel, sample
IDs, and threads in the settings panel; every stage command updates as you type.

To publish the site (one-time): GitHub repo **Settings → Pages → Build and deployment → Deploy
from branch `main`, folder `/docs`**.

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
| [`docs/index.html`](docs/index.html) | Interactive GitHub Pages guide — stage-by-stage walkthrough with adjustable, copy-pasteable commands |
| [`docs/DATA_TYPES_AND_WORKFLOWS.md`](docs/DATA_TYPES_AND_WORKFLOWS.md) | Introduction to genomic data types (sequencing vs. array), tool landscape (DRAGEN vs. samtools/GATK vs. PLINK, etc.), and goal/tier matrix — what's implemented here vs. roadmap |
| [`docs/ORIGINAL_DRAGEN_PIPELINE.md`](docs/ORIGINAL_DRAGEN_PIPELINE.md) | Case study: reconstruction of a real FPGA-accelerated DRAGEN pipeline, as run in production |
| [`docs/DRAGEN_TO_OSS_MAPPING.md`](docs/DRAGEN_TO_OSS_MAPPING.md) | Stage-by-stage table mapping each DRAGEN feature to its open-source replacement |
| [`docs/SAREK_ALTERNATIVE.md`](docs/SAREK_ALTERNATIVE.md) | Alternative sequencing engine: [nf-core/sarek](https://nf-co.re/sarek/3.9.0/) (Nextflow); clinical stages 05–07 shared |
| [`panels/`](panels/) | Swappable gene-panel configs (gene list + BED region file); ships with a cardiomyopathy/channelopathy panel as the worked example |
| [`envs/environment.yml`](envs/environment.yml) | Conda environment: bwa, samtools, bcftools, GATK4, snpEff, fastp/fastqc |
| [`pipeline/`](pipeline/) | The pipeline itself: align → call variants (bcftools + GATK4) → annotate (snpEff/VEP + ClinVar) → filter pathogenic calls → case/control aggregate → HTML report |
| [`test_case/`](test_case/) | A small, synthetic, shareable 2-sample demo (1 case + 1 control) using the cardiomyopathy example panel, running the whole pipeline end-to-end |

## Quick start (synthetic demo)

```bash
git clone https://github.com/Toki-bio/example_workflow.git
cd example_workflow

conda env create -f envs/environment.yml
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate variant-pipeline

# Confirm tools are on PATH (do NOT run bare `bwa` — that only prints usage help)
bash pipeline/verify_tools.sh

cd test_case
./run_demo.sh
python3 check_demo.py results
```

This aligns two small synthetic samples against a ~48kb slice of real GRCh38 sequence (MYBPC3
+ MYH7), calls variants, annotates against a real published ClinVar pathogenic variant, and
generates an interactive HTML clinical report per sample — end to end in well under a minute,
no FPGA or license required. See [`test_case/README.md`](test_case/README.md) for details.

**Working directory:** clone the repo and run commands from that tree. Relative paths in the
interactive guide assume the repo root (the folder that contains `pipeline/` and `test_case/`).
The demo script (`test_case/run_demo.sh`) `cd`s itself and needs no path fiddling.

## Running on real data, or with a different panel

```bash
export REF_FASTA=/path/to/reference.fa          # GRCh37/hg19, GRCh38/hg38, T2T-CHM13, etc.
export CLINVAR_VCF=/path/to/clinvar.vcf.gz      # same build as REF_FASTA (NCBI: vcf_GRCh38, vcf_GRCh37, …)
export BCFTOOLS_PLOIDY=GRCh38                   # or GRCh37 — must match REF_FASTA
export PANEL_GENES=/path/to/your_panel_genes.txt
export PANEL_BED=/path/to/your_panel.bed        # coordinates must match REF_FASTA build
export PANEL_NAME="Your Panel Name"
export SNPEFF_DB=GRCh38.mane.1.2.ensembl      # snpEff DB for your build
pipeline/run_pipeline.sh my_cohort_manifest.tsv
```

`my_cohort_manifest.tsv` is tab-separated: `sample_id  case|control  R1.fastq[.gz]  R2.fastq[.gz]`
(see `test_case/samples.tsv` for the format). R1/R2 accept plain `.fastq` or `.fastq.gz`; the
align step auto-resolves paths if the extension is omitted. See [`panels/README.md`](panels/README.md) for how
to define a new panel — no pipeline code changes needed.

## Known limitations / roadmap

- Only the sequencing (FASTQ) input path is implemented. The array/genotyping path (IDAT/CEL →
  PLINK → imputation) is documented as a design in
  [`docs/DATA_TYPES_AND_WORKFLOWS.md`](docs/DATA_TYPES_AND_WORKFLOWS.md) but not yet built here.
- No equivalent to DRAGEN's proprietary pangenome graph-reference mode is provided (linear
  reference only — any build you configure via `REF_FASTA`, not pangenome graphs) — see
  `docs/DRAGEN_TO_OSS_MAPPING.md`.
- **Build consistency:** `REF_FASTA`, ClinVar VCF, panel BED, `SNPEFF_DB`, and `BCFTOOLS_PLOIDY`
  must all refer to the same genome assembly (e.g. all GRCh38 or all GRCh37). The shipped demo
  uses GRCh38; switching to GRCh37 or T2T means updating every coordinate-dependent resource, not
  just the FASTA.
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
