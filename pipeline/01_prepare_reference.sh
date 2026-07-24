#!/bin/bash
# Build all indexes needed by the downstream stages: BWA index, .fai, GATK .dict,
# and tabix on ClinVar. Safe to re-run — skips work that is already done.
#
# Usage: 01_prepare_reference.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/00_config.sh"

log "Reference: $REF_FASTA"

if [[ ! -f "$REF_FASTA" ]]; then
  echo "ERROR: reference FASTA not found at $REF_FASTA" >&2
  echo "Set REF_FASTA to your reference FASTA (GRCh37/hg19, GRCh38/hg38, T2T-CHM13, etc.)." >&2
  echo "ClinVar VCF, panel BED, snpEff DB, and bcftools --ploidy must use the same build." >&2
  echo "For the synthetic demo: cd test_case && bash run_demo.sh" >&2
  exit 1
fi

# BWA index produces several files; .bwt is the usual marker.
if [[ -f "${REF_FASTA}.bwt" ]]; then
  log "BWA index already present — skipping bwa index"
else
  log "Indexing reference with bwa index (slow for a full genome; seconds for the demo)"
  bwa index "$REF_FASTA"
fi

if [[ -f "${REF_FASTA}.fai" ]]; then
  log "samtools .fai already present — skipping"
else
  log "Building samtools .fai"
  samtools faidx "$REF_FASTA"
fi

dict_path="${REF_FASTA%.*}.dict"
if [[ -f "$dict_path" ]]; then
  log "Sequence dictionary already present — skipping"
elif command -v gatk >/dev/null 2>&1; then
  log "Building GATK sequence dictionary"
  gatk CreateSequenceDictionary -R "$REF_FASTA" --QUIET true
else
  log "gatk not on PATH — skipping .dict (only needed if you use the GATK caller in stage 03)"
fi

if [[ -f "$CLINVAR_VCF" ]]; then
  if [[ -f "${CLINVAR_VCF}.tbi" ]]; then
    log "ClinVar tabix index already present — skipping"
  else
    log "Indexing ClinVar VCF"
    tabix -f -p vcf "$CLINVAR_VCF"
  fi
else
  log "WARNING: ClinVar VCF not found at $CLINVAR_VCF — annotation step will fail until you download it."
  log "  Source (GRCh38 example): https://ftp.ncbi.nlm.nih.gov/pub/clinvar/vcf_GRCh38/clinvar.vcf.gz"
  log "  GRCh37: https://ftp.ncbi.nlm.nih.gov/pub/clinvar/vcf_GRCh37/clinvar.vcf.gz"
fi

log "Reference preparation complete."
