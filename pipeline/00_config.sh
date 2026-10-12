#!/bin/bash
# Shared configuration for all pipeline scripts.
# Override any of these with environment variables before calling run_pipeline.sh.
#
# Defaults resolve relative to this repo (pipeline/..), so they work no matter which
# directory you are in when you invoke a pipeline script. For the demo they point at
# test_case/; for real WGS, export absolute paths instead.

set -euo pipefail

_PIPELINE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_REPO_ROOT="$(cd "$_PIPELINE_DIR/.." && pwd)"

: "${REF_FASTA:=$_REPO_ROOT/test_case/refs/panel_region.fa}"   # any build; demo = GRCh38 slice
: "${CLINVAR_VCF:=$_REPO_ROOT/test_case/refs/clinvar_panel_subset.vcf.gz}"  # must match REF_FASTA build
# For real runs point CLINVAR_VCF at a current ClinVar VCF with the SAME contig naming as REF_FASTA
# and the VCF being annotated (GATK.GRCh38 / sarek use chr-prefixed names; 04_annotate.sh detects
# and normalises a mismatch, but the right file skips that pass). Record the release from the
# file's own `##fileDate` header, never from a README next to it: a README once said 2024-09-02
# for a file that was 2025-07-15.
: "${SNPEFF_DB:=GRCh38.mane.1.2.ensembl}"           # snpEff DB name — must match REF_FASTA build
: "${BCFTOOLS_PLOIDY:=GRCh38}"                       # bcftools call --ploidy set (e.g. GRCh37, GRCh38)

# Panel selection: swap these two paths (and PANEL_NAME below) to point this same pipeline at a
# different clinical/research gene panel -- see panels/README.md. Cardiomyopathy is just the
# example panel shipped with this repo, not a hardcoded assumption of the pipeline itself.
: "${PANEL_BED:=$_REPO_ROOT/panels/cardiomyopathy/cardiomyopathy_genes_grch38.bed}"
: "${PANEL_GENES:=$_REPO_ROOT/panels/cardiomyopathy/cardiomyopathy_genes.txt}"
: "${PANEL_NAME:=Cardiomyopathy}"                   # human-readable label, used in report titles

# Set to 1 for real WGS/panel runs so callers use -T/-L PANEL_BED. Keep 0 for the synthetic
# demo: demo FASTA contig names (demo_chr11_*) do not match the GRCh38 chrN coordinates in PANEL_BED.
: "${RESTRICT_TO_PANEL:=0}"

# Attention genes: a file (one gene per line, first token = current HGNC symbol, further tokens =
# previous symbols/aliases) of genes that must be reviewed in EVERY run of a cohort, on top of the
# panel. Empty by default. When set: stage 07 marks their variants ATTENTION and names any attention
# gene with no variant listed; stage 08 adds them to the phenotype gene set; run_pipeline.sh refuses
# to start when RESTRICT_TO_PANEL=1 and PANEL_BED lacks one of them (it would never be called).
# Cohort rules live in docs/COHORT_NOTES.md. For Uzbek samples (GBA1, GAA, GLA, GALC, IDUA, SMPD1):
#   export ATTENTION_GENES="$_REPO_ROOT/panels/lysosomal_storage/lysosomal_storage_genes.txt"
: "${ATTENTION_GENES:=}"

: "${THREADS:=8}"
: "${OUT_DIR:=$_REPO_ROOT/test_case/results}"
: "${TMP_DIR:=$OUT_DIR/tmp}"

mkdir -p "$OUT_DIR" "$TMP_DIR"

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >&2
}
