#!/bin/bash
# Build all indexes needed by the downstream stages: BWA index, .fai, GATK .dict,
# and the snpEff database. Run this once per reference.
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
  echo "For the synthetic test case, run test_case/simulate_reads.sh first." >&2
  exit 1
fi

log "Indexing reference with bwa index (this is slow for a full genome, seconds for the demo panel region)"
bwa index "$REF_FASTA"

log "Building samtools .fai"
samtools faidx "$REF_FASTA"

log "Building GATK sequence dictionary"
gatk CreateSequenceDictionary -R "$REF_FASTA" --QUIET true

if [[ -f "$CLINVAR_VCF" ]]; then
  log "Indexing ClinVar VCF"
  tabix -f -p vcf "$CLINVAR_VCF"
else
  log "WARNING: ClinVar VCF not found at $CLINVAR_VCF -- annotation step will fail until you download it."
  log "  Source (GRCh38 example): https://ftp.ncbi.nlm.nih.gov/pub/clinvar/vcf_GRCh38/clinvar.vcf.gz"
  log "  GRCh37: https://ftp.ncbi.nlm.nih.gov/pub/clinvar/vcf_GRCh37/clinvar.vcf.gz"
fi

log "Reference preparation complete."
