#!/usr/bin/env bash
# 03_call_variants.sh ? patched to read CRAM instead of BAM
set -euo pipefail

source "$(dirname "$0")/00_config.sh"

sample_id="$1"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

# Use CRAM instead of BAM
cram="$OUT_DIR/${sample_id}.markdup.cram"
if [[ ! -f "$cram" ]]; then
  # Fall back to BAM if CRAM not found (backward compat)
  bam="$OUT_DIR/${sample_id}.markdup.bam"
  if [[ ! -f "$bam" ]]; then
    echo "ERROR: neither $cram nor $bam found -- run 02_align.sh first." >&2
    exit 1
  fi
  align_input="$bam"
  log "[$sample_id] Using BAM input: $bam"
else
  align_input="$cram"
  log "[$sample_id] Using CRAM input: $cram"
fi

# Restrict to panel BED if enabled
region_args_mpileup=()
if [[ "${RESTRICT_TO_PANEL:-0}" == "1" && -f "${PANEL_BED:-}" ]]; then
  log "[$sample_id] restricting variant calling to panel BED: $PANEL_BED"
  region_args_mpileup=(-T "$PANEL_BED")
fi

# --- Primary caller: bcftools ---
log "[$sample_id] bcftools mpileup + call"
bcftools mpileup -f "$REF_FASTA" --threads "$THREADS" -a AD,DP \
  "${region_args_mpileup[@]}" -Ou "$align_input" \
  | bcftools call -mv --ploidy "${BCFTOOLS_PLOIDY}" -Oz -o "$OUT_DIR/${sample_id}.bcftools.raw.vcf.gz"

tabix -f -p vcf "$OUT_DIR/${sample_id}.bcftools.raw.vcf.gz"

log "[$sample_id] bcftools norm (split multi-allelics, left-align indels)"
bcftools norm -m -any -f "$REF_FASTA" -Oz \
  -o "$OUT_DIR/${sample_id}.bcftools.norm.vcf.gz" \
  "$OUT_DIR/${sample_id}.bcftools.raw.vcf.gz"
tabix -f -p vcf "$OUT_DIR/${sample_id}.bcftools.norm.vcf.gz"

# Hard filter: flag low-quality/low-depth sites, then keep PASS only
log "[$sample_id] bcftools hard filter (QUAL<20 || DP<10 -> LowQual; PASS only)"
bcftools filter -e 'QUAL<20 || INFO/DP<10' -s LowQual \
  "$OUT_DIR/${sample_id}.bcftools.norm.vcf.gz" \
  | bcftools view -f PASS -Oz \
    -o "$OUT_DIR/${sample_id}.bcftools.hard-filtered.vcf.gz"
tabix -f -p vcf "$OUT_DIR/${sample_id}.bcftools.hard-filtered.vcf.gz"

# Clean up intermediate VCFs (keep raw + filtered, remove norm)
rm -f "$OUT_DIR/${sample_id}.bcftools.norm.vcf.gz" "$OUT_DIR/${sample_id}.bcftools.norm.vcf.gz.tbi"

log "[$sample_id] variant calling complete -> ${sample_id}.bcftools.hard-filtered.vcf.gz"

# --- GATK4 HaplotypeCaller (optional cross-check) ---
if command -v gatk &>/dev/null; then
  log "[$sample_id] GATK4 HaplotypeCaller (cross-check)"
  gatk HaplotypeCaller \
    -R "$REF_FASTA" \
    -I "$align_input" \
    ${PANEL_BED:+-L "$PANEL_BED" --interval-padding 50} \
    -O "$OUT_DIR/${sample_id}.gatk.raw.vcf.gz" \
    --native-pair-hmm-threads "$THREADS"
  gatk VariantFiltration \
    -R "$REF_FASTA" \
    -V "$OUT_DIR/${sample_id}.gatk.raw.vcf.gz" \
    -O "$OUT_DIR/${sample_id}.gatk.hard-filtered.vcf.gz" \
    --filter-name "LowQual" --filter-expression "QUAL < 30"
  tabix -f -p vcf "$OUT_DIR/${sample_id}.gatk.hard-filtered.vcf.gz"
  rm -f "$OUT_DIR/${sample_id}.gatk.raw.vcf.gz" "$OUT_DIR/${sample_id}.gatk.raw.vcf.gz.tbi"
  log "[$sample_id] GATK calling complete"
else
  log "[$sample_id] gatk not on PATH ? skipping GATK caller"
fi
