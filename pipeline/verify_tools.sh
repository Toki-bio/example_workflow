#!/bin/bash
# Check that required (and optional) tools are on PATH.
# Exit 0 if all required tools are present; exit 1 otherwise.
#
# Usage:  pipeline/verify_tools.sh
#         (run from anywhere; no working-directory requirement)
set -euo pipefail

REQUIRED=(bwa samtools bcftools gatk fastp tabix bgzip python3)
OPTIONAL=(snpEff vep)

missing=0

echo "=== Required tools ==="
for t in "${REQUIRED[@]}"; do
  if command -v "$t" >/dev/null 2>&1; then
    printf "OK       %-10s -> %s\n" "$t" "$(command -v "$t")"
  else
    printf "MISSING  %-10s\n" "$t"
    missing=1
  fi
done

echo
echo "=== Optional tools (pipeline skips these if absent) ==="
for t in "${OPTIONAL[@]}"; do
  if command -v "$t" >/dev/null 2>&1; then
    printf "OK       %-10s -> %s\n" "$t" "$(command -v "$t")"
  else
    printf "skipped  %-10s (not on PATH)\n" "$t"
  fi
done

echo
python3 --version

if [[ "$missing" -ne 0 ]]; then
  echo
  echo "ERROR: one or more required tools are missing." >&2
  echo "Full env:  conda env create -f envs/environment.yml && conda activate variant-pipeline" >&2
  echo "Or add to current env: conda install -c bioconda -c conda-forge gatk4 fastp" >&2
  exit 1
fi

echo
echo "All required tools found."
