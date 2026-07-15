#!/bin/bash
# Shared configuration for all pipeline scripts.
# Override any of these with environment variables before calling run_pipeline.sh.

set -euo pipefail

: "${REF_FASTA:=$PWD/refs/hg38_panel.fa}"          # reference FASTA — any build (GRCh37, GRCh38, T2T, …); demo default below
: "${CLINVAR_VCF:=$PWD/refs/clinvar_grch38.vcf.gz}" # ClinVar VCF — must match REF_FASTA genome build
: "${SNPEFF_DB:=GRCh38.mane.1.2.ensembl}"           # snpEff DB name — must match REF_FASTA build
: "${BCFTOOLS_PLOIDY:=GRCh38}"                       # bcftools call --ploidy set (e.g. GRCh37, GRCh38)

# Panel selection: swap these two paths (and PANEL_NAME below) to point this same pipeline at a
# different clinical/research gene panel -- see panels/README.md. Cardiomyopathy is just the
# example panel shipped with this repo, not a hardcoded assumption of the pipeline itself.
: "${PANEL_BED:=$PWD/panels/cardiomyopathy/cardiomyopathy_genes_grch38.bed}"
: "${PANEL_GENES:=$PWD/panels/cardiomyopathy/cardiomyopathy_genes.txt}"
: "${PANEL_NAME:=Cardiomyopathy}"                   # human-readable label, used in report titles

: "${THREADS:=8}"
: "${OUT_DIR:=$PWD/results}"
: "${TMP_DIR:=$OUT_DIR/tmp}"

mkdir -p "$OUT_DIR" "$TMP_DIR"

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >&2
}
