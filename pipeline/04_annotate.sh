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

# --- Harmonize ClinVar contig names to the call VCF (NCBI "1" vs UCSC "chr1") ---
# NCBI ClinVar VCFs use 1..22,X,Y,MT; many references/BAMs use chr1..chr22,chrX,chrY,chrM.
# Without renaming, bcftools annotate silently transfers nothing.
harmonize_clinvar_contigs() {
  local target_vcf="$1"
  local clinvar_vcf="$2"
  local cache_dir="$OUT_DIR/.cache"
  mkdir -p "$cache_dir"

  local target_chrom clinvar_chrom
  target_chrom="$(bcftools query -f '%CHROM\n' "$target_vcf" | head -1 || true)"
  clinvar_chrom="$(bcftools query -f '%CHROM\n' "$clinvar_vcf" | head -1 || true)"
  if [[ -z "$target_chrom" || -z "$clinvar_chrom" ]]; then
    echo "$clinvar_vcf"
    return 0
  fi

  local target_chr=0 clinvar_chr=0
  [[ "$target_chrom" == chr* ]] && target_chr=1
  [[ "$clinvar_chrom" == chr* ]] && clinvar_chr=1

  if [[ "$target_chr" -eq "$clinvar_chr" ]]; then
    echo "$clinvar_vcf"
    return 0
  fi

  # Cache key for the harmonized VCF must include the source ClinVar file's identity
  # (path + size + mtime), not just the rename direction -- otherwise switching
  # CLINVAR_VCF while reusing the same OUT_DIR silently serves a stale harmonized file.
  # The rename maps themselves (add_chr.map/strip_chr.map) are direction-only and safe
  # to share across runs.
  local clinvar_abs clinvar_fingerprint key
  clinvar_abs="$(cd "$(dirname "$clinvar_vcf")" && pwd)/$(basename "$clinvar_vcf")"
  clinvar_fingerprint="$(stat -c '%s_%Y' "$clinvar_abs" 2>/dev/null || stat -f '%z_%m' "$clinvar_abs")"
  key="$(printf '%s|%s' "$clinvar_abs" "$clinvar_fingerprint" | cksum | cut -d' ' -f1)"

  local tag map out
  if [[ "$target_chr" -eq 1 ]]; then
    tag="add_chr"
    out="$cache_dir/clinvar_add_chr_${key}.vcf.gz"
    map="$cache_dir/clinvar_add_chr.map"
    if [[ ! -f "$map" ]]; then
      {
        local i
        for i in $(seq 1 22); do printf '%s\tchr%s\n' "$i" "$i"; done
        printf 'X\tchrX\nY\tchrY\nMT\tchrM\nM\tchrM\n'
      } > "$map"
    fi
  else
    tag="strip_chr"
    out="$cache_dir/clinvar_strip_chr_${key}.vcf.gz"
    map="$cache_dir/clinvar_strip_chr.map"
    if [[ ! -f "$map" ]]; then
      {
        local i
        for i in $(seq 1 22); do printf 'chr%s\t%s\n' "$i" "$i"; done
        printf 'chrX\tX\nchrY\tY\nchrM\tMT\nchrMT\tMT\n'
      } > "$map"
    fi
  fi

  if [[ ! -f "$out" || ! -f "${out}.tbi" ]]; then
    log "[$sample_id] harmonizing ClinVar contigs ($tag) to match calls (target=$target_chrom clinvar=$clinvar_chrom)"
    bcftools annotate --rename-chrs "$map" -Oz -o "$out" "$clinvar_vcf"
    tabix -f -p vcf "$out"
  else
    log "[$sample_id] using cached ClinVar contig-harmonized VCF ($tag)"
  fi
  echo "$out"
}

# CLINVAR_VCF is a real env var set in 00_config.sh (sourced dynamically, so shellcheck
# can't see it); not a typo of the local clinvar_vcf.
# shellcheck disable=SC2153
clinvar_for_annot="$(harmonize_clinvar_contigs "$snpeff_input" "$CLINVAR_VCF")"

# Transfer annotation fields only (not CHROM/POS/REF/ALT match keys).
# Include CLNVID / GENEINFO when the annotation VCF defines them (real ClinVar).
annotate_cols="ID,INFO/CLNSIG,INFO/CLNDN,INFO/CLNREVSTAT"
if bcftools view -h "$clinvar_for_annot" | grep -q 'ID=CLNVID,'; then
  annotate_cols+=",INFO/CLNVID"
fi
if bcftools view -h "$clinvar_for_annot" | grep -q 'ID=GENEINFO,'; then
  annotate_cols+=",INFO/GENEINFO"
fi

log "[$sample_id] annotate with ClinVar ($annotate_cols)"
bcftools annotate \
  -a "$clinvar_for_annot" \
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
    --custom "$clinvar_for_annot",ClinVar,vcf,exact,0,CLNSIG,CLNDN,CLNREVSTAT \
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
