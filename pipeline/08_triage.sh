#!/usr/bin/env bash
# 08_triage.sh -- phenotype-driven candidate search that does NOT depend on ClinVar's aggregate label.
#
#   08_triage.sh <sample_id> <vcf[.gz]> <out_dir>
#
# Required environment (there is deliberately no default gene list):
#   TRIAGE_HPO        space-separated HPO terms of the referral, e.g. "HP:0001250 HP:0007359"
#   TRIAGE_KEYWORDS   space-separated PanelApp panel-name keywords, e.g. "epilep seizure"
# Optional:
#   TRIAGE_EXCLUDE    panel-name substrings to drop (wrongly matched panels)
#   TRIAGE_NIRVANA    Nirvana .json.gz of the same VCF (offline annotation) instead of Ensembl VEP REST
#   TRIAGE_CLINVAR    local/remote ClinVar VCF (default: current NCBI release)
#   TRIAGE_DOSSIERS   number of per-variant evidence dossiers to write (default 15; 0 = none)
#
# Tiers (independent, combined by union -- a ClinVar label may ADD a variant, never remove one):
#   T1a ClinVar P/LP | T1b ClinVar "Conflicting" with a P/LP submission |
#   T2 rare protein-altering in a phenotype gene, ClinVar ignored | T2r the same at 0.1-1 % frequency
# Output: <out_dir>/{genes.tsv,tiers.tsv,candidates.tsv,outside_phenotype.tsv,dossier/,manifest.json}.
# manifest.json records panel versions, ClinVar fileDate (from the file header), thresholds and dates.
set -euo pipefail

if [[ $# -ne 3 ]]; then
  echo "Usage: $0 <sample_id> <vcf[.gz]> <out_dir>" >&2
  exit 1
fi
sample_id="$1"
vcf="$2"
out_dir="$3"

source "$(dirname "$0")/00_config.sh"

: "${TRIAGE_HPO:?set TRIAGE_HPO to the HPO terms of the referral - there is no default gene list on purpose}"
: "${TRIAGE_KEYWORDS:?set TRIAGE_KEYWORDS to PanelApp panel-name keywords}"
edt="$(dirname "$0")/triage/edt.py"

read -r -a hpo <<< "$TRIAGE_HPO"
read -r -a keywords <<< "$TRIAGE_KEYWORDS"
exclude_args=()
if [[ -n "${TRIAGE_EXCLUDE:-}" ]]; then
  read -r -a exclude <<< "$TRIAGE_EXCLUDE"
  exclude_args=(--exclude "${exclude[@]}")
fi
clinvar_args=()
if [[ -n "${TRIAGE_CLINVAR:-}" ]]; then
  clinvar_args=(--clinvar-vcf "$TRIAGE_CLINVAR")
fi
annotate_args=(--workers 4)
if [[ -n "${TRIAGE_NIRVANA:-}" ]]; then
  annotate_args+=(--nirvana "$TRIAGE_NIRVANA")
fi

mkdir -p "$out_dir"
log "[$sample_id] positive controls (must pass before any result is trusted)"
python3 -X utf8 "$edt" control

log "[$sample_id] gene set from PanelApp UK/AU + HPO (${TRIAGE_KEYWORDS}; ${TRIAGE_HPO})"
python3 -X utf8 "$edt" genes --out "$out_dir" --keywords "${keywords[@]}" --hpo "${hpo[@]}" "${exclude_args[@]}"
python3 -X utf8 "$edt" regions --out "$out_dir"

log "[$sample_id] scan calls (nothing dropped; low quality is flagged)"
python3 -X utf8 "$edt" scan --out "$out_dir" --vcf "$vcf"
python3 -X utf8 "$edt" clinvar --out "$out_dir" "${clinvar_args[@]}"

log "[$sample_id] annotate"
python3 -X utf8 "$edt" annotate --out "$out_dir" "${annotate_args[@]}"

log "[$sample_id] rank (union of tiers)"
python3 -X utf8 "$edt" rank --out "$out_dir" --top 30

n_dossiers="${TRIAGE_DOSSIERS:-15}"
if [[ "$n_dossiers" -gt 0 ]]; then
  log "[$sample_id] evidence dossiers for the top $n_dossiers (every ClinVar submission listed)"
  python3 -X utf8 "$edt" dossier --out "$out_dir" --top "$n_dossiers"
fi
log "[$sample_id] done -> $out_dir (read candidates.tsv, dossier/, outside_phenotype.tsv, manifest.json)"
