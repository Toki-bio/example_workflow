# Stage 08: phenotype-driven triage (does not trust ClinVar's aggregate label)

Stages 05-07 report what ClinVar already knows about a panel. Stage 08 answers the question a
diagnostic exome actually asks: *which variant in this patient explains this phenotype?* It exists
because a pipeline that keeps only ClinVar Pathogenic / Likely pathogenic can call a real disease
variant correctly and still report "nothing found": ClinVar sets the aggregate to "Conflicting
classifications of pathogenicity" when one criteria-provided submission disagrees with the rest, whatever its
age (for example 11 of 12 submissions P/LP plus one old VUS). Such variants never pass a P/LP filter.

## Run

```bash
export TRIAGE_HPO="HP:0001250 HP:0007359"        # HPO terms translated from the referral
export TRIAGE_KEYWORDS="epilep seizure"          # PanelApp panel-name keywords
# optional: TRIAGE_EXCLUDE="irrelevant panel part"  TRIAGE_NIRVANA=x.json.gz  TRIAGE_CLINVAR=clinvar.vcf.gz
bash pipeline/08_triage.sh SAMPLE annotated_or_raw.vcf.gz results/SAMPLE_triage
```

There is deliberately no default gene list. The gene set is built from PanelApp UK + Australia
(green panels matching the keywords) and the genes annotated to the HPO terms; panel IDs and versions go
into `manifest.json`. A short hand-picked list is the other way to lose a variant (a 48-gene epilepsy list
omitted a gene that PanelApp's epilepsy panels contain).

## Tiers (independent, combined by union)

| Tier | Rule |
|---|---|
| T1a | ClinVar aggregate Pathogenic / Likely pathogenic |
| T1b | ClinVar aggregate Conflicting, but at least one submission is P/LP (`CLNSIGCONF`) |
| T2 | gnomAD frequency < 0.1 %, protein-altering or splice, in a phenotype gene, **ClinVar ignored** |
| T2r | the same at 0.1-1 % (recessive range) |

A ClinVar label may add a variant to the list; it never removes one. Variants that could not be
annotated stay in T2, flagged. Scores only reorder: single heterozygotes in recessive-only genes, low allele
balance, low depth, and variants common in any gnomAD source rank lower and carry a note.
ClinVar-tier variants outside the phenotype genes go to `outside_phenotype.tsv`, not into the ranking.

## Outputs

`candidates.tsv` (top 30), `tiers.tsv` (full union), `outside_phenotype.tsv`, `dossier/*.md` (every
ClinVar submission with date, submitter and classification, per-condition records, gnomAD v4, panel and
Gene2Phenotype curation, literature under every protein numbering), and `manifest.json` (panel versions,
ClinVar `##fileDate` read from the file header, thresholds, annotation source, counts of
variants that failed annotation).

## What it cannot see

CNVs and exon deletions, structural variants, repeat expansions, mtDNA, deep intronic and regulatory
variants, off-target regions, low-coverage exons and mosaicism below the calling threshold. A singleton
gives no de novo status. State this, with the gene set and thresholds, in every report; never write "no
pathogenic variant found" without it. Final classification is a clinical geneticist's task: ACMG/AMP
criteria scored from the primary evidence, parental testing, phenotype fit.

## Offline annotation

Run Illumina Connected Annotations (Nirvana) once on the whole VCF and pass the JSON with
`TRIAGE_NIRVANA`: about 4 minutes per exome, gnomAD v4.1, REVEL, AlphaMissense, MANE. Without it the
script uses the Ensembl VEP REST service (parallel, resumable, slower).

`pipeline/triage/edt.py` is the same code as the `exome-diagnostic-triage` Claude skill; tests are in
`tests/test_triage_edt.py` (offline).
