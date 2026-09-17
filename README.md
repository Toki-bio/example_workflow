# example_workflow — CPU-only germline variant-calling & clinical-panel pipeline

A CPU-only, license-free, open-source pipeline for germline variant calling and gene-panel
clinical reporting from sequencing (FASTQ) data — with the panel definition, reference, and
annotation sources all swappable via configuration rather than hardcoded. Originally built as a
drop-in replacement for an Illumina DRAGEN FPGA-accelerated pipeline that lost its
license/subscription; the DRAGEN case study is documented, but the pipeline itself is not
cardio-specific.

**No real patient data, sample identifiers, or licensed reference data are included anywhere
in this repository.** See [`docs/`](docs/) for details.

## Interactive guide (GitHub Pages)

**[toki-bio.github.io/example_workflow](https://toki-bio.github.io/example_workflow/)** — a
step-by-step walkthrough with live-updating, copy-pasteable commands. Adjust paths, panel, sample
IDs, and threads in the settings panel; every stage command updates as you type.

To publish the site (one-time): GitHub repo **Settings → Pages → Build and deployment → Deploy
from branch `main`, folder `/docs`**.

## Why this exists

DRAGEN (FPGA bitstream + a data-processing subscription) is one way to go from paired-end WGS
FASTQ to annotated, clinically-filtered variant calls for a gene panel. When a DRAGEN
subscription lapses — or was never available in the first place — you need a CPU-only
replacement that keeps the same inputs/outputs and clinical logic without specialized hardware or
a paid license. This repo documents that replacement, generalized so the same pipeline can serve
any gene panel or clinical/research goal, not just the one it was first built for.

See [`docs/DATA_TYPES_AND_WORKFLOWS.md`](docs/DATA_TYPES_AND_WORKFLOWS.md) for a broader,
tool-neutral introduction to the genomic data types and workflows this pipeline sits within —
useful background if you're new to this space.

## What's here

| Path | Contents |
|---|---|
| [`docs/index.html`](docs/index.html) | Interactive GitHub Pages guide — stage-by-stage walkthrough with adjustable, copy-pasteable commands |
| [`docs/DATA_TYPES_AND_WORKFLOWS.md`](docs/DATA_TYPES_AND_WORKFLOWS.md) | Introduction to genomic data types (sequencing vs. array), tool landscape (DRAGEN vs. samtools/GATK vs. PLINK, etc.), and goal/tier matrix — what's implemented here vs. roadmap |
| [`docs/ORIGINAL_DRAGEN_PIPELINE.md`](docs/ORIGINAL_DRAGEN_PIPELINE.md) | Case study: reconstruction of a real FPGA-accelerated DRAGEN pipeline, as run in production |
| [`docs/DRAGEN_TO_OSS_MAPPING.md`](docs/DRAGEN_TO_OSS_MAPPING.md) | Stage-by-stage table mapping each DRAGEN feature to its open-source replacement |
| [`docs/SAREK_ALTERNATIVE.md`](docs/SAREK_ALTERNATIVE.md) | Alternative sequencing engine: [nf-core/sarek](https://nf-co.re/sarek/3.9.0/) (Nextflow); clinical stages 05–07 shared |
| [`docs/ARRAY_GENOTYPING_ROADMAP.md`](docs/ARRAY_GENOTYPING_ROADMAP.md) | **(roadmap, not implemented)** IDAT → genotype calling estimate: GenomeStudio vs. DRAGEN Array, plus open-source callers (zCall, crlmm) |
| [`panels/`](panels/) | Swappable gene-panel configs (gene list + BED region file); ships with a cardiomyopathy/channelopathy panel as the worked example |
| [`envs/environment.yml`](envs/environment.yml) | Conda environment: python3, bwa, samtools, bcftools, fastp, htslib (tabix/bgzip) (GATK/snpEff optional, install separately) |
| [`pipeline/`](pipeline/) | The pipeline itself, per sample: align → call variants (bcftools, + GATK4 as an optional cross-check) → annotate (snpEff/VEP + ClinVar) → filter pathogenic calls → HTML report. After all samples: case/control aggregate. |
| [`test_case/`](test_case/) | A small, synthetic, shareable 2-sample demo (1 case + 1 control) using the cardiomyopathy example panel, running the whole pipeline end-to-end |

## Quick start (synthetic demo)

```bash
REPO="$HOME/example_workflow"
if [[ ! -d "$REPO/.git" ]]; then
  git clone https://github.com/Toki-bio/example_workflow.git "$REPO"
fi
cd "$REPO"
git pull origin main

# Create env only if missing
conda env list | awk '{print $1}' | grep -qx variant-pipeline \
  || conda env create -f envs/environment.yml

source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate variant-pipeline
bash pipeline/verify_tools.sh

cd test_case
bash run_demo.sh
python3 check_demo.py results
```

**Required on PATH:** `bwa`, `samtools`, `bcftools`, `fastp`, `tabix`, `bgzip`, `python3`  
**Optional:** `gatk` (secondary caller), `snpEff` (gene annotation — ClinVar still runs without it)

If you already have most tools in another conda env, run `bash pipeline/verify_tools.sh` to see what is missing.

This aligns two small synthetic samples against a ~48kb slice of real GRCh38 sequence (MYBPC3
+ MYH7), calls variants, annotates against a real published ClinVar pathogenic variant, and
generates an interactive HTML clinical report per sample — end to end in well under a minute,
no FPGA or license required. See [`test_case/README.md`](test_case/README.md) for details.

**Working directory:** clone the repo and run commands from that tree. Relative paths in the
interactive guide assume the repo root (the folder that contains `pipeline/` and `test_case/`).
The demo script (`test_case/run_demo.sh`) `cd`s itself and needs no path fiddling.

## Running on real data, or with a different panel

```bash
export REF_FASTA=/path/to/reference.fa          # GRCh37/hg19, GRCh38/hg38, T2T-CHM13, etc.
export CLINVAR_VCF=/path/to/clinvar.vcf.gz      # same build as REF_FASTA (NCBI: vcf_GRCh38, vcf_GRCh37, …)
export BCFTOOLS_PLOIDY=GRCh38                   # or GRCh37 — must match REF_FASTA
                                                 # (bcftools has no built-in T2T-CHM13 preset;
                                                 #  if REF_FASTA is T2T, use GRCh38 here for now
                                                 #  and check `bcftools call --ploidy ?` for updates)
export PANEL_GENES=/path/to/your_panel_genes.txt
export PANEL_BED=/path/to/your_panel.bed        # coordinates must match REF_FASTA build
export PANEL_NAME="Your Panel Name"
export SNPEFF_DB=GRCh38.mane.1.2.ensembl      # snpEff DB for your build
export RESTRICT_TO_PANEL=1                      # recommended for real WGS: call only PANEL_BED
pipeline/run_pipeline.sh my_cohort_manifest.tsv
```

> **⚠️ `RESTRICT_TO_PANEL=1` silently restricts variant calling to whatever `PANEL_BED` points
> at — with no warning if that BED doesn't match your actual study scope.** This has bitten real
> runs: a whole-exome cohort was accidentally called against a 26-gene disease-panel BED left
> over from a different, earlier configuration. Nothing in `03_call_variants.sh` errors or warns
> when `PANEL_BED` is narrower than intended — it just quietly produces a valid-looking VCF with
> far fewer variants than expected. Before trusting a real run's output, confirm `PANEL_BED`,
> `PANEL_NAME`, and `RESTRICT_TO_PANEL` all actually reflect what you meant to run — an exome
> study should either use `RESTRICT_TO_PANEL=0` (call everywhere the reads land) or a BED that
> genuinely covers the full exome capture design, not a gene-specific sub-panel BED.

Stage 04 automatically renames ClinVar contigs when needed (`1` ↔ `chr1`) so NCBI ClinVar
annotates against UCSC-style references. Without a snpEff database, gene symbols fall back to
ClinVar `GENEINFO`.

**What "hard-filtered" is supposed to mean** (worth knowing so you can verify your own copy of
`03_call_variants.sh` matches, in case of local edits or merge drift): the intended logic is
`bcftools filter -e 'QUAL<20 || INFO/DP<10' -s LowQual`, followed by keeping only `PASS` records.
A local copy that instead does `bcftools view -f PASS,.` directly on the un-filtered calls (i.e.
skips the `bcftools filter` step entirely) will silently pass through *every* record, since
`bcftools call` leaves `FILTER` unset (`.`) on all sites by default — the output file is still
named `*.hard-filtered.vcf.gz` but nothing has actually been filtered. This exact regression has
occurred in a real deployment of this pipeline; it produces no error and no obviously wrong
output, only a quietly inflated variant count with low-quality/low-depth noise mixed into
downstream annotation and pathogenic-filtering. If a run's `hard-filtered.vcf.gz` has roughly the
same record count as its `raw.vcf.gz`, the filter step isn't actually running.


`my_cohort_manifest.tsv` is tab-separated: `sample_id  case|control  R1.fastq[.gz]  R2.fastq[.gz]`
(see `test_case/samples.tsv` for the format). R1/R2 accept plain `.fastq` or `.fastq.gz`; the
align step auto-resolves paths if the extension is omitted. See [`panels/README.md`](panels/README.md) for how
to define a new panel — no pipeline code changes needed.

### Preparing the real-data inputs above

These paths are not auto-generated by this pipeline; you obtain them once per reference build:

- **`REF_FASTA`**: a FASTA for your build (e.g. from Ensembl/UCSC/NCBI), then index it —
  `bwa index REF_FASTA` and `samtools faidx REF_FASTA` (`pipeline/01_prepare_reference.sh` does
  this automatically on first run if the index files are missing, but the FASTA itself must
  already be downloaded).
- **`CLINVAR_VCF`**: download from NCBI's ClinVar FTP (e.g.
  `https://ftp.ncbi.nlm.nih.gov/pub/clinvar/vcf_GRCh38/clinvar.vcf.gz`, or `vcf_GRCh37` for that
  build), then `tabix -p vcf clinvar.vcf.gz`.
- **`SNPEFF_DB`** (optional): `snpEff download <db-name>` (e.g. `GRCh38.mane.1.2.ensembl`) —
  only needed if you want transcript/consequence annotation; ClinVar annotation works without it.

**Measured real-data sizing** (16-thread run, real WES sample, ~10-15 GB paired FASTQ input,
fastp → align → call → annotate → filter → report, single sample at a time):

| Metric | Observed |
|---|---|
| Wall time | ~60-80 min per sample (~5-6 min per GB of input FASTQ, roughly linear) |
| CRAM output size | ~25-27% of input FASTQ size (e.g. 14.3 GB FASTQ → 3.7 GB CRAM) |
| Total per-sample output (CRAM + VCFs + report) | ~ equal to CRAM size — everything else is small by comparison |

`run_pipeline.sh` processes samples **strictly sequentially**, one at a time, even when the host
has many more cores than a single sample's `THREADS` setting uses. If you have CPU headroom
(check with `nproc`), running multiple samples' pipelines concurrently (separate
`bash pipeline/run_pipeline.sh` invocations, or a wrapper that backgrounds several at once) cuts
wall-clock time for a cohort roughly in proportion to how many you run in parallel — a 16-sample
cohort at ~70 min/sample sequential (~18-19 hours) drops to ~5 hours run 4-at-a-time, for example.
Size your run conservatively and monitor the first sample before committing to a full cohort.

