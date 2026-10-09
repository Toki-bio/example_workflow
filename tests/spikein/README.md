# Spike-in test of the triage logic

Measures how often the triage (`pipeline/triage/edt.py`) puts a *known* causal variant in its candidate list,
and where it ranks, compared with reporting only ClinVar Pathogenic / Likely pathogenic. Needs network and
a Nirvana install; not part of CI. Published result: [`RESULTS.md`](RESULTS.md).

Steps (run in this folder):

1. `curl -sLO https://github.com/monarch-initiative/phenopacket-store/releases/latest/download/all_phenopackets.zip`
2. `python select_cases.py 200` -> `spike_cases.tsv` (solved single-variant hg38 cases, one per gene, seed 42).
3. Build `spike.vcf` from the keys in `spike_cases.tsv` (one record per key, GT 0/1), annotate it with Nirvana
   (`spike_nv.json.gz`) and run `edt.py clinvar` on a folder holding the keys as `allcalls.keys`
   (-> `spikeclin/clinvar_hits.tsv`).
4. `curl -sLO https://purl.obolibrary.org/obo/hp.obo; curl -sLO https://purl.obolibrary.org/obo/hp/hpoa/genes_to_phenotype.txt`
   then `python hpo_local.py` -> `hpo_genes.json` (ontology-propagated, no web calls).
5. `python run_spikein.py --background-vcf X.vcf.gz --background-nirvana X_nv.json.gz --background-clinvar-hits X/clinvar_hits.tsv --exclude-genes GENE1 GENE2`
   -> `spike_results.tsv`, `spike_summary.txt`.

Caveats are in RESULTS.md: the HPO gene sets come from the same disease records as the cases (the causal gene is
nearly always in the set), spike-ins overstate real performance, and one background was used.
