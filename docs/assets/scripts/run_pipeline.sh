#!/bin/bash
# End-to-end orchestrator: runs stages 01–07 for every sample listed in a manifest,
# then aggregates pathogenic calls across the whole cohort.
#
# Manifest format (tab-separated, no header):
#   sample_id  sample_type(case|control)  R1.fastq[.gz]  R2.fastq[.gz]
#
# Relative FASTQ paths in the manifest are resolved against the manifest's directory
# (so test_case/samples.tsv works whether you call this from the repo root or elsewhere).
#
# Usage: run_pipeline.sh <manifest.tsv>
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/00_config.sh"

manifest_arg="${1:?Usage: run_pipeline.sh <manifest.tsv>}"
if [[ ! -f "$manifest_arg" ]]; then
  echo "ERROR: manifest not found: $manifest_arg" >&2
  exit 1
fi
manifest="$(cd "$(dirname "$manifest_arg")" && pwd)/$(basename "$manifest_arg")"
manifest_dir="$(dirname "$manifest")"

# Resolve a path: absolute stays; relative is taken from the manifest directory.
resolve_from_manifest() {
  local path="$1"
  if [[ "$path" = /* ]]; then
    echo "$path"
  else
    echo "$manifest_dir/$path"
  fi
}

log "Manifest: $manifest"
log "Preparing reference (indexes if missing)"
bash "$SCRIPT_DIR/01_prepare_reference.sh"

while IFS=$'\t' read -r sample_id sample_type r1 r2 || [[ -n "${sample_id:-}" ]]; do
  [[ -z "${sample_id:-}" || "$sample_id" == \#* ]] && continue
  r1_abs="$(resolve_from_manifest "$r1")"
  r2_abs="$(resolve_from_manifest "$r2")"
  log "=== Sample $sample_id ($sample_type) ==="
  bash "$SCRIPT_DIR/02_align.sh" "$sample_id" "$r1_abs" "$r2_abs"
  bash "$SCRIPT_DIR/03_call_variants.sh" "$sample_id"
  bash "$SCRIPT_DIR/04_annotate.sh" "$sample_id" bcftools
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