## Troubleshooting

- **`conda env create` fails / hangs on solving.** Try `conda config --set channel_priority
  strict` first, or use `mamba env create -f envs/environment.yml` instead of `conda`.
- **`ERROR: ... .fa.fai not found` / bwa index errors.** `REF_FASTA` hasn't been indexed yet —
  see "Preparing the real-data inputs" above; `01_prepare_reference.sh` builds missing indexes
  automatically but the FASTA itself must exist first.
- **ClinVar annotation transfers nothing (no CLNSIG on any variant).** Almost always a contig
  naming mismatch (`1` vs `chr1`) between `REF_FASTA`/your VCF and `CLINVAR_VCF` that stage 04's
  auto-harmonization didn't catch, or `CLINVAR_VCF` is for the wrong genome build. Confirm with
  `bcftools query -f '%CHROM\n' "$CLINVAR_VCF" | head -1` vs the same for your annotated VCF.
- **`gatk: command not found` / GATK step silently skipped.** GATK is optional (see Required vs
  Optional above) — `03_call_variants.sh` skips it automatically when absent and continues with
  the bcftools-only path. Install GATK4 and put it on `PATH` if you want the cross-check.
- **snpEff step logs a warning and continues with ClinVar-only annotation.** Either snpEff isn't
  installed, or `SNPEFF_DB` hasn't been downloaded (`snpEff download <db-name>`) — this is
  non-fatal by design; gene symbols fall back to ClinVar's `GENEINFO` field.
