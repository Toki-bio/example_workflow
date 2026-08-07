# Array genotyping (IDAT → PLINK): roadmap estimate

This document covers the **array/genotyping side** of the data landscape introduced in
[`DATA_TYPES_AND_WORKFLOWS.md`](DATA_TYPES_AND_WORKFLOWS.md) §3 — IDAT files off an Illumina
iScan scanner, turned into called genotypes. **This is a roadmap estimate, not a runnable
pipeline.** Nothing in `pipeline/` implements this path today; this document exists to size the
work and pick a direction before building it, the same way
[`DRAGEN_TO_OSS_MAPPING.md`](DRAGEN_TO_OSS_MAPPING.md) sizes the sequencing side.

Two vendor approaches turn raw IDATs into genotype calls; both are compared below, plus
open-source alternatives that avoid vendor lock-in entirely (see [Open-source callers](#open-source-callers-zcall--crlmm) below).

## GenomeStudio vs. DRAGEN Array

| | GenomeStudio | DRAGEN Array |
|---|---|---|
| **Platform** | Windows GUI, single workstation | Linux CLI, DRAGEN hardware or cloud (DRAGEN On-Demand) |
| **Automation** | Poor — manual clustering/QC is the standard workflow; not reliably scriptable | Strong — headless CLI, wrappable as a Nextflow/Snakemake step |
| **Throughput (24-sample plate, GSA-class array)** | ~2–4h wall time including analyst review | Minutes to low tens of minutes of compute (order-of-magnitude estimate — validate against current DRAGEN Array release notes before sizing infrastructure) |
| **Output** | Tabular "Final Report" / PED-MAP via the PLINK Report plugin — needs careful strand/allele (AB vs TOP/FORWARD) reconciliation before converting to BED/BIM/FAM | Native VCF and/or GTC — converts cleanly to PLINK BED/BIM/FAM, matching this repo's VCF-centric downstream shape |
| **Reproducibility** | Poor — edited clusters live as state inside a GUI project file, not a declarative config | Good — CLI invocation is declarative and version-pinnable |
| **Cost** | Free software (Illumina-account-gated download) + analyst time + a Windows box | Commercial DRAGEN license/hardware; exact array-module terms not confirmed — get an Illumina quote before committing |
| **Fits this repo's pattern?** | No — cannot be a reliable headless pipeline step | Yes — CLI-native, VCF output, consistent with the existing DRAGEN documentation pattern on the sequencing side |

**Recommendation:** build the array roadmap item around **DRAGEN Array as the automatable
primary**, and treat **GenomeStudio as the manual reference/QC comparator** — analogous to how
the sequencing side pairs an open-source primary (bcftools) with a vendor/secondary cross-check
(GATK4), except inverted here (DRAGEN Array primary, GenomeStudio as the legacy manual
comparator). Because *neither* GenomeStudio nor DRAGEN Array is open source, also plan an
open-source caller as a no-vendor-dependency fallback — see below.

**Confidence note:** the workflow shape for both tools (manifest `.bpm` + cluster `.egt` files,
GenomeStudio's Final Report format, DRAGEN's VCF/GTC output) is stable and well documented.
Specific DRAGEN Array CLI flags, exact supported-beadchip list, and licensing/pricing terms are
version-dependent and were **not** verified against current Illumina documentation for this
estimate — confirm those directly with Illumina before infrastructure spend.

## Open-source callers: zCall / crlmm

Both GenomeStudio and DRAGEN Array are proprietary. Two open-source options exist for calling
genotypes from Illumina array intensity data without ongoing vendor dependency — though neither
is a drop-in, from-scratch replacement in the same way bcftools replaces DRAGEN's sequencing
caller. They serve different roles:

### zCall
[zCall](https://github.com/wtsi-npg/zCall) ([Goldstein et al. 2012, *Bioinformatics*](https://academic.oup.com/bioinformatics/article/28/19/2543/290288)) is
a **post-processing rescue step**, not a standalone caller — it does not read IDATs directly.
It runs *after* GenomeStudio (or another GenCall-based caller) has already produced preliminary
calls and no-calls, and recalibrates the no-call/boundary genotypes using a per-SNP z-score
threshold model fit from common variants (MAF > 5%). This specifically improves accuracy on
**rare variants**, where GenCall's default clustering thresholds are tuned for common alleles
and are conservative — the original paper reports rare-variant (singleton) concordance with
whole-exome sequencing improving from 92.5% (GenCall alone) to 96.8% (GenCall + zCall). Practical
implications: still requires GenomeStudio (or another GenCall pass) in the loop first; recommends
**≥1000 samples** to reliably fit per-SNP thresholds, so it's a poor fit for small batches; adds
a real accuracy improvement specifically for rare-variant genotyping, which matters if this
repo's array roadmap ever needs to genotype rare/panel-relevant variants rather than just common
GWAS-array SNPs.

### crlmm
[crlmm](https://bioconductor.org/packages/crlmm/) (**C**orrected **R**obust **L**inear **M**odel
with **M**aximum-likelihood classification) is an R/Bioconductor package that genuinely **can**
call genotypes from raw intensities without GenomeStudio — it reads IDATs (via the companion
`illuminaio` Bioconductor package) directly, normalizes them, and applies its own clustering
algorithm to produce genotype calls, confidence scores, and copy-number estimates. Originally
built for Affymetrix arrays, later extended to Illumina Infinium BeadChips. This is the closer
analogue to "bcftools for arrays" — a real, independent, from-scratch open-source caller.
Practical implications: R/Bioconductor-based, so it fits a scripted/headless pipeline (unlike
GenomeStudio) but in a different language ecosystem than this repo's Python/bash tooling;
maintenance activity and current Bioconductor release status should be checked before adopting
it as a production dependency, since it is an older, narrower-audience package than
mainstream sequencing tools like bcftools/GATK4.

**Where each fits a future array pipeline:**
```
IDAT ──► crlmm (open-source primary caller) ──► genotype calls ──┐
IDAT ──► GenomeStudio/GenCall ──► zCall rescue (rare-variant pass) ──┤──► PLINK BED/BIM/FAM ──► imputation ──► VCF
IDAT ──► DRAGEN Array (vendor primary, if licensed) ─────────────────┘
```

## References

- [zCall paper (Goldstein et al. 2012)](https://academic.oup.com/bioinformatics/article/28/19/2543/290288) · [GitHub](https://github.com/wtsi-npg/zCall)
- [crlmm on Bioconductor](https://bioconductor.org/packages/crlmm/) · [illuminaio (IDAT reader)](https://bioconductor.org/packages/illuminaio/)
- [DATA_TYPES_AND_WORKFLOWS.md](DATA_TYPES_AND_WORKFLOWS.md) — where this fits in the wider data landscape
- [DRAGEN_TO_OSS_MAPPING.md](DRAGEN_TO_OSS_MAPPING.md) — the equivalent estimate for the sequencing side
