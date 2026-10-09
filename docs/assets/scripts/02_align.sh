#!/usr/bin/env bash
# 02_align.sh — CRAM output, NO FASTQ deletion
set -euo pipefail

source "$(dirname "$0")/00_config.sh"

sample_id="$1"
r1="$2"
r2="$3"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

# Resolve a FASTQ given without (or with a different) extension; fail loudly if it cannot be found
# (the earlier eval-based version never actually reassigned r1/r2 and let a missing file reach fastp).
resolve_fastq() {
  local f="$1" ext
  if [[ -f "$f" ]]; then
    echo "$f"
    return 0
  fi
  for ext in .gz .fq.gz .fastq.gz .fq .fastq; do
    if [[ -f "${f}${ext}" ]]; then
      echo "${f}${ext}"
      return 0
    fi
  done
  echo "ERROR: FASTQ not found: $f" >&2
  return 1
}
r1="$(resolve_fastq "$r1")"
r2="$(resolve_fastq "$r2")"

bam_sorted="$TMP_DIR/${sample_id}.sorted.bam"
cram_final="$OUT_DIR/${sample_id}.markdup.cram"

log "[$sample_id] fastp (adapter + quality trim)"
fastp \
  -i "$r1" -I "$r2" \
  -o "$TMP_DIR/${sample_id}.trim_R1.fastq.gz" -O "$TMP_DIR/${sample_id}.trim_R2.fastq.gz" \
  --thread "$THREADS" \
  --detect_adapter_for_pe \
  --cut_front --cut_tail --cut_window_size 4 --cut_mean_quality 20 \
  --length_required 50 \
  --json "$OUT_DIR/${sample_id}.fastp.json" --html "$OUT_DIR/${sample_id}.fastp.html" \
  2>&1 | tee "$OUT_DIR/${sample_id}.fastp.stderr.log"

log "[$sample_id] bwa mem + fixmate + sort"
bwa mem -t "$THREADS" -Y \
  -R "@RG\tID:${sample_id}\tSM:${sample_id}\tPL:ILLUMINA\tLB:${sample_id}" \
  "$REF_FASTA" \
  "$TMP_DIR/${sample_id}.trim_R1.fastq.gz" \
  "$TMP_DIR/${sample_id}.trim_R2.fastq.gz" \
  | samtools fixmate -@ "$THREADS" -m -u - - \
  | samtools sort -@ "$THREADS" -o "$bam_sorted" -

log "[$sample_id] markdup + CRAM conversion"
samtools markdup -@ "$THREADS" "$bam_sorted" - \
  | samtools view -C -@ "$THREADS" -T "$REF_FASTA" -o "$cram_final" -

log "[$sample_id] indexing CRAM"
samtools index -@ "$THREADS" "$cram_final"

log "[$sample_id] flagstat"
samtools flagstat "$cram_final" | tee "$OUT_DIR/${sample_id}.flagstat.txt"

# Cleanup temp files only (NOT merged FASTQs)
rm -f "$bam_sorted" \
  "$TMP_DIR/${sample_id}.trim_R1.fastq.gz" \
  "$TMP_DIR/${sample_id}.trim_R2.fastq.gz"
rm -f "$TMP_DIR/${sample_id}.sorted.bam.tmp."*.bam 2>/dev/null || true

log "[$sample_id] alignment complete -> $cram_final"