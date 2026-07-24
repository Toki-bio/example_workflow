(function () {
  "use strict";

  const STORAGE_KEY = "variant-pipeline-guide-v4";
  const SCRIPTS_BASE = "assets/scripts/";

  const DEFAULTS = {
    refFasta: "test_case/refs/panel_region.fa",
    clinvarVcf: "test_case/refs/clinvar_panel_subset.vcf.gz",
    panelGenes: "panels/cardiomyopathy/cardiomyopathy_genes.txt",
    panelBed: "panels/cardiomyopathy/cardiomyopathy_genes_grch38.bed",
    panelName: "Cardiomyopathy (demo)",
    snpeffDb: "GRCh38.mane.1.2.ensembl",
    bcftoolsPloidy: "GRCh38",
    sampleId: "case1",
    sampleType: "case",
    r1Fastq: "test_case/fastq/case1_R1.fastq.gz",
    r2Fastq: "test_case/fastq/case1_R2.fastq.gz",
    threads: "8",
    outDir: "test_case/results",
    tmpDir: "test_case/results/tmp",
    manifest: "test_case/samples.tsv",
    caller: "bcftools",
    sarekSamplesheet: "samplesheet.csv",
    sarekOutDir: "sarek_results",
    sarekProfile: "docker",
    sarekGenome: "GRCh38",
    sarekTools: "haplotypecaller,snpeff",
    sarekVcf: "sarek_results/variant_calling/haplotypecaller/case1/case1.haplotypecaller.vcf.gz",
  };

  const KIND_LABELS = {
    file: "File path — you download or create this file on disk",
    tool: "Tool lookup name — not a path; install via the tool's own command",
    setting: "Setting you choose — folder, number, or label",
    create: "File you create — you write this yourself",
  };

  const VAR_META = {
    refFasta: {
      label: "REF_FASTA",
      group: "reference",
      kind: "file",
      bundled: "test_case/refs/panel_region.fa (tiny slice, in repo)",
      what: "Path to your reference genome FASTA — reads align to this sequence; variants are called relative to it.",
      where: "Real WGS: download whole-genome FASTA (GRCh38 from UCSC/GATK bundle, GRCh37/hg19 similarly, T2T from marbl/CHM13). Put it outside the repo (e.g. /data/refs/hg38.fa). Run stage 01 once to build indexes.",
      example: "/data/refs/hg38.fa",
      note: "ClinVar, panel BED, SNPEFF_DB, and BCFTOOLS_PLOIDY must use the same genome build.",
    },
    clinvarVcf: {
      label: "CLINVAR_VCF",
      group: "reference",
      kind: "file",
      bundled: "test_case/refs/clinvar_panel_subset.vcf.gz (1 variant, in repo)",
      what: "Path to ClinVar as a bgzip + tabix VCF. Pipeline joins it to add clinical significance (Pathogenic, Benign, …).",
      where: "Real data: wget from NCBI FTP — vcf_GRCh38/clinvar.vcf.gz or vcf_GRCh37/ for hg19. Must match REF_FASTA build. Stage 01 runs tabix if the file exists.",
      example: "/data/clinvar/clinvar_grch38.vcf.gz",
      note: "Wrong build = chromosome names and positions won't match your calls.",
    },
    snpeffDb: {
      label: "SNPEFF_DB",
      group: "reference",
      kind: "tool",
      bundled: "Not in the default conda env — install snpeff separately if you want gene annotation",
      what: "snpEff database name (not a file path). snpEff looks up this name in its own data/ folder to add gene symbols and consequences to VCFs.",
      where: "After conda activate: snpEff databases (list), then snpEff download GRCh38.mane.1.2.ensembl — installs into snpEff's data/. Type the same name here. GRCh37: snpEff download GRCh37.75.",
      example: "GRCh38.mane.1.2.ensembl",
      note: "Optional. If not installed, stage 04 skips gene annotation; ClinVar still runs. Different from REF_FASTA — you don't point at a .fa file.",
    },
    bcftoolsPloidy: {
      label: "BCFTOOLS_PLOIDY",
      group: "reference",
      kind: "tool",
      bundled: "GRCh38 preset is built into bcftools — no download",
      what: "bcftools call --ploidy preset — tells bcftools which human chromosome naming/ploidy model to use.",
      where: "No file to download. Run bcftools call -l to list presets. GRCh38 with hg38, GRCh37 with hg19.",
      example: "GRCh38",
    },
    panelGenes: {
      label: "PANEL_GENES",
      group: "panel",
      kind: "file",
      bundled: "panels/cardiomyopathy/cardiomyopathy_genes.txt (in repo)",
      what: "Path to a plain-text gene list — one HGNC symbol per line (e.g. MYBPC3).",
      where: "Demo uses shipped example. Real panel: you or your clinical team maintain this file.",
      example: "panels/cardiomyopathy/cardiomyopathy_genes.txt",
    },
    panelBed: {
      label: "PANEL_BED",
      group: "panel",
      kind: "file",
      bundled: "panels/cardiomyopathy/cardiomyopathy_genes_grch38.bed (in repo, GRCh38 coords)",
      what: "Path to a BED file of genomic regions for your panel genes (chrom, start, end).",
      where: "Build from Ensembl BioMart or UCSC Table Browser. Coordinates must match REF_FASTA build.",
      example: "panels/cardiomyopathy/cardiomyopathy_genes_grch38.bed",
    },
    panelName: {
      label: "PANEL_NAME",
      group: "panel",
      kind: "setting",
      bundled: "Any label you like — demo uses Cardiomyopathy (demo)",
      what: "Display name in HTML report titles — not a file.",
      where: "Pick any short string for your study or panel.",
      example: "Cardiomyopathy",
    },
    threads: {
      label: "THREADS",
      group: "runtime",
      kind: "setting",
      bundled: "No default file — typical value 8 (demo uses 2)",
      what: "CPU thread count for bwa, samtools, bcftools, fastp.",
      where: "Set to available cores on your machine (8–32 typical).",
      example: "8",
    },
    outDir: {
      label: "OUT_DIR",
      group: "runtime",
      kind: "setting",
      bundled: "test_case/results (demo) — pipeline creates the folder",
      what: "Output directory for BAMs, VCFs, reports, JSONL. You choose the path; pipeline creates it.",
      where: "Any writable folder. Run from repo root or test_case/ — use relative or absolute paths consistently.",
      example: "results",
    },
    tmpDir: {
      label: "TMP_DIR",
      group: "runtime",
      kind: "setting",
      bundled: "Defaults to OUT_DIR/tmp",
      what: "Scratch space for sorted BAMs and intermediate VCFs during a run.",
      where: "Fast local disk recommended for large WGS. Pipeline creates it if missing.",
      example: "results/tmp",
    },
    sampleId: {
      label: "SAMPLE_ID",
      group: "sample",
      kind: "setting",
      bundled: "case1 in demo",
      what: "Sample identifier — used in output filenames and BAM read groups.",
      where: "Match your LIMS / manifest naming.",
      example: "case1",
    },
    sampleType: {
      label: "SAMPLE_TYPE",
      group: "sample",
      kind: "setting",
      bundled: "case or control",
      what: "case = sample of interest; control = comparison — tags JSONL for cohort aggregation.",
      where: "Per-sample when running stages individually; manifest column for full cohort runs.",
      type: "select",
      options: ["case", "control"],
    },
    r1Fastq: {
      label: "R1 FASTQ",
      group: "sample",
      kind: "file",
      bundled: "test_case/fastq/case1_R1.fastq.gz (synthetic, in repo)",
      what: "Path to forward (R1) paired-end reads from the sequencer.",
      where: "Real data: your instrument or demultiplexing output. .fastq or .fastq.gz.",
      example: "/data/fastq/sample_R1.fastq.gz",
    },
    r2Fastq: {
      label: "R2 FASTQ",
      group: "sample",
      kind: "file",
      bundled: "test_case/fastq/case1_R2.fastq.gz (synthetic, in repo)",
      what: "Path to reverse (R2) paired-end reads — mate of R1.",
      where: "Same rules as R1.",
      example: "/data/fastq/sample_R2.fastq.gz",
    },
    caller: {
      label: "CALLER",
      group: "sample",
      kind: "setting",
      bundled: "bcftools (default); gatk optional secondary output in stage 03",
      what: "Which hard-filtered VCF from stage 03 to annotate. The default pipeline uses bcftools.",
      where: "bcftools = default. gatk = only if GATK4 is installed and you ran stage 03 with it.",
      type: "select",
      options: ["bcftools", "gatk"],
    },
    manifest: {
      label: "MANIFEST_TSV",
      group: "cohort",
      kind: "create",
      bundled: "test_case/samples.tsv (in repo)",
      what: "Path to a tab-separated cohort table you create: sample_id, case|control, R1 path, R2 path.",
      where: "Copy test_case/samples.tsv as a template. One row per sample. Used by run_pipeline.sh.",
      example: "samples.tsv",
    },
    sarekSamplesheet: {
      label: "SAREK_SAMPLESHEET",
      group: "sarek",
      kind: "create",
      bundled: "docs/assets/scripts/sarek_samplesheet.example.csv",
      what: "CSV samplesheet for nf-core/sarek — columns: patient, sample, lane, fastq_1, fastq_2. Different from this repo's TSV manifest.",
      where: "You create this file. See sarek usage docs and SAREK_ALTERNATIVE.md. One row per FASTQ pair.",
      example: "samplesheet.csv",
    },
    sarekOutDir: {
      label: "SAREK_OUTDIR",
      group: "sarek",
      kind: "setting",
      bundled: "Any writable folder you choose",
      what: "sarek --outdir — where Nextflow writes BAMs, VCFs, MultiQC, etc.",
      where: "Pick a path with enough disk space (WGS needs hundreds of GB per cohort).",
      example: "sarek_results",
    },
    sarekProfile: {
      label: "SAREK_PROFILE",
      group: "sarek",
      kind: "setting",
      bundled: "docker or singularity — must match your system",
      what: "Nextflow -profile flag — selects container runtime and resource defaults.",
      where: "Use docker on a laptop with Docker installed, singularity on HPC. Institute configs also exist.",
      example: "docker",
    },
    sarekGenome: {
      label: "SAREK_GENOME",
      group: "sarek",
      kind: "setting",
      bundled: "GRCh38 via sarek iGenomes cache",
      what: "Reference genome preset for sarek --genome.",
      where: "GRCh38, GRCh37, etc. per sarek docs. First run downloads reference cache.",
      example: "GRCh38",
    },
    sarekTools: {
      label: "SAREK_TOOLS",
      group: "sarek",
      kind: "setting",
      bundled: "haplotypecaller,snpeff is a common germline panel choice",
      what: "Comma-separated list passed to sarek --tools (callers + annotators).",
      where: "See sarek parameter docs: haplotypecaller, deepvariant, snpeff, vep, mutect2, ...",
      example: "haplotypecaller,snpeff",
    },
    sarekVcf: {
      label: "SAREK_VCF",
      group: "sarek",
      kind: "file",
      bundled: "Path under sarek --outdir — varies by --tools and version",
      what: "Annotated VCF from sarek for one sample — input to this repo's clinical scripts (stages 05–07).",
      where: "After sarek completes, find per-sample VCF under variant_calling/ in --outdir. Adjust path to match your run.",
      example: "sarek_results/variant_calling/haplotypecaller/case1/case1.haplotypecaller.vcf.gz",
      note: "Exact subdirectory names depend on sarek version and --tools. Check sarek output docs.",
    },
  };

  const GROUP_TITLES = {
    reference: "Reference and annotation databases",
    panel: "Gene panel configuration",
    runtime: "Runtime directories and parallelism",
    sample: "Sample input",
    cohort: "Cohort manifest",
  };

  const GROUP_INTROS = {
    reference:
      "Reference build assets. Mix of file paths (you download) and tool names (snpEff/bcftools look up internally). All must match the same genome assembly. See Getting started if unsure which is which.",
    panel:
      "Gene panel files (paths in the repo for the demo). Swap for your own panel — no pipeline code changes.",
    runtime: "Where outputs go and how much CPU to use. Pipeline creates OUT_DIR/TMP_DIR if missing.",
    sample: "Per-sample paths and IDs when running one sample at a time. Paths are on your machine.",
    cohort: "Batch manifest you write when running the full pipeline over many samples.",
    sarek: "nf-core/sarek settings — external Nextflow pipeline, not shipped in this repo.",
  };

  const CLINICAL_STAGES = [
    {
      id: "filter",
      num: "05",
      title: "Filter pathogenic calls",
      desc: "Requires annotated VCF (from bash pipeline stage 04 or from sarek output). Writes per-sample JSONL of ClinVar Pathogenic / Likely pathogenic variants.",
      vars: ["sampleId", "sampleType", "caller", "outDir"],
      varsSarek: ["sampleId", "sampleType", "sarekVcf", "outDir"],
      file: "05_filter_pathogenic.py",
      runName: "05_filter_pathogenic.py",
      isPython: true,
    },
    {
      id: "report",
      num: "06",
      title: "Generate HTML report",
      desc: "Per-sample interactive clinical report (panel + ClinVar). Same script regardless of which engine produced the VCF.",
      vars: ["sampleId", "caller", "panelGenes", "panelName", "outDir"],
      varsSarek: ["sampleId", "sarekVcf", "panelGenes", "panelName", "outDir"],
      file: "07_generate_report.py",
      runName: "07_generate_report.py",
      isPython: true,
    },
    {
      id: "aggregate",
      num: "07",
      title: "Aggregate cohort",
      desc: "After stage 05 for every sample: case vs control counts per pathogenic variant.",
      vars: ["outDir"],
      file: "06_aggregate_case_control.py",
      runName: "06_aggregate_case_control.py",
      isPython: true,
    },
  ];

  const STAGES_BASH = [
    {
      id: "setup",
      num: "0",
      title: "Environment setup",
      desc: "Once per machine: clone, create conda env, activate, verify tools. Required: bwa, samtools, bcftools, fastp, tabix, python3.",
      vars: [],
      file: null,
      runName: "setup.sh",
    },
    {
      id: "config",
      num: "00",
      title: "Shared configuration",
      desc: "Every pipeline/*.sh script sources 00_config.sh. Defaults already point at the demo files inside this repo (resolved from the script location, not your shell cwd). Override with export for real data.",
      vars: ["refFasta", "clinvarVcf", "snpeffDb", "bcftoolsPloidy", "panelGenes", "panelBed", "panelName", "threads", "outDir", "tmpDir"],
      file: "00_config.sh",
      personalize: "config",
      runName: "00_config.sh",
    },
    {
      id: "prepare",
      num: "01",
      title: "Prepare reference",
      desc: "Build BWA index, samtools .fai, tabix ClinVar. GATK .dict only if gatk is installed. Safe to re-run.",
      vars: ["refFasta", "clinvarVcf", "snpeffDb", "bcftoolsPloidy", "threads", "outDir", "tmpDir"],
      file: "01_prepare_reference.sh",
      runName: "01_prepare_reference.sh",
    },
    {
      id: "align",
      num: "02",
      title: "Align reads",
      desc: "fastp QC → bwa mem → sort → markdup → index. Accepts .fastq or .fastq.gz. FASTQ paths may be absolute or relative to your shell cwd (or to the manifest dir when using run_pipeline.sh).",
      vars: ["sampleId", "r1Fastq", "r2Fastq", "refFasta", "threads", "outDir", "tmpDir"],
      file: "02_align.sh",
      runName: "02_align.sh",
    },
    {
      id: "call",
      num: "03",
      title: "Call variants",
      desc: "Requires stage 02 BAM. bcftools mpileup+call (primary). GATK4 runs only if gatk is on PATH.",
      vars: ["sampleId", "refFasta", "bcftoolsPloidy", "threads", "outDir", "tmpDir"],
      file: "03_call_variants.sh",
      runName: "03_call_variants.sh",
    },
    {
      id: "annotate",
      num: "04",
      title: "Annotate variants",
      desc: "Requires stage 03 hard-filtered VCF. snpEff (if DB installed) + ClinVar via bcftools annotate. Optional VEP cross-check.",
      vars: ["sampleId", "caller", "clinvarVcf", "snpeffDb", "refFasta", "outDir", "tmpDir"],
      file: "04_annotate.sh",
      runName: "04_annotate.sh",
    },
    {
      id: "filter",
      num: "05",
      title: "Filter pathogenic calls",
      desc: "Requires stage 04 annotated VCF. Writes per-sample JSONL of ClinVar Pathogenic / Likely pathogenic variants.",
      vars: ["sampleId", "sampleType", "caller", "outDir"],
      file: "05_filter_pathogenic.py",
      runName: "05_filter_pathogenic.py",
      isPython: true,
    },
    {
      id: "report",
      num: "06",
      title: "Generate HTML report",
      desc: "Requires stage 04 annotated VCF. Per-sample interactive clinical report (panel + ClinVar).",
      vars: ["sampleId", "caller", "panelGenes", "panelName", "outDir"],
      file: "07_generate_report.py",
      runName: "07_generate_report.py",
      isPython: true,
    },
    {
      id: "aggregate",
      num: "07",
      title: "Aggregate cohort",
      desc: "Run after stage 05 for every sample. Case vs control counts per pathogenic variant.",
      vars: ["outDir"],
      file: "06_aggregate_case_control.py",
      runName: "06_aggregate_case_control.py",
      isPython: true,
    },
    {
      id: "fullrun",
      num: "∞",
      title: "Full cohort run (recommended)",
      desc: "One command: prepares reference, then for each manifest row runs align→call→annotate→filter→report, then aggregates. Prefer this over copying stages 01–07 by hand. Easiest path: cd test_case && bash run_demo.sh",
      vars: ["manifest", "refFasta", "clinvarVcf", "panelGenes", "panelBed", "panelName", "threads", "outDir", "tmpDir"],
      file: "run_pipeline.sh",
      runName: "run_pipeline.sh",
    },
  ];

  const STAGES_SAREK = [
    {
      id: "sarek-setup",
      num: "0",
      title: "Install Nextflow + sarek",
      desc: "One-time setup: Nextflow + Docker or Singularity. Not part of this repo — run externally. Test with sarek -profile test before real data.",
      vars: [],
      file: null,
      runName: "sarek-setup.sh",
    },
    {
      id: "sarek-samplesheet",
      num: "1",
      title: "Prepare samplesheet",
      desc: "CSV with columns patient,sample,lane,fastq_1,fastq_2 — different from this repo's TSV manifest. See SAREK_ALTERNATIVE.md.",
      vars: ["sarekSamplesheet"],
      file: "sarek_samplesheet.example.csv",
      runName: "samplesheet.csv",
    },
    {
      id: "sarek-run",
      num: "2",
      title: "Run nf-core/sarek",
      desc: "Runs QC → align → BQSR → variant calling → annotation in containers. Output: annotated VCFs under SAREK_OUTDIR.",
      vars: ["sarekSamplesheet", "sarekOutDir", "sarekProfile", "sarekGenome", "sarekTools"],
      file: null,
      runName: "sarek-run.sh",
    },
    ...CLINICAL_STAGES,
  ];

  let activePathway = "bash";

  function getActiveStages() {
    let stages;
    if (activePathway === "sarek") {
      stages = STAGES_SAREK.map((s) => {
        if (!s.varsSarek) return s;
        return { ...s, vars: s.varsSarek };
      });
    } else if (activePathway === "array") {
      return [];
    } else {
      stages = STAGES_BASH;
    }
    return enrichStages(stages);
  }

  let settings = { ...DEFAULTS };
  let scriptBodies = {};
  let locked = {};
  let textareaEls = {};
  let runEls = {};

  function loadState() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        settings = { ...DEFAULTS, ...(parsed.settings || {}) };
        activePathway = parsed.activePathway || "bash";
        locked = parsed.locked || {};
        const edits = parsed.edits || {};
        Object.keys(edits).forEach((id) => {
          if (locked[id] && edits[id]) {
            scriptBodies["_edit_" + id] = edits[id];
          }
        });
      }
    } catch (_) {
      settings = { ...DEFAULTS };
      locked = {};
    }
  }

  function saveState() {
    const edits = {};
    Object.keys(textareaEls).forEach((id) => {
      if (locked[id] && textareaEls[id]) {
        edits[id] = textareaEls[id].value;
        scriptBodies["_edit_" + id] = edits[id];
      }
    });
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({ settings, locked, edits, activePathway })
    );
  }

  function resolveFastq(path) {
    if (!path) return { display: "", format: "unknown", note: "Enter a path" };
    const lower = path.toLowerCase();
    if (lower.endsWith(".fastq.gz") || lower.endsWith(".fq.gz")) {
      return { display: path, format: "gzip", note: "Gzip FASTQ — fastp reads directly, no unpack step" };
    }
    if (lower.endsWith(".fastq") || lower.endsWith(".fq")) {
      return { display: path, format: "plain", note: "Plain FASTQ — used directly" };
    }
    return {
      display: path,
      format: "auto",
      note: "No extension — pipeline tries .fastq.gz, .fq.gz, .fastq, .fq",
    };
  }

  function cwdPreamble() {
    return `# Prerequisite: be inside the cloned repo (folder that contains pipeline/ and test_case/).
# Example:
#   cd /path/to/example_workflow
# And have the conda env active:
#   source "$(conda info --base)/etc/profile.d/conda.sh"
#   conda activate variant-pipeline
`;
  }

  function exportsBlock(s) {
    return `${cwdPreamble()}
export REF_FASTA="${s.refFasta}"
export CLINVAR_VCF="${s.clinvarVcf}"
export PANEL_GENES="${s.panelGenes}"
export PANEL_BED="${s.panelBed}"
export PANEL_NAME="${s.panelName}"
export SNPEFF_DB="${s.snpeffDb}"
export BCFTOOLS_PLOIDY="${s.bcftoolsPloidy}"
export THREADS=${s.threads}
export OUT_DIR="${s.outDir}"
export TMP_DIR="${s.tmpDir}"`;
  }

  const renderedVarKeys = new Set();

  function personalizeConfig(text, s) {
    const subs = {
      REF_FASTA: s.refFasta,
      CLINVAR_VCF: s.clinvarVcf,
      SNPEFF_DB: s.snpeffDb,
      BCFTOOLS_PLOIDY: s.bcftoolsPloidy,
      PANEL_BED: s.panelBed,
      PANEL_GENES: s.panelGenes,
      PANEL_NAME: s.panelName,
      THREADS: s.threads,
      OUT_DIR: s.outDir,
      TMP_DIR: s.tmpDir,
    };
    let out = text;
    Object.entries(subs).forEach(([key, val]) => {
      out = out.replace(new RegExp(`\\$\\{${key}:=[^}]*\\}`, "g"), `\${${key}:=${val}}`);
    });
    return out;
  }

  function annotatedVcfPath(s) {
    if (activePathway === "sarek") return s.sarekVcf;
    return `${s.outDir}/${s.sampleId}.${s.caller}.annotated.vcf.gz`;
  }

  const RUNNERS = {
    setup: () =>
      `# === Step 0: install tools (run once) ===
# Clone if you have not already:
#   git clone https://github.com/Toki-bio/example_workflow.git
cd /path/to/example_workflow

# Create env (skip if it already exists)
conda env create -f envs/environment.yml

# Activate (needed in every new shell)
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate variant-pipeline

# Verify required tools (bwa samtools bcftools fastp tabix bgzip python3)
bash pipeline/verify_tools.sh

# Optional: GATK secondary caller, snpEff gene annotation
# conda install -c bioconda gatk4 snpeff

# Quick path after setup: run the built-in demo (no extra downloads)
#   cd test_case && bash run_demo.sh && python3 check_demo.py results
`,

    config: (s) => `${exportsBlock(s)}

# These exports override pipeline/00_config.sh defaults for subsequent commands
# in THIS shell. Pipeline scripts also work with zero exports (demo defaults).
# Check resolved values:
echo "REF_FASTA=$REF_FASTA"
echo "OUT_DIR=$OUT_DIR"
`,

    prepare: (s) => `${exportsBlock(s)}

bash pipeline/01_prepare_reference.sh
`,

    align: (s) => {
      const r1 = resolveFastq(s.r1Fastq);
      const r2 = resolveFastq(s.r2Fastq);
      return `${exportsBlock(s)}

# R1: ${r1.note}
# R2: ${r2.note}
bash pipeline/02_align.sh ${s.sampleId} ${s.r1Fastq} ${s.r2Fastq}
`;
    },

    call: (s) => `${exportsBlock(s)}

bash pipeline/03_call_variants.sh ${s.sampleId}
`,

    annotate: (s) => `${exportsBlock(s)}

bash pipeline/04_annotate.sh ${s.sampleId} ${s.caller}
`,

    filter: (s) => `${cwdPreamble()}
python3 pipeline/05_filter_pathogenic.py \\
  "${annotatedVcfPath(s)}" \\
  "${s.sampleId}" \\
  "${s.sampleType}" \\
  "${s.outDir}/${s.sampleId}.${s.sampleType}.pathogenic.jsonl"
`,

    report: (s) => `${cwdPreamble()}
python3 pipeline/07_generate_report.py \\
  "${annotatedVcfPath(s)}" \\
  "${s.sampleId}" \\
  "${s.panelGenes}" \\
  "${s.outDir}/${s.sampleId}.report.html" \\
  "${s.panelName}"
`,

    aggregate: (s) => `${cwdPreamble()}
# Glob is expanded by Python (quotes are intentional)
python3 pipeline/06_aggregate_case_control.py \\
  "${s.outDir}/*.pathogenic.jsonl" \\
  "${s.outDir}/aggregated_pathogenic_variants.json"
`,

    fullrun: (s) => `${exportsBlock(s)}

# --- Easiest: synthetic demo (recommended first run) ---
# cd test_case
# bash run_demo.sh
# python3 check_demo.py results

# --- Or full cohort with your settings ---
# Manifest columns (tab-separated, no header):
#   sample_id   case|control   R1.fastq[.gz]   R2.fastq[.gz]
# Relative FASTQ paths are resolved from the manifest's directory.
bash pipeline/run_pipeline.sh ${s.manifest}
`,

    "sarek-setup": () =>
      `# === nf-core/sarek setup (external — not in this repo) ===
# Install Nextflow: https://www.nextflow.io/docs/latest/getstarted.html
curl -s https://get.nextflow.io | bash
sudo mv nextflow /usr/local/bin/   # or add to PATH

# Install Docker OR Singularity (pick one for -profile)

# Smoke test — uses sarek's tiny built-in dataset
nextflow run nf-core/sarek -r 3.9.0 -profile test,docker --outdir sarek_test

# Full docs: https://nf-co.re/sarek/3.9.0/
`,

    "sarek-samplesheet": (s) =>
      `# Create ${s.sarekSamplesheet} — CSV, one row per FASTQ pair:
# patient,sample,lane,fastq_1,fastq_2
#
# Example (demo FASTQs in this repo):
# patient,sample,lane,fastq_1,fastq_2
# case1,case1,L001,test_case/fastq/case1_R1.fastq.gz,test_case/fastq/case1_R2.fastq.gz
# control1,control1,L001,test_case/fastq/control1_R1.fastq.gz,test_case/fastq/control1_R2.fastq.gz
#
# See docs/assets/scripts/sarek_samplesheet.example.csv and SAREK_ALTERNATIVE.md
`,

    "sarek-run": (s) =>
      `# Run from repo root (or any directory with your samplesheet)
nextflow run nf-core/sarek -r 3.9.0 \\
  -profile ${s.sarekProfile} \\
  --input ${s.sarekSamplesheet} \\
  --outdir ${s.sarekOutDir} \\
  --genome ${s.sarekGenome} \\
  --tools ${s.sarekTools}

# Then use stages 05–07 below with the per-sample VCF path from sarek output.
# Typical VCF (adjust to your --tools and sarek version):
#   ${s.sarekOutDir}/variant_calling/haplotypecaller/${s.sampleId}/${s.sampleId}.haplotypecaller.vcf.gz
`,
  };

  function scriptContent(stage, s) {
    const raw = scriptBodies[stage.file] || "";
    if (stage.personalize === "config") {
      return personalizeConfig(raw, s);
    }
    return raw;
  }

  function appendHelpLine(parent, label, text) {
    const p = document.createElement("p");
    const strong = document.createElement("span");
    strong.className = "help-label";
    strong.textContent = label + ": ";
    p.appendChild(strong);
    p.appendChild(document.createTextNode(text));
    parent.appendChild(p);
  }

  function buildHelpBlock(meta) {
    const block = document.createElement("div");
    block.className = "help-block";
    if (meta.kind && KIND_LABELS[meta.kind]) {
      appendHelpLine(block, "Kind", KIND_LABELS[meta.kind]);
    }
    if (meta.bundled) appendHelpLine(block, "Demo default", meta.bundled);
    if (meta.what) appendHelpLine(block, "What", meta.what);
    if (meta.where) appendHelpLine(block, "Real data — where/how", meta.where);
    if (meta.example) appendHelpLine(block, "Example value", meta.example);
    if (meta.note) appendHelpLine(block, "Note", meta.note);
    return block;
  }

  function buildVarField(key) {
    const meta = VAR_META[key];
    const div = document.createElement("div");
    div.className = "field field-full";

    const label = document.createElement("label");
    const isFirst = !renderedVarKeys.has(key);
    if (isFirst) {
      label.htmlFor = "var-" + key;
    }
    label.textContent = meta.label;

    let input;
    if (meta.type === "select") {
      input = document.createElement("select");
      meta.options.forEach((opt) => {
        const o = document.createElement("option");
        o.value = opt;
        o.textContent = opt;
        input.appendChild(o);
      });
    } else {
      input = document.createElement("input");
      input.type = "text";
    }
    input.dataset.setting = key;
    if (isFirst) {
      input.id = "var-" + key;
    }
    input.value = settings[key] ?? "";

    label.appendChild(buildHelpBlock(meta));
    div.appendChild(label);
    div.appendChild(input);
    renderedVarKeys.add(key);

    if (key === "r1Fastq" || key === "r2Fastq") {
      const badge = document.createElement("span");
      badge.className = "format-badge";
      badge.id = "badge-" + key;
      div.appendChild(badge);
    }

    input.addEventListener("input", onSettingsChange);
    input.addEventListener("change", onSettingsChange);
    return div;
  }

  function groupVars(varKeys) {
    const groups = {};
    varKeys.forEach((key) => {
      const g = VAR_META[key].group;
      if (!groups[g]) groups[g] = [];
      groups[g].push(key);
    });
    return groups;
  }

  function renderVarGroups(container, varKeys) {
    container.innerHTML = "";
    const groups = groupVars(varKeys);
    Object.keys(groups).forEach((g) => {
      const wrap = document.createElement("div");
      wrap.className = "var-group";
      const title = document.createElement("div");
      title.className = "var-group-title";
      title.textContent = GROUP_TITLES[g] || g;
      wrap.appendChild(title);
      if (GROUP_INTROS[g]) {
        const intro = document.createElement("p");
        intro.className = "var-group-intro";
        intro.textContent = GROUP_INTROS[g];
        wrap.appendChild(intro);
      }
      const fields = document.createElement("div");
      fields.className = "var-fields";
      groups[g].forEach((key) => fields.appendChild(buildVarField(key)));
      wrap.appendChild(fields);
      container.appendChild(wrap);
    });
  }

  function updateFastqBadges() {
    ["r1Fastq", "r2Fastq"].forEach((key) => {
      const badge = document.getElementById("badge-" + key);
      if (!badge) return;
      const info = resolveFastq(settings[key]);
      badge.textContent = info.format + ": " + info.note;
    });
  }

  function renderStage(stage) {
    const el = document.createElement("article");
    el.className = "stage";
    el.id = "stage-" + stage.id;

    const header = document.createElement("div");
    header.className = "stage-header";
    const badge = document.createElement("span");
    badge.className = "stage-badge";
    badge.textContent = stage.stepLabel || stage.num;
    const title = document.createElement("h3");
    title.textContent = stage.title;
    header.appendChild(badge);
    header.appendChild(title);
    el.appendChild(header);

    const scriptRef = stage.scriptLabel || (stage.file ? `pipeline/${stage.file}` : "");
    if (scriptRef) {
      const scriptEl = document.createElement("p");
      scriptEl.className = "stage-script-ref";
      scriptEl.textContent = scriptRef;
      el.appendChild(scriptEl);
    }

    const desc = document.createElement("p");
    desc.className = "stage-desc";
    desc.textContent = stage.desc;
    el.appendChild(desc);

    if (stage.vars.length) {
      const varsWrap = document.createElement("div");
      varsWrap.className = "stage-vars";
      renderVarGroups(varsWrap, stage.vars);
      el.appendChild(varsWrap);
    }

    const runSection = document.createElement("div");
    runSection.className = "subsection";
    runSection.innerHTML = '<div class="subsection-label">How to run</div>';
    const runPre = document.createElement("pre");
    runPre.className = "run-block";
    runPre.id = "run-" + stage.id;
    runSection.appendChild(runPre);
    el.appendChild(runSection);
    runEls[stage.id] = runPre;

    if (stage.file) {
      const scriptSection = document.createElement("div");
      scriptSection.className = "subsection";
      scriptSection.innerHTML = `<div class="subsection-label">Script: pipeline/${stage.file}</div>`;
      el.appendChild(scriptSection);
      appendScriptEditor(el, stage, `pipeline/${stage.file}`);
    } else {
      const scriptSection = document.createElement("div");
      scriptSection.className = "subsection";
      scriptSection.innerHTML = '<div class="subsection-label">Commands</div>';
      el.appendChild(scriptSection);
      appendScriptEditor(el, stage, "commands");
    }

    return el;
  }

  function appendScriptEditor(parent, stage, label) {
      const toolbar = document.createElement("div");
      toolbar.className = "script-toolbar";

      const copyBtn = document.createElement("button");
      copyBtn.type = "button";
      copyBtn.className = "btn btn-small btn-secondary";
      copyBtn.textContent = "Copy";

      const dlBtn = document.createElement("button");
      dlBtn.type = "button";
      dlBtn.className = "btn btn-small btn-secondary";
      dlBtn.textContent = "Download";

      const resetBtn = document.createElement("button");
      resetBtn.type = "button";
      resetBtn.className = "btn btn-small btn-secondary";
      resetBtn.textContent = "Reset from template";

      const lockLabel = document.createElement("label");
      lockLabel.className = "lock-label";
      const lockCb = document.createElement("input");
      lockCb.type = "checkbox";
      lockCb.checked = !!locked[stage.id];

      const panel = document.createElement("div");
      panel.className = "script-panel";
      panel.appendChild(toolbar);

      const ta = document.createElement("textarea");
      ta.className = "script-textarea";
      ta.spellcheck = false;
      ta.id = "script-" + stage.id;

      copyBtn.addEventListener("click", () => copyText(ta.value, copyBtn));
      dlBtn.addEventListener("click", () => downloadFile(stage.runName, ta.value));
      resetBtn.addEventListener("click", () => {
        locked[stage.id] = false;
        delete scriptBodies["_edit_" + stage.id];
        lockCb.checked = false;
        refreshStage(stage.id);
        saveState();
      });
      lockCb.addEventListener("change", () => {
        locked[stage.id] = lockCb.checked;
        if (!lockCb.checked) {
          delete scriptBodies["_edit_" + stage.id];
          refreshStage(stage.id);
        }
        saveState();
      });
      ta.addEventListener("input", () => {
        locked[stage.id] = true;
        scriptBodies["_edit_" + stage.id] = ta.value;
        lockCb.checked = true;
        saveState();
      });

      lockLabel.appendChild(lockCb);
      lockLabel.appendChild(document.createTextNode(" Lock manual edits"));
      toolbar.appendChild(copyBtn);
      toolbar.appendChild(dlBtn);
      toolbar.appendChild(resetBtn);
      toolbar.appendChild(lockLabel);
      panel.appendChild(ta);
      parent.appendChild(panel);
      textareaEls[stage.id] = ta;
  }

  function refreshStage(id) {
    const stage = getActiveStages().find((s) => s.id === id);
    if (!stage) return;
    if (runEls[id] && RUNNERS[id]) {
      runEls[id].textContent = RUNNERS[id](settings);
    }
    if (!textareaEls[id]) return;
    if (locked[id]) {
      const saved = scriptBodies["_edit_" + id];
      if (saved !== undefined) textareaEls[id].value = saved;
      return;
    }
    if (stage.file) {
      textareaEls[id].value = scriptContent(stage, settings);
    } else if (id === "setup" || RUNNERS[id]) {
      textareaEls[id].value = typeof RUNNERS[id] === "function" ? RUNNERS[id](settings) : RUNNERS.setup();
    }
  }

  function readAllSettings() {
    document.querySelectorAll("[data-setting]").forEach((el) => {
      settings[el.dataset.setting] = el.value;
    });
    updateFastqBadges();
    saveState();
  }

  function onSettingsChange(ev) {
    const el = ev && ev.target ? ev.target : null;
    if (el && el.dataset.setting) {
      const key = el.dataset.setting;
      settings[key] = el.value;
      document.querySelectorAll('[data-setting="' + key + '"]').forEach((other) => {
        if (other !== el) other.value = el.value;
      });
    } else {
      readAllSettings();
      return;
    }
    updateFastqBadges();
    saveState();
    getActiveStages().forEach((stage) => refreshStage(stage.id));
  }

  function refreshAll() {
    getActiveStages().forEach((stage) => refreshStage(stage.id));
    updateFastqBadges();
    enhanceCodeBlocks(document.getElementById("pipeline-stages"));
  }

  async function fetchScripts() {
    const files = getActiveStages().map((s) => s.file).filter(Boolean);
    await Promise.all(
      files.map(async (file) => {
        const res = await fetch(SCRIPTS_BASE + file);
        if (res.ok) scriptBodies[file] = await res.text();
      })
    );
  }

  async function copyText(text, btn) {
    try {
      await navigator.clipboard.writeText(text);
    } catch (_) {
      const ta = document.createElement("textarea");
      ta.value = text;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
    }
    const orig = btn.textContent;
    btn.textContent = "Copied!";
    setTimeout(() => { btn.textContent = orig; }, 1200);
  }

  function enhanceCodeBlocks(root) {
    const scope = root || document;
    scope.querySelectorAll("pre.inline-cmd, pre.workspace-layout, pre.run-block").forEach((pre) => {
      if (pre.dataset.copyEnhanced) return;
      pre.dataset.copyEnhanced = "1";
      const wrap = document.createElement("div");
      wrap.className = "code-block-wrap";
      const parent = pre.parentNode;
      parent.insertBefore(wrap, pre);
      wrap.appendChild(pre);
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "btn btn-small code-copy-btn";
      btn.textContent = "Copy";
      btn.addEventListener("click", () => copyText(pre.textContent.replace(/\s+$/, ""), btn));
      wrap.appendChild(btn);
    });
  }

  function downloadFile(name, content) {
    const blob = new Blob([content], { type: "text/plain" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = name;
    a.click();
    URL.revokeObjectURL(a.href);
  }

  async function exportAll() {
    if (typeof JSZip === "undefined") {
      getActiveStages().forEach((stage) => {
        const ta = textareaEls[stage.id];
        if (ta && ta.value.trim()) downloadFile(stage.runName || stage.id + ".txt", ta.value);
      });
      return;
    }
    const zip = new JSZip();
    const folder = zip.folder("pipeline");
    getActiveStages().forEach((stage) => {
      const ta = textareaEls[stage.id];
      if (ta && ta.value.trim()) {
        folder.file(stage.runName || stage.id + ".txt", ta.value);
      }
      const run = runEls[stage.id];
      if (run && run.textContent.trim()) {
        folder.file((stage.runName || stage.id).replace(/\.(sh|py)$/, "") + "_run.txt", run.textContent);
      }
    });
    const blob = await zip.generateAsync({ type: "blob" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "variant-pipeline-scripts.zip";
    a.click();
    URL.revokeObjectURL(a.href);
  }

  function resetAll() {
    settings = { ...DEFAULTS };
    locked = {};
    document.querySelectorAll("[data-setting]").forEach((el) => {
      el.value = settings[el.dataset.setting] ?? "";
    });
    Object.keys(scriptBodies).forEach((k) => {
      if (k.startsWith("_edit_")) delete scriptBodies[k];
    });
    refreshAll();
    saveState();
  }

  const STAGE_SHORT = {
    setup: "Environment setup",
    config: "Shared configuration",
    prepare: "Prepare reference",
    align: "Align reads",
    call: "Call variants",
    annotate: "Annotate variants",
    filter: "Filter pathogenic",
    report: "HTML report",
    aggregate: "Aggregate cohort",
    fullrun: "Full cohort run",
    "sarek-setup": "Install Nextflow",
    "sarek-samplesheet": "Prepare samplesheet",
    "sarek-run": "Run nf-core/sarek",
  };

  const STAGE_NAV_SHORT = {
    setup: "Setup",
    config: "Config",
    prepare: "Reference",
    align: "Align",
    call: "Call",
    annotate: "Annotate",
    filter: "Filter",
    report: "Report",
    aggregate: "Cohort",
    fullrun: "Full run",
    "sarek-setup": "Setup",
    "sarek-samplesheet": "Sheet",
    "sarek-run": "Run",
  };

  const STAGE_NAV_DESC = {
    setup: "One-time: clone repo, conda env, verify tools",
    config: "Default paths — override for real data",
    prepare: "Index reference FASTA and tabix ClinVar",
    align: "FASTQ → sorted, deduplicated BAM",
    call: "Variant calling (bcftools)",
    annotate: "snpEff + ClinVar on VCF",
    filter: "Keep pathogenic / likely pathogenic",
    report: "Per-sample HTML clinical report",
    aggregate: "Case vs control counts across cohort",
    fullrun: "One command for the whole manifest",
    "sarek-setup": "Install Nextflow and a container runtime",
    "sarek-samplesheet": "CSV input for nf-core/sarek",
    "sarek-run": "QC, align, call, annotate in containers",
  };

  function enrichStages(stages) {
    let step = 0;
    return stages.map((stage) => {
      const navTitle = STAGE_SHORT[stage.id] || stage.title;
      const navDesc = STAGE_NAV_DESC[stage.id] || stage.title;
      const scriptLabel = stage.file
        ? `pipeline/${stage.file}`
        : stage.runName && !stage.isPython
          ? stage.runName
          : null;

      if (stage.id === "fullrun") {
        return {
          ...stage,
          stepLabel: "Quick start",
          navTitle,
          navDesc,
          scriptLabel: stage.file ? `pipeline/${stage.file}` : scriptLabel,
        };
      }

      step += 1;
      return {
        ...stage,
        step,
        stepLabel: `Step ${step}`,
        navTitle,
        navDesc,
        scriptLabel,
      };
    });
  }

  function getNavGroups() {
    const stages = getActiveStages();
    const items = [
      { href: "#overview", title: "Overview" },
      { href: "#getting-started", title: "Getting started" },
      { href: "#inputs-guide", title: "Input reference" },
    ];

    if (activePathway !== "array") {
      items.push(
        ...stages.map((s) => ({
          href: "#stage-" + s.id,
          stepLabel: s.stepLabel,
          title: s.navTitle,
          desc: s.navDesc,
          scriptLabel: s.scriptLabel,
          stageId: s.id,
        }))
      );
    }

    items.push(
      { href: "#roadmap", title: "Roadmap" },
      { href: "SAREK_ALTERNATIVE.md", title: "Sarek guide", external: true },
      { href: "DATA_TYPES_AND_WORKFLOWS.md", title: "Data types", external: true }
    );

    return [{ id: "toc", items }];
  }

  function allNavItems() {
    return getNavGroups().flatMap((g) => g.items).filter((i) => !i.external);
  }

  function buildContentsNav(container) {
    container.innerHTML = "";
    getNavGroups().forEach((group) => {
      const section = document.createElement("section");
      section.className = "contents-group";
      if (group.id === "pipeline") section.classList.add("contents-group-pipeline");

      const title = document.createElement("h3");
      title.className = "contents-group-title";
      if (group.title) {
        title.textContent = group.title;
        section.appendChild(title);
      }

      if (group.intro) {
        const intro = document.createElement("p");
        intro.className = "contents-group-intro";
        intro.textContent = group.intro;
        section.appendChild(intro);
      }

      const list = document.createElement("ol");
      list.className = "step-nav-list";
      group.items.forEach((item) => {
        const li = document.createElement("li");
        li.className = "step-nav-item";
        const a = document.createElement("a");
        a.href = item.href;
        if (item.external) {
          a.target = "_blank";
          a.rel = "noopener";
        }

        const badgeLabel = item.stepLabel || item.step;
        if (badgeLabel) {
          const badge = document.createElement("span");
          badge.className = "step-badge";
          badge.textContent = badgeLabel;
          a.appendChild(badge);
        } else {
          a.classList.add("step-nav-link-plain");
        }

        const body = document.createElement("span");
        body.className = "step-nav-body";

        const titleEl = document.createElement("span");
        titleEl.className = "step-nav-title";
        titleEl.textContent = item.title;
        body.appendChild(titleEl);

        if (item.desc) {
          const descEl = document.createElement("span");
          descEl.className = "step-nav-desc";
          descEl.textContent = item.desc;
          body.appendChild(descEl);
        }

        if (item.scriptLabel) {
          const scriptEl = document.createElement("span");
          scriptEl.className = "step-nav-script";
          scriptEl.textContent = item.scriptLabel;
          body.appendChild(scriptEl);
        }

        a.appendChild(body);
        li.appendChild(a);
        list.appendChild(li);
      });
      section.appendChild(list);
      container.appendChild(section);
    });
  }

  function initScrollSpy() {
    const links = document.querySelectorAll(".step-nav-list a");
    const sections = allNavItems().map((item) => document.querySelector(item.href)).filter(Boolean);

    function onScroll() {
      let current = sections[0];
      const offset = 120;
      sections.forEach((sec) => {
        if (sec.getBoundingClientRect().top <= offset) current = sec;
      });
      const id = current ? "#" + current.id : "";
      links.forEach((link) => {
        link.classList.toggle("active", link.getAttribute("href") === id);
      });
    }
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
  }

  function renderArrayPlaceholder() {
    const el = document.createElement("article");
    el.className = "stage pathway-placeholder";
    el.id = "stage-array-info";
    el.innerHTML = `
      <h3>Array / PLINK pathway — roadmap</h3>
      <p>Not implemented in this repo. Array data (IDAT/CEL → PLINK → imputed VCF) is documented in
      <a href="DATA_TYPES_AND_WORKFLOWS.md">DATA_TYPES_AND_WORKFLOWS.md</a> section 3.
      Population-frequency and PRS/GWAS workflows use this path instead of FASTQ sequencing.</p>
    `;
    return el;
  }

  function updatePathwayOverview(pathway) {
    document.querySelectorAll(".pathway-diagram").forEach((el) => {
      el.classList.toggle("hidden", el.id !== "pathway-diagram-" + pathway);
    });
    const cap = document.getElementById("pathway-caption");
    if (cap) {
      const text = {
        bash: "Demo: <code>cd test_case && bash run_demo.sh</code>",
        sarek: "External Nextflow pipeline. See <a href=\"SAREK_ALTERNATIVE.md\">Sarek guide</a>.",
        array: "Not implemented in this repo.",
      };
      cap.innerHTML = text[pathway] || "";
    }
    const heading = document.getElementById("stages-heading");
    if (heading) {
      heading.textContent = pathway === "array"
        ? "Array pathway (roadmap)"
        : pathway === "sarek"
          ? "Sarek + clinical stages"
          : "Pipeline stages";
    }
    const note = document.getElementById("stages-note");
    if (note) {
      note.innerHTML = pathway === "bash"
        ? "Each field shows <em>Kind</em>, <em>Demo default</em>, and how to obtain values for real data."
        : pathway === "sarek"
          ? "Sarek runs outside this repo. Point <code>SAREK_VCF</code> at sarek's per-sample annotated VCF for stages below."
          : "Array ingestion is not implemented. Select <strong>Bash pipeline</strong> or <strong>nf-core/sarek</strong>.";
    }
  }

  function rebuildStages() {
    renderedVarKeys.clear();
    const container = document.getElementById("pipeline-stages");
    container.innerHTML = "";
    textareaEls = {};
    runEls = {};

    if (activePathway === "array") {
      container.appendChild(renderArrayPlaceholder());
    } else {
      getActiveStages().forEach((stage) => container.appendChild(renderStage(stage)));
    }

    buildContentsNav(document.getElementById("contents-links"));
    initScrollSpy();
    fetchScripts().then(() => refreshAll());
  }

  function setPathway(pathway) {
    if (pathway === "array") {
      activePathway = "array";
    } else {
      activePathway = pathway === "sarek" ? "sarek" : "bash";
    }
    document.querySelectorAll(".pathway-tab").forEach((btn) => {
      const on = btn.dataset.pathway === activePathway;
      btn.classList.toggle("active", on);
      if (!btn.disabled) btn.setAttribute("aria-selected", on ? "true" : "false");
    });
    updatePathwayOverview(activePathway);
    rebuildStages();
    saveState();
  }

  function buildPage() {
    const container = document.getElementById("pipeline-stages");
    container.innerHTML = "";
    if (activePathway === "array") {
      container.appendChild(renderArrayPlaceholder());
    } else {
      getActiveStages().forEach((stage) => container.appendChild(renderStage(stage)));
    }

    document.getElementById("export-all")?.addEventListener("click", exportAll);
    document.getElementById("reset-all")?.addEventListener("click", resetAll);
    document.getElementById("load-demo")?.addEventListener("click", () => {
      setPathway("bash");
      resetAll();
    });

    document.querySelectorAll(".pathway-tab").forEach((btn) => {
      btn.addEventListener("click", () => setPathway(btn.dataset.pathway));
    });

    updatePathwayOverview(activePathway);
    buildContentsNav(document.getElementById("contents-links"));
    initScrollSpy();
  }

  async function init() {
    loadState();
    buildPage();
    await fetchScripts();
    document.querySelectorAll("[data-setting]").forEach((el) => {
      if (settings[el.dataset.setting] !== undefined) el.value = settings[el.dataset.setting];
    });
    try {
      const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
      const edits = parsed.edits || {};
      Object.keys(edits).forEach((id) => {
        if (locked[id]) scriptBodies["_edit_" + id] = edits[id];
      });
    } catch (_) {}
    refreshAll();
    enhanceCodeBlocks();
  }

  init();
})();