- **Still stuck?** Run `bash pipeline/verify_tools.sh` first — it reports exactly which required
  and optional tools are missing before you dig further.
- **Editing `pipeline/*.sh` while a run is in progress corrupts that run.** Bash does not load an
  entire script into memory before executing it — for a script actively running, it reads the
  next line from the file at its current byte offset each time. If you edit the file in place
  while it's mid-execution (even just adding a comment or a couple of lines earlier in the file),
  every subsequent read lands at the wrong byte offset and the script can start executing garbled
  commands (observed in production: a `bwa mem | samtools fixmate | samtools sort` pipeline
  half-finished, then choked on a corrupted command name once the file was edited underneath it).
  Wait for a stage script to finish (or kill it first) before editing it — never hot-patch a
  script that's currently running.
- **`bcftools call -mv` (used throughout `03_call_variants.sh`) only emits variant sites.** A
  sample that's homozygous-reference at a given position produces **no VCF record at all** —
  not a `0/0` genotype line, just silence. This is fine for per-sample pathogenic-variant
  reporting (the pipeline's actual purpose), but it's a trap if you repurpose these VCFs for
  anything that needs a real denominator — e.g. computing cohort allele frequencies, or comparing
  against an orthogonal genotyping platform (SNP array, etc.) position-by-position. For that, you
  need `bcftools call -m` **without** `-v` on the positions you care about, which forces a real
  genotype call (including `0/0`) at every requested site. Using the variant-only VCFs for that
  kind of comparison silently drops every reference-matching sample from the count, biasing
  frequency estimates upward.

## Known limitations / roadmap

- Only the sequencing (FASTQ) input path is implemented. The array/genotyping path (IDAT/CEL →
  PLINK → imputation) is documented as a design in
  [`docs/DATA_TYPES_AND_WORKFLOWS.md`](docs/DATA_TYPES_AND_WORKFLOWS.md) but not yet built here.
- No equivalent to DRAGEN's proprietary pangenome graph-reference mode is provided (linear
  reference only — any build you configure via `REF_FASTA`, not pangenome graphs) — see
  `docs/DRAGEN_TO_OSS_MAPPING.md`.
