#!/bin/bash
# Replaces DRAGEN's --enable-map-align-output / --enable-sort / --enable-duplicate-marking
# / --enable-bam-indexing with: bwa mem -> fixmate -m -> sort -> markdup -> index.
#
# Usage: 02_align.sh <sample_id> <R1.fastq[.gz]> <R2.fastq[.gz]>
# Accepts plain .fastq or .fastq.gz (and .fq / .fq.gz). Auto-resolves paths without extension.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/00_config.sh"

# Resolve FASTQ path: use as given, or try .fastq.gz / .fastq / .fq.gz / .fq suffixes.
resolve_fastq() {
  local path="$1"
  if [[ -f "$path" ]]; then
    echo "$path"
    return 0
  fi
  for candidate in "${path}.fastq.gz" "${path}.fq.gz" "${path}.fastq" "${path}.fq"; do
    if [[ -f "$candidate" ]]; then
      echo "$candidate"
      return 0
    fi
  done
  echo "$path"
}

fastq_format_label() {
  local path="$1"
  if [[ "$path" == *.gz ]]; then echo "gzip"; else echo "plain"; fi
}

sample_id="$1"
r1_raw="$2"
r2_raw="$3"
r1="$(resolve_fastq "$r1_raw")"
r2="$(resolve_fastq "$r2_raw")"

if [[ ! -f "$r1" ]]; then
  echo "ERROR: R1 FASTQ not found (tried '$r1_raw' and common suffixes): $r1" >&2
  exit 1
fi
if [[ ! -f "$r2" ]]; then
  echo "ERROR: R2 FASTQ not found (tried '$r2_raw' and common suffixes): $r2" >&2
  exit 1
fi

bam_sorted="$TMP_DIR/${sample_id}.sorted.bam"
bam_final="$OUT_DIR/${sample_id}.markdup.bam"

log "[$sample_id] fastp QC/trim (R1: $r1 [$(fastq_format_label "$r1")], R2: $r2 [$(fastq_format_label "$r2")])"
fastp \
  -i "$r1" -I "$r2" \
  -o "$TMP_DIR/${sample_id}.trim_R1.fastq.gz" -O "$TMP_DIR/${sample_id}.trim_R2.fastq.gz" \
  --json "$OUT_DIR/${sample_id}.fastp.json" --html "$OUT_DIR/${sample_id}.fastp.html" \
  --thread "$THREADS"

log "[$sample_id] bwa mem + fixmate + sort"
bwa mem -t "$THREADS" \
  -R "@RG\tID:${sample_id}\tSM:${sample_id}\tPL:ILLUMINA\tLB:${sample_id}" \
  "$REF_FASTA" \
  "$TMP_DIR/${sample_id}.trim_R1.fastq.gz" "$TMP_DIR/${sample_id}.trim_R2.fastq.gz" \
  | samtools fixmate -@ "$THREADS" -m -u - - \
  | samtools sort -@ "$THREADS" -o "$bam_sorted" -

log "[$sample_id] mark duplicates"
samtools markdup -@ "$THREADS" "$bam_sorted" "$bam_final"

log "[$sample_id] index"
samtools index -@ "$THREADS" "$bam_final"

rm -f "$bam_sorted"
log "[$sample_id] alignment complete -> $bam_final"
