#!/bin/bash
# Replaces DRAGEN's --enable-variant-annotation / Illumina Nirvana with two open,
# license-free annotation paths run in parallel for cross-validation:
#   1. snpEff (transcript/consequence) + bcftools annotate with the public ClinVar VCF
#   2. Ensembl VEP (--custom ClinVar) as a second, independently-implemented annotator
#
# Usage: 04_annotate.sh <sample_id> <caller: bcftools|gatk>
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/00_config.sh"

sample_id="$1"
caller="${2:-bcftools}"
in_vcf="$OUT_DIR/${sample_id}.${caller}.hard-filtered.vcf.gz"

if [[ ! -f "$in_vcf" ]]; then
  echo "ERROR: $in_vcf not found -- run 03_call_variants.sh first." >&2
  exit 1
fi

# --- Path 1: snpEff (if a matching database is installed) + ClinVar (always) ---
snpeff_input="$in_vcf"
if command -v snpEff >/dev/null 2>&1 && snpEff databases 2>/dev/null | grep -qi "^${SNPEFF_DB}\b"; then
  log "[$sample_id] snpEff annotation ($caller calls, db=$SNPEFF_DB)"
  if snpEff -Xmx8g "$SNPEFF_DB" "$in_vcf" > "$TMP_DIR/${sample_id}.${caller}.snpeff.vcf" \
       2> "$OUT_DIR/${sample_id}.${caller}.snpeff.log"; then
    bgzip -f "$TMP_DIR/${sample_id}.${caller}.snpeff.vcf"
    tabix -f -p vcf "$TMP_DIR/${sample_id}.${caller}.snpeff.vcf.gz"
    snpeff_input="$TMP_DIR/${sample_id}.${caller}.snpeff.vcf.gz"
  else
    log "[$sample_id] WARNING: snpEff run failed -- continuing with ClinVar-only annotation."
  fi
else
  log "[$sample_id] snpEff database '$SNPEFF_DB' not installed -- skipping gene/consequence"
  log "  annotation (harmless for the small demo genome; install the DB for real WGS runs:"
  log "  snpEff download $SNPEFF_DB). Continuing with ClinVar-only annotation."
fi

log "[$sample_id] annotate with public ClinVar VCF (ID + CLNSIG/CLNDN/CLNREVSTAT[+CLNVID])"
# Transfer annotation fields only (not CHROM/POS/REF/ALT match keys). Include CLNVID when
# the annotation VCF defines it (real ClinVar); the demo subset may omit it.
annotate_cols="ID,INFO/CLNSIG,INFO/CLNDN,INFO/CLNREVSTAT"
if bcftools view -h "$CLINVAR_VCF" | grep -q 'ID=CLNVID,'; then
  annotate_cols+=",INFO/CLNVID"
fi
bcftools annotate \
  -a "$CLINVAR_VCF" \
  -c "$annotate_cols" \
  -Oz -o "$OUT_DIR/${sample_id}.${caller}.annotated.vcf.gz" \
  "$snpeff_input"
tabix -f -p vcf "$OUT_DIR/${sample_id}.${caller}.annotated.vcf.gz"

# --- Path 2: Ensembl VEP (optional -- skipped automatically if vep is not on PATH) ---
if command -v vep >/dev/null 2>&1; then
  log "[$sample_id] Ensembl VEP annotation (cross-check)"
  vep \
    --input_file "$in_vcf" --format vcf \
    --fasta "$REF_FASTA" \
    --custom "$CLINVAR_VCF",ClinVar,vcf,exact,0,CLNSIG,CLNDN,CLNREVSTAT \
    --vcf --output_file "$OUT_DIR/${sample_id}.${caller}.vep_clinvar.vcf" \
    --force_overwrite --offline --cache --everything \
    --stats_file "$OUT_DIR/${sample_id}.${caller}.vep_summary.html" \
    2> "$OUT_DIR/${sample_id}.${caller}.vep.log" || \
    log "[$sample_id] WARNING: VEP run failed -- see ${sample_id}.${caller}.vep.log (falling back to snpEff+ClinVar only)"
  if [[ -f "$OUT_DIR/${sample_id}.${caller}.vep_clinvar.vcf" ]]; then
    bgzip -f "$OUT_DIR/${sample_id}.${caller}.vep_clinvar.vcf"
    tabix -f -p vcf "$OUT_DIR/${sample_id}.${caller}.vep_clinvar.vcf.gz"
  fi
else
  log "[$sample_id] vep not found on PATH -- skipping VEP cross-check, snpEff+ClinVar remains the primary annotation."
fi

log "[$sample_id] annotation complete"
