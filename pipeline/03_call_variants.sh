#!/bin/bash
# Replaces DRAGEN's --enable-variant-caller with two independent CPU-only callers:
#   1. bcftools mpileup | bcftools call  (primary -- fast, zero extra install)
#   2. GATK4 HaplotypeCaller             (secondary cross-check -- local re-assembly,
#                                          closer to DRAGEN's methodology for indels)
# Both are hard-filtered to a PASS-only VCF, mirroring DRAGEN's *.hard-filtered.vcf.
#
# Set RESTRICT_TO_PANEL=1 to limit calling to PANEL_BED (recommended for real WGS).
# Leave unset/0 for the synthetic demo (demo FASTA contig names do not match the GRCh38 BED).
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

: "${RESTRICT_TO_PANEL:=0}"
region_args_mpileup=()
region_args_gatk=()
if [[ "$RESTRICT_TO_PANEL" == "1" ]]; then
  if [[ ! -f "$PANEL_BED" ]]; then
    echo "ERROR: RESTRICT_TO_PANEL=1 but PANEL_BED not found: $PANEL_BED" >&2
    exit 1
  fi
  log "[$sample_id] restricting variant calling to panel BED: $PANEL_BED"
  region_args_mpileup=(-T "$PANEL_BED")
  region_args_gatk=(-L "$PANEL_BED")
fi

# --- Primary caller: bcftools ---
log "[$sample_id] bcftools mpileup + call"
bcftools mpileup -f "$REF_FASTA" --threads "$THREADS" -a AD,DP \
  "${region_args_mpileup[@]}" -Ou "$bam" \
  | bcftools call -mv --ploidy "${BCFTOOLS_PLOIDY}" -Oz -o "$OUT_DIR/${sample_id}.bcftools.raw.vcf.gz"
tabix -f -p vcf "$OUT_DIR/${sample_id}.bcftools.raw.vcf.gz"

log "[$sample_id] bcftools norm (split multi-allelics, left-align indels)"
bcftools norm -m -any -f "$REF_FASTA" -Oz \
  -o "$OUT_DIR/${sample_id}.bcftools.vcf.gz" \
  "$OUT_DIR/${sample_id}.bcftools.raw.vcf.gz"
tabix -f -p vcf "$OUT_DIR/${sample_id}.bcftools.vcf.gz"

log "[$sample_id] bcftools hard filter -> PASS-only"
bcftools filter \
  -e 'QUAL<20 || INFO/DP<10' \
  -s LowQual \
  "$OUT_DIR/${sample_id}.bcftools.vcf.gz" \
  | bcftools view -f PASS -Oz -o "$OUT_DIR/${sample_id}.bcftools.hard-filtered.vcf.gz"
tabix -f -p vcf "$OUT_DIR/${sample_id}.bcftools.hard-filtered.vcf.gz"

# --- Secondary caller: GATK4 HaplotypeCaller (optional cross-check) ---
if command -v gatk >/dev/null 2>&1; then
  log "[$sample_id] GATK4 HaplotypeCaller"
  gatk HaplotypeCaller \
    -R "$REF_FASTA" \
    -I "$bam" \
    "${region_args_gatk[@]}" \
    -O "$OUT_DIR/${sample_id}.gatk.raw.vcf.gz" \
    --quiet

  log "[$sample_id] GATK LeftAlignAndTrimVariants + SplitMultiAllelics (via bcftools norm)"
  bcftools norm -m -any -f "$REF_FASTA" -Oz \
    -o "$OUT_DIR/${sample_id}.gatk.vcf.gz" \
    "$OUT_DIR/${sample_id}.gatk.raw.vcf.gz"
  tabix -f -p vcf "$OUT_DIR/${sample_id}.gatk.vcf.gz"

  log "[$sample_id] GATK hard filter -> PASS-only (approximating DRAGEN/GATK best-practice defaults)"
  gatk VariantFiltration \
    -R "$REF_FASTA" \
    -V "$OUT_DIR/${sample_id}.gatk.vcf.gz" \
    --filter-expression "QD < 2.0" --filter-name "QD2" \
    --filter-expression "FS > 60.0" --filter-name "FS60" \
    --filter-expression "MQ < 40.0" --filter-name "MQ40" \
    --filter-expression "DP < 10" --filter-name "DP10" \
    -O "$OUT_DIR/${sample_id}.gatk.filtered.vcf.gz" \
    --quiet
  bcftools view -f PASS -Oz -o "$OUT_DIR/${sample_id}.gatk.hard-filtered.vcf.gz" \
    "$OUT_DIR/${sample_id}.gatk.filtered.vcf.gz"
  tabix -f -p vcf "$OUT_DIR/${sample_id}.gatk.hard-filtered.vcf.gz"
else
  log "[$sample_id] gatk not on PATH — skipping GATK caller (bcftools output is used by default)"
fi

if command -v gatk >/dev/null 2>&1; then
  log "[$sample_id] variant calling complete (bcftools primary + GATK secondary)"
else
  log "[$sample_id] variant calling complete (bcftools primary)"
fi
