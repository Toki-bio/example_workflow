#!/bin/bash
# Runs the full replacement pipeline end-to-end on the 2-sample synthetic demo.
# No FPGA, no license, no real patient data -- runs on a laptop in well under a minute
# once the (tiny) conda environment is set up.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$SCRIPT_DIR"

# Prepare demo reference files (inline — no separate script execution required)
vcf_plain="refs/clinvar_panel_subset.vcf"
vcf_gz="refs/clinvar_panel_subset.vcf.gz"
if [[ ! -f "$vcf_gz" ]]; then
  if [[ ! -f "$vcf_plain" ]]; then
    echo "ERROR: neither $vcf_plain nor $vcf_gz found" >&2
    exit 1
  fi
  bgzip -c "$vcf_plain" > "$vcf_gz"
fi
tabix -f -p vcf "$vcf_gz"
if [[ ! -f refs/panel_region.fa ]]; then
  echo "ERROR: refs/panel_region.fa not found" >&2
  exit 1
fi
if [[ ! -f refs/panel_region.fa.fai ]]; then
  samtools faidx refs/panel_region.fa
fi

export REF_FASTA="$SCRIPT_DIR/refs/panel_region.fa"
export CLINVAR_VCF="$SCRIPT_DIR/refs/clinvar_panel_subset.vcf.gz"
export PANEL_GENES="$REPO_ROOT/panels/cardiomyopathy/cardiomyopathy_genes.txt"
export PANEL_BED="$REPO_ROOT/panels/cardiomyopathy/cardiomyopathy_genes_grch38.bed"
export PANEL_NAME="Cardiomyopathy (demo)"
export OUT_DIR="$SCRIPT_DIR/results"
export THREADS="${THREADS:-2}"

bash "$REPO_ROOT/pipeline/run_pipeline.sh" "$SCRIPT_DIR/samples.tsv"

echo
echo "=== Demo complete ==="
echo "Reports:      $OUT_DIR/case1.report.html , $OUT_DIR/control1.report.html"
echo "Case/control: $OUT_DIR/aggregated_pathogenic_variants.json"
echo
echo "Expected: case1 should show one Pathogenic hit in MYBPC3 (chr11:47342698 G>A,"
echo "p.Arg502Trp / rs375882485) that control1 does not have."
