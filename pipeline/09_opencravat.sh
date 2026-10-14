#!/usr/bin/env bash
# 09_opencravat.sh -- OPTIONAL second opinion on the stage-08 candidates with OpenCRAVAT.
#
#   09_opencravat.sh <sample_id> <triage_out_dir> <out_dir>
#
# Reads <triage_out_dir>/candidates.tsv (column 1 = CHROM:POS:REF:ALT, GRCh38), annotates only those
# variants with OpenCRAVAT, and writes <out_dir>/{candidates.vcf,oc/<id>.variant.tsv,manifest.json}.
# It does NOT rank or filter: tiers stay the job of stage 08. Use it to cross-check ClinVar, REVEL and
# SpliceAI against the stage-08 annotator, and to add modules stage 08 does not have.
#
# Required environment:
#   OC_BIN       path to the `oc` executable (OpenCRAVAT >= 3.2, installed in its own venv)
# Optional:
#   OC_MODULES   annotators to run (default: "clinvar revel clingen loftool spliceai")
#   OC_THREADS   annotator processes (default 2)
#
# One-off setup (modules are separate downloads, about 10 GB for the default set; keep the venv and
# XDG_CACHE_HOME/TMPDIR on the data volume, never in the login home):
#   $OC_BIN module install -y hg38 vcf-converter aggregator tsvreporter tagsampler vcfinfo varmeta \
#       clinvar revel clingen loftool spliceai
set -euo pipefail

if [[ $# -ne 3 ]]; then
  echo "Usage: $0 <sample_id> <triage_out_dir> <out_dir>" >&2
  exit 1
fi
sample_id="$1"
triage_dir="$2"
out_dir="$3"

source "$(dirname "$0")/00_config.sh"

: "${OC_BIN:?set OC_BIN to the oc executable of an OpenCRAVAT venv}"
modules="${OC_MODULES:-clinvar revel clingen loftool spliceai}"
threads="${OC_THREADS:-2}"
cand="$triage_dir/candidates.tsv"
[[ -s "$cand" ]] || { echo "ERROR: $cand missing or empty - run stage 08 first" >&2; exit 1; }

mkdir -p "$out_dir/oc"
vcf="$out_dir/candidates.vcf"
{
  echo "##fileformat=VCFv4.2"
  printf '#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n'
  tail -n +2 "$cand" | cut -f1 | awk -F: '{c=$1; sub(/^chr/,"",c); printf "chr%s\t%s\t.\t%s\t%s\t.\t.\t.\n", c,$2,$3,$4}'
} > "$vcf"
n=$(($(wc -l < "$vcf") - 2))
log "[$sample_id] OpenCRAVAT on $n stage-08 candidates (modules: $modules)"

read -r -a mods <<< "$modules"
"$OC_BIN" run "$vcf" -l hg38 -t tsv --mp "$threads" -d "$out_dir/oc" -x -a "${mods[@]}"
tsv="$out_dir/oc/$(basename "$vcf").variant.tsv"
[[ -s "$tsv" ]] || { echo "ERROR: OpenCRAVAT produced no $tsv" >&2; exit 1; }

# Provenance from the tool itself (module versions are what make a re-run comparable).
{
  echo '{'
  echo "  \"sample\": \"$sample_id\", \"date\": \"$(date -u +%FT%TZ)\", \"n_variants\": $n,"
  echo "  \"opencravat\": \"$("$OC_BIN" version | tr -d '\n')\","
  echo '  "modules": ['
  "$OC_BIN" module ls | awk 'NR>1 && NF>=4 {gsub(/"/,""); gsub(/ +/," "); printf "%s    \"%s\"", (c++?",\n":""), $0}'
  echo
  echo '  ]'
  echo '}'
} > "$out_dir/manifest.json"
log "[$sample_id] done -> $tsv (columns are group.name, e.g. clinvar.sig, revel.score; manifest.json lists module versions)"
