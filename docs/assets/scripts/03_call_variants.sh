#!/bin/bash
# Replaces DRAGEN's --enable-variant-caller with two independent CPU-only callers:
#   1. bcftools mpileup | bcftools call  (primary -- fast, zero extra install)
#   2. GATK4 HaplotypeCaller             (secondary cross-check -- local re-assembly,
#                                          closer to DRAGEN's methodology for indels)
# Both are hard-filtered to a PASS-only VCF, mirroring DRAGEN's *.hard-filtered.vcf.
#
# Usage: 03_call_variants.sh <sample_id>
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/00_config.sh"

sample_id="$1"
bam="$OUT_DIR/${sample_id}.markdup.bam"

if [[ ! -f "$bam" ]]; then
  echo "ERROR: $bam not found -- run 02_align.sh first." >&2
  exit 1
fi

# --- Primary caller: bcftools ---
log "[$sample_id] bcftools mpileup + call"
bcftools mpileup -f "$REF_FASTA" --threads "$THREADS" -a AD,DP -Ou "$bam" \
  | bcftools call -mv --ploidy GRCh38 -Oz -o "$OUT_DIR/${sample_id}.bcftools.vcf.gz"
tabix -f -p vcf "$OUT_DIR/${sample_id}.bcftools.vcf.gz"

log "[$sample_id] bcftools hard filter -> PASS-only"
bcftools filter \
  -e 'QUAL<20 || INFO/DP<10' \
  -s LowQual \
  -Oz -o "$OUT_DIR/${sample_id}.bcftools.hard-filtered.vcf.gz" \
  "$OUT_DIR/${sample_id}.bcftools.vcf.gz"
tabix -f -p vcf "$OUT_DIR/${sample_id}.bcftools.hard-filtered.vcf.gz"

# --- Secondary caller: GATK4 HaplotypeCaller ---
log "[$sample_id] GATK4 HaplotypeCaller"
gatk HaplotypeCaller \
  -R "$REF_FASTA" \
  -I "$bam" \
  -O "$OUT_DIR/${sample_id}.gatk.vcf.gz" \
  --quiet

log "[$sample_id] GATK hard filter -> PASS-only (approximating DRAGEN/GATK best-practice defaults)"
gatk VariantFiltration \
  -R "$REF_FASTA" \
  -V "$OUT_DIR/${sample_id}.gatk.vcf.gz" \
  --filter-expression "QD < 2.0" --filter-name "QD2" \
  --filter-expression "FS > 60.0" --filter-name "FS60" \
  --filter-expression "MQ < 40.0" --filter-name "MQ40" \
  --filter-expression "DP < 10" --filter-name "DP10" \
  -O "$OUT_DIR/${sample_id}.gatk.hard-filtered.vcf.gz" \
  --quiet

log "[$sample_id] variant calling complete (bcftools primary + GATK secondary)"
