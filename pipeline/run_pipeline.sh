#!/bin/bash
# End-to-end orchestrator: runs stages 02-07 for every sample listed in a manifest,
# then aggregates pathogenic calls across the whole cohort.
#
# Manifest format (tab-separated, no header):
#   sample_id  sample_type(case|control)  R1.fastq.gz  R2.fastq.gz
#
# Usage: run_pipeline.sh <manifest.tsv>
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/00_config.sh"

manifest="${1:?Usage: run_pipeline.sh <manifest.tsv>}"

log "Preparing reference (skips work that is already done)"
"$SCRIPT_DIR/01_prepare_reference.sh"

while IFS=$'\t' read -r sample_id sample_type r1 r2; do
  [[ -z "$sample_id" || "$sample_id" == \#* ]] && continue
  log "=== Sample $sample_id ($sample_type) ==="
  "$SCRIPT_DIR/02_align.sh" "$sample_id" "$r1" "$r2"
  "$SCRIPT_DIR/03_call_variants.sh" "$sample_id"
  "$SCRIPT_DIR/04_annotate.sh" "$sample_id" bcftools
  python3 "$SCRIPT_DIR/05_filter_pathogenic.py" \
    "$OUT_DIR/${sample_id}.bcftools.annotated.vcf.gz" \
    "$sample_id" "$sample_type" \
    "$OUT_DIR/${sample_id}.${sample_type}.pathogenic.jsonl"
  python3 "$SCRIPT_DIR/07_generate_report.py" \
    "$OUT_DIR/${sample_id}.bcftools.annotated.vcf.gz" \
    "$sample_id" "$PANEL_GENES" \
    "$OUT_DIR/${sample_id}.report.html" \
    "$PANEL_NAME"
done < "$manifest"

log "Aggregating pathogenic calls across the cohort"
python3 "$SCRIPT_DIR/06_aggregate_case_control.py" \
  "$OUT_DIR/*.pathogenic.jsonl" \
  "$OUT_DIR/aggregated_pathogenic_variants.json"

log "Pipeline complete. Results in $OUT_DIR"
