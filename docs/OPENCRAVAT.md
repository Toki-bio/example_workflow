# Stage 09: OpenCRAVAT cross-check (optional)

`pipeline/09_opencravat.sh <sample> <triage_out_dir> <out_dir>` annotates the stage-08 candidates
(`candidates.tsv`, about 30 variants) with [OpenCRAVAT](https://docs.opencravat.org/) and writes a TSV beside the
triage output. It never ranks, filters or removes anything: tiers remain stage 08's job.

## What it is for

1. **A second annotator on the short list.** ClinVar, REVEL and SpliceAI are annotated independently of the
   stage-08 annotator, so a disagreement points at a mis-keyed indel, a different transcript, or a different database release.
2. **Modules stage 08 does not have**, for example ClinGen gene curation, LoFtool, PharmGKB, OMIM (licence needed) and, in the
   store, tumour-oriented modules for somatic cases. Only the default set below has been run.

## What it is not for

- Not a replacement for the tier union (T1a/T1b/T2) or the per-variant dossier.
- Not the frequency source: the store offers gnomAD v2.1 and v3 only, older than the gnomAD 4.1 used by stage 08.
- AlphaMissense was not found in the module store (REVEL was). COSMIC and CIVIC did not show up in the store
  listing I searched either; check `oc module ls -a` before relying on them.

## Setup (once, on the data volume)

```
python3 -m venv /staging/tmp/ocrav/venv && /staging/tmp/ocrav/venv/bin/pip install open-cravat
export XDG_CACHE_HOME=/staging/tmp/ocrav/cache TMPDIR=/staging/tmp/ocrav/tmp OC_BIN=/staging/tmp/ocrav/venv/bin/oc
$OC_BIN module install -y hg38 vcf-converter aggregator tsvreporter tagsampler vcfinfo varmeta \
    clinvar revel clingen loftool spliceai
```

Measured 2026-10-14 on DRAGEN (OpenCRAVAT 3.2.3, Python 3.12): module download about 10 GB, about 4 minutes;
annotation of 30 variants 3 s. Modules live inside the venv, so nothing is written to `/home`.
`manifest.json` lists every installed module with its version; put it next to `versions.json` when reporting.

## Toy test: 30 candidates of 26-BB-107930 against stage 08 (Nirvana)

| Check | Result |
|---|---|
| Variants matched by CHROM:POS:REF:ALT | 30 / 30 |
| ClinVar significance where both have a record | same on every variant (ATP6V0A1 and KCNJ10 both "Conflicting") |
| ClinVar submission counts (ATP6V0A1) | OpenCRAVAT Pathogenic (6), Nirvana Pathogenic (7): different ClinVar releases (OpenCRAVAT 2026.10.01, Nirvana data 2026-08-04); not checked further |
| REVEL | 26 variants have a value in both: 24 identical, 2 differ (ATP11A 0.348 vs 0.25, WDR45 0.447 vs 0.301), most likely a different transcript, not checked; SEMA6B has a value only in Nirvana |
| SpliceAI | a value for 1 of 30 variants (ATP11A, DS_AG 0.15) |

This is a 30-variant smoke test, not a validation. It shows the stage runs end to end and agrees with stage 08 where
both have data. Open: run it on the 197k-record blind VCF only if a whole-exome comparison is wanted (not tried).
