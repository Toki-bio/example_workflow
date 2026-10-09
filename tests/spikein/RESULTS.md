# Spike-in test of the triage logic (2026-10-09)

200 solved single-variant cases from GA4GH phenopacket-store 0.1.27 (hg38 VCF records, >=3 observed HPO
terms, one case per gene, seed 42; 78 het / 113 hom / 9 hemizygous; 150 SNV / 50 indel) inserted one at a time
into the 26-BB-107930 exome (ATP6V0A1 / ATP6V1A removed from the pool). Annotation Nirvana (gnomAD 4.1, REVEL,
AlphaMissense), ClinVar fileDate 2026-10-04, HPO release 2026-09-01. Gene set per case = genes annotated to
the case's observed HPO terms (ontology-propagated); no PanelApp panel. Scripts: select_cases.py, hpo_local.py,
run_spikein.py (this folder). Per-case results: spike_results.tsv.

| Measure | New logic (tiers T1a/T1b/T2, union) | Old logic (ClinVar aggregate P/LP only) |
|---|---|---|
| Causal variant reported / in candidate list | 198/200 (99%) | 122/200 (61%) |
| Rank 1 | 153 (76%) | n/a |
| Within top 5 / 10 / 30 | 177 (88%) / 183 (92%) / 197 (98%) | n/a |
| Among the 78 the old logic would miss: in list / top 10 / top 30 | 76 / 62 / 75 | 0 |

By ClinVar aggregate of the causal variant: Pathogenic 85 (84 in top 10), P/LP 21 (21), LP 16 (16),
Conflicting 19 (19 in top 10; all T1b), VUS 25 (19), no ClinVar record 28 (19).
By type: SNV top-10 142/150, indel 41/50; het 68/78, hom/hemi 115/122. Median candidate list 191 variants.
Not in the list: IKZF1 variant (ClinVar Benign/Likely benign; gene not in the HPO gene set) and an RNU5B-1
non-coding variant (no protein-altering consequence).

## Read this before quoting the numbers
- Circular gene sets: HPO gene annotations derive from the same diseases as the phenopacket cases, so the
  causal gene is almost always in the gene set (198/200). Real referrals describe phenotypes less completely;
  the in-list rate will be lower. The rank inside the list is the more informative figure.
- Spike-ins overstate performance (published Exomiser benchmarks: ~97% top-hit on spike-ins vs 74% top-1 on a
  real cohort). One background only; clean depth/quality set for every spike.
- "Old logic 61%" is the ClinVar-aggregate ceiling (no PASS filter or gene-list effects), not a measured
  pipeline recall. Many cases are published and therefore in ClinVar (Pathogenic), which flatters the old logic.
- 19 conflicting-aggregate cases were all recovered through T1b: the failure that hid the original variant.
