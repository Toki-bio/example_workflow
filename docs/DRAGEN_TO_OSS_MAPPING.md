# DRAGEN feature → open-source replacement mapping

Stage-by-stage mapping for the specific cardiomyopathy-panel case study described in
[`ORIGINAL_DRAGEN_PIPELINE.md`](ORIGINAL_DRAGEN_PIPELINE.md). For where DRAGEN and its
replacements sit in the wider genomic data/tooling landscape (sequencing vs. array data, other
goal tiers), see [`DATA_TYPES_AND_WORKFLOWS.md`](DATA_TYPES_AND_WORKFLOWS.md).

| Stage | Original (DRAGEN, FPGA + licensed) | Replacement (CPU-only, open source) | Notes |
|---|---|---|---|
| Read QC | DRAGEN internal trimmer metrics | `fastp` (QC + adapter trimming) | Used for QC-only checks in the original setup. (`fastqc` is not part of this pipeline -- `fastp` alone covers QC + trimming here.) |
| Alignment | DRAGEN Map/Align (FPGA-accelerated BWA-like aligner against a DRAGEN hash table) | `bwa mem` against user-supplied `REF_FASTA` (BWA-MEM2 optional for speed) | Reference build is configurable (GRCh37, GRCh38, T2T, etc.); original case study used GRCh38. |
| Sort + index | `--enable-sort --enable-bam-indexing` (DRAGEN) | `samtools sort` + `samtools index` | Drop-in equivalent. |
| Duplicate marking | `--enable-duplicate-marking` (DRAGEN) | `samtools markdup` (or GATK `MarkDuplicates`) | Drop-in equivalent. |
| Variant calling | DRAGEN's proprietary ML-assisted, FPGA-accelerated caller | **Primary:** `bcftools mpileup \| bcftools call` (fast, already installed, pileup-based). **Secondary cross-check:** GATK4 `HaplotypeCaller` (local re-assembly, closer methodology to DRAGEN for indels/complex variants), when `gatk` is on PATH. | Both run per sample when GATK is available; each is independently annotated and filtered, producing a separate per-sample GATK report (`<sample>.gatk.report.html`) and pathogenic-call file (`<sample>.<type>.gatk_crosscheck.jsonl`) alongside the primary bcftools output, for manual comparison. |
| Hard filtering | DRAGEN default hard filters → `*.hard-filtered.vcf` | `bcftools filter` / GATK `VariantFiltration` with equivalent QUAL/QD/FS/MQ/depth thresholds | Filter set documented in `pipeline/03_call_variants.sh`. |
| Graph/pangenome reference | DRAGEN pangenome mode (`--ref-dir .../pangenome/`) | **Not reproduced.** Linear `REF_FASTA` only (any assembly build you configure). | No mature, drop-in open equivalent exists for DRAGEN's proprietary pangenome graph mode; noted as a documented capability gap rather than approximated. |
| Annotation | Illumina Nirvana (licensed data bundle: ClinVar, gnomAD, 1000G, TopMed, MITOMAP, COSMIC, REVEL, CADD, PhyloP, GERP, transcripts...) | **snpEff** (transcript/consequence annotation, optional -- ClinVar annotation still works without it) + `bcftools annotate` with the public **ClinVar VCF** (clinical significance) for the primary path; **Ensembl VEP** (with the ClinVar + gnomAD custom annotations) as a second, cross-validating annotation engine. | All annotation sources used (ClinVar, gnomAD) are free/public; no licensed content is bundled in this repo. Neither snpEff nor VEP is in `envs/environment.yml` -- install separately if you want transcript/consequence annotation (see README). |
| Pathogenic extraction | `jq` over Nirvana JSON, ClinVar significance regex match | Equivalent `jq`/Python logic over the VCF `INFO` fields populated by snpEff/VEP + `bcftools annotate` | Same "select ClinVar Pathogenic/Likely pathogenic" rule, same case/control tagging and aggregation logic. |
| Case/control aggregation | `aggregated_pathogenic_variants.json` (group by variant, count case vs control) | Same aggregation logic, same output shape | Ported almost unchanged — this stage was tool-agnostic to begin with. |
| Reporting | `single_sample_report.py` HTML report keyed to the 26-gene panel | Renamed `pipeline/07_generate_report.py` in this repo (same logic, adapted field-extraction to read from the annotated VCF instead of Nirvana JSON) | Same gene panel (`panels/cardiomyopathy/cardiomyopathy_genes.txt`), same clinical filter thresholds. A companion multi-sample case/control view (`cardiopanel_visualizer.py` in the original DRAGEN pipeline) has no replacement in this repo yet -- `pipeline/06_aggregate_case_control.py` produces the underlying JSON, but not a rendered visualization. |

## Expected differences vs. the original DRAGEN output

- Small differences in exact read alignment and variant calls are expected between DRAGEN's
  proprietary aligner/caller and BWA+GATK/bcftools — this is normal and well documented in the
  literature; the replacement pipeline was validated by comparing pathogenic-variant calls on
  real samples still hosted on the source server (not shipped here, and no validation report is
  included in this repo -- treat this as an unvalidated reference implementation until you run
  your own comparison against a trusted caller).
- Population-frequency and in-silico-score fields will differ slightly from Nirvana's bundled
  versions of gnomAD/dbNSFP/etc., since this pipeline uses independently-downloaded, differently
  versioned public resources.
- The DRAGEN pangenome-mode run has no counterpart here; only the linear-`REF_FASTA` path is
  reproduced (build-agnostic — demo and original case study used GRCh38).
