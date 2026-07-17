#!/bin/bash
# One-time setup for the demo: bgzip + tabix-index the small ClinVar subset VCF.
# Idempotent — safe to re-run.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

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

echo "Demo reference materials ready: refs/panel_region.fa, $vcf_gz"
