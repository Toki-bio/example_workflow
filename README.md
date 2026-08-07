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
| [`envs/environment.yml`](envs/environment.yml) | Conda environment: python3, bwa, samtools, bcftools, fastp, htslib (tabix/bgzip) (GATK/snpEff optional, install separately) |
| [`pipeline/`](pipeline/) | The pipeline itself, per sample: align → call variants (bcftools, + GATK4 as an optional cross-check) → annotate (snpEff/VEP + ClinVar) → filter pathogenic calls → HTML report. After all samples: case/control aggregate. |
| [`test_case/`](test_case/) | A small, synthetic, shareable 2-sample demo (1 case + 1 control) using the cardiomyopathy example panel, running the whole pipeline end-to-end |

## Quick start (synthetic demo)

```bash
REPO="$HOME/example_workflow"
if [[ ! -d "$REPO/.git" ]]; then
  git clone https://github.com/Toki-bio/example_workflow.git "$REPO"
fi
cd "$REPO"
git pull origin main

# Create env only if missing
conda env list | awk '{print $1}' | grep -qx variant-pipeline \
  || conda env create -f envs/environment.yml

source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate variant-pipeline
bash pipeline/verify_tools.sh

cd test_case
bash run_demo.sh
python3 check_demo.py results
```

**Required on PATH:** `bwa`, `samtools`, `bcftools`, `fastp`, `tabix`, `bgzip`, `python3`  
**Optional:** `gatk` (secondary caller), `snpEff` (gene annotation — ClinVar still runs without it)

If you already have most tools in another conda env, run `bash pipeline/verify_tools.sh` to see what is missing.

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
                                                 # (bcftools has no built-in T2T-CHM13 preset;
                                                 #  if REF_FASTA is T2T, use GRCh38 here for now
                                                 #  and check `bcftools call --ploidy ?` for updates)
export PANEL_GENES=/path/to/your_panel_genes.txt
export PANEL_BED=/path/to/your_panel.bed        # coordinates must match REF_FASTA build
export PANEL_NAME="Your Panel Name"
export SNPEFF_DB=GRCh38.mane.1.2.ensembl      # snpEff DB for your build
export RESTRICT_TO_PANEL=1                      # recommended for real WGS: call only PANEL_BED
pipeline/run_pipeline.sh my_cohort_manifest.tsv
```

Stage 04 automatically renames ClinVar contigs when needed (`1` ↔ `chr1`) so NCBI ClinVar
annotates against UCSC-style references. Without a snpEff database, gene symbols fall back to
ClinVar `GENEINFO`.


`my_cohort_manifest.tsv` is tab-separated: `sample_id  case|control  R1.fastq[.gz]  R2.fastq[.gz]`
(see `test_case/samples.tsv` for the format). R1/R2 accept plain `.fastq` or `.fastq.gz`; the
align step auto-resolves paths if the extension is omitted. See [`panels/README.md`](panels/README.md) for how
to define a new panel — no pipeline code changes needed.

### Preparing the real-data inputs above

These paths are not auto-generated by this pipeline; you obtain them once per reference build:

- **`REF_FASTA`**: a FASTA for your build (e.g. from Ensembl/UCSC/NCBI), then index it —
  `bwa index REF_FASTA` and `samtools faidx REF_FASTA` (`pipeline/01_prepare_reference.sh` does
  this automatically on first run if the index files are missing, but the FASTA itself must
  already be downloaded).
- **`CLINVAR_VCF`**: download from NCBI's ClinVar FTP (e.g.
  `https://ftp.ncbi.nlm.nih.gov/pub/clinvar/vcf_GRCh38/clinvar.vcf.gz`, or `vcf_GRCh37` for that
  build), then `tabix -p vcf clinvar.vcf.gz`.
- **`SNPEFF_DB`** (optional): `snpEff download <db-name>` (e.g. `GRCh38.mane.1.2.ensembl`) —
  only needed if you want transcript/consequence annotation; ClinVar annotation works without it.

No expected-runtime/memory sizing is published yet for real WES/WGS-scale data (only the
synthetic demo's "well under a minute" is measured); size your run conservatively and monitor
the first sample before committing to a full cohort.

## Troubleshooting

- **`conda env create` fails / hangs on solving.** Try `conda config --set channel_priority
  strict` first, or use `mamba env create -f envs/environment.yml` instead of `conda`.
- **`ERROR: ... .fa.fai not found` / bwa index errors.** `REF_FASTA` hasn't been indexed yet —
  see "Preparing the real-data inputs" above; `01_prepare_reference.sh` builds missing indexes
  automatically but the FASTA itself must exist first.
- **ClinVar annotation transfers nothing (no CLNSIG on any variant).** Almost always a contig
  naming mismatch (`1` vs `chr1`) between `REF_FASTA`/your VCF and `CLINVAR_VCF` that stage 04's
  auto-harmonization didn't catch, or `CLINVAR_VCF` is for the wrong genome build. Confirm with
  `bcftools query -f '%CHROM\n' "$CLINVAR_VCF" | head -1` vs the same for your annotated VCF.
- **`gatk: command not found` / GATK step silently skipped.** GATK is optional (see Required vs
  Optional above) — `03_call_variants.sh` skips it automatically when absent and continues with
  the bcftools-only path. Install GATK4 and put it on `PATH` if you want the cross-check.
- **snpEff step logs a warning and continues with ClinVar-only annotation.** Either snpEff isn't
  installed, or `SNPEFF_DB` hasn't been downloaded (`snpEff download <db-name>`) — this is
  non-fatal by design; gene symbols fall back to ClinVar's `GENEINFO` field.
- **Still stuck?** Run `bash pipeline/verify_tools.sh` first — it reports exactly which required
  and optional tools are missing before you dig further.

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