- **Build consistency:** `REF_FASTA`, ClinVar VCF, panel BED, `SNPEFF_DB`, and `BCFTOOLS_PLOIDY`
  must all refer to the same genome assembly (e.g. all GRCh38 or all GRCh37). The shipped demo
  uses GRCh38; switching to GRCh37 or T2T means updating every coordinate-dependent resource, not
  just the FASTA.
- Exact variant calls and QC metrics will differ slightly from DRAGEN's output, as expected
  when comparing any two independently-implemented aligners/callers. Cross-validation against
  an original DRAGEN pipeline's pathogenic-variant calls on real samples (kept on the source
  infrastructure, never included here) is a recommended follow-up before relying on this
  pipeline for anything beyond technical demonstration.
- Annotation uses independently-downloaded public resources (ClinVar, and optionally
  snpEff/VEP), not Illumina's licensed Nirvana data bundle.
- Only two variant callers (bcftools, GATK4) are wired in; pluggable alternate callers (e.g.
  DeepVariant) and workflow-manager orchestration (Nextflow/Snakemake) are roadmap items.
- **`02_align.sh`'s `bwa mem` call must include a `-R "@RG\tID:...\tSM:...\tPL:...\tLB:..."`
  read-group argument.** GATK4's `HaplotypeCaller` (the optional cross-check caller) requires a
  read group to run at all and will error without one; a CRAM/BAM aligned without `-R` will work
  fine for the bcftools-only path (making the omission easy to miss) and then fail the moment
  GATK is installed and enabled. If you're maintaining a fork or local patch of `02_align.sh`,
  confirm the read group is still present — this is exactly the kind of silent, low-visibility
  regression that survives until someone turns GATK on.
- **HGVS-normalized indel consequence calls (`start_lost`, `frameshift_variant`, etc.) can be
  representation artifacts, not real severity, when the indel sits in a short repeat that spans
  a boundary** (e.g. the last base of a UTR matching the first base of the adjacent start codon).
  HGVS convention reports such ambiguous indels at their most-3′ equivalent position (flagged by
  `INFO_REALIGN_3_PRIME` in the `ANN` field), which can make a harmless UTR insertion get
  reported as duplicating the coding sequence's first base — annotated as a destroyed start
  codon, even though a real ribosome scanning the mRNA would simply find the same intact start
  codon one base later and translate a normal protein. A SnpEff `HIGH` impact label on an indel
  near a transcript/UTR boundary or short repeat is worth a manual pileup check (or Sanger
  confirmation before clinical reporting) rather than being trusted at face value — especially
  since only one caller (bcftools) runs by default with no independent cross-check unless GATK
  is installed (see the read-group note above).

## License

See [`LICENSE`](LICENSE). The example gene panel, pipeline logic, and clinical filtering rules
are provided as-is for technical/educational purposes and are **not validated for clinical use**.
