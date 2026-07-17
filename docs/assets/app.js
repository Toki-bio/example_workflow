(function () {
  "use strict";

  const STORAGE_KEY = "variant-pipeline-guide-v3";
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
      bundled: "Not installed by default — conda gives snpEff the program only, not annotation DBs",
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
      bundled: "bcftools (primary); gatk also always produced in stage 03",
      what: "Which hard-filtered VCF from stage 03 to annotate — both callers always run.",
      where: "bcftools = fast primary. gatk = GATK4 cross-check.",
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
  };

  const STAGES = [
    {
      id: "setup",
      num: "0",
      title: "Environment setup",
      desc: "Once per machine: clone the repo, create the conda env, activate it, verify tools. Do not run bare 'bwa' / 'samtools' — that dumps usage text. Use pipeline/verify_tools.sh.",
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
      desc: "Build BWA index, samtools .fai, GATK dict, tabix ClinVar. Safe to re-run — skips steps already done. Run once per REF_FASTA.",
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
      desc: "Requires stage 02 BAM. bcftools mpileup+call (primary) and GATK4 HaplotypeCaller (secondary). Both hard-filtered to PASS.",
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
      desc: "One command: prepares reference, then for each manifest row runs align→call→annotate→filter→report, then aggregates. Prefer this over copying stages 01–07 by hand. Easiest path: cd test_case && ./run_demo.sh",
      vars: ["manifest", "refFasta", "clinvarVcf", "panelGenes", "panelBed", "panelName", "threads", "outDir", "tmpDir"],
      file: "run_pipeline.sh",
      runName: "run_pipeline.sh",
    },
  ];

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
      JSON.stringify({ settings, locked, edits })
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

# Verify tools are on PATH — do NOT run bare "bwa" / "samtools" (that only prints usage help)
bash pipeline/verify_tools.sh

# Quick path after setup: run the built-in demo (no extra downloads)
#   cd test_case && ./run_demo.sh && python3 check_demo.py results
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
  "${s.outDir}/${s.sampleId}.${s.caller}.annotated.vcf.gz" \\
  "${s.sampleId}" \\
  "${s.sampleType}" \\
  "${s.outDir}/${s.sampleId}.${s.sampleType}.pathogenic.jsonl"
`,

    report: (s) => `${cwdPreamble()}
python3 pipeline/07_generate_report.py \\
  "${s.outDir}/${s.sampleId}.${s.caller}.annotated.vcf.gz" \\
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
# ./run_demo.sh
# python3 check_demo.py results

# --- Or full cohort with your settings ---
# Manifest columns (tab-separated, no header):
#   sample_id   case|control   R1.fastq[.gz]   R2.fastq[.gz]
# Relative FASTQ paths are resolved from the manifest's directory.
bash pipeline/run_pipeline.sh ${s.manifest}
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
    header.innerHTML = `<span class="stage-num">${stage.num}</span><h3>${stage.title}</h3>`;
    el.appendChild(header);

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
    const stage = STAGES.find((s) => s.id === id);
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
    } else if (id === "setup") {
      textareaEls[id].value = RUNNERS.setup();
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
    STAGES.forEach((stage) => refreshStage(stage.id));
  }

  function refreshAll() {
    STAGES.forEach((stage) => refreshStage(stage.id));
    updateFastqBadges();
  }

  async function fetchScripts() {
    const files = STAGES.map((s) => s.file).filter(Boolean);
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
      STAGES.forEach((stage) => {
        const ta = textareaEls[stage.id];
        if (ta && ta.value.trim()) downloadFile(stage.runName || stage.id + ".txt", ta.value);
      });
      return;
    }
    const zip = new JSZip();
    const folder = zip.folder("pipeline");
    STAGES.forEach((stage) => {
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
  };

  const NAV_GROUPS = [
    {
      id: "guide",
      title: "Guide",
      items: [
        { href: "#overview", label: "Overview" },
        { href: "#getting-started", label: "Getting started" },
        { href: "#inputs-guide", label: "Input reference" },
      ],
    },
    {
      id: "pipeline",
      title: "Pipeline",
      items: STAGES.map((s) => ({
        href: "#stage-" + s.id,
        label: s.num,
        title: STAGE_SHORT[s.id] || s.title,
        stageId: s.id,
      })),
    },
    {
      id: "more",
      title: "More",
      items: [{ href: "#roadmap", label: "Roadmap" }],
    },
  ];

  function allNavItems() {
    return NAV_GROUPS.flatMap((g) => g.items);
  }

  function buildTopNav(container) {
    container.innerHTML = "";
    NAV_GROUPS.forEach((group) => {
      const wrap = document.createElement("div");
      wrap.className = "nav-group" + (group.id === "pipeline" ? " nav-group-pipeline" : "");
      const label = document.createElement("span");
      label.className = "nav-group-label";
      label.textContent = group.title;
      wrap.appendChild(label);
      const links = document.createElement("div");
      links.className = "nav-group-links";
      group.items.forEach((item) => {
        const a = document.createElement("a");
        a.href = item.href;
        a.textContent = item.stageId
          ? item.label + " " + (STAGE_NAV_SHORT[item.stageId] || item.title)
          : item.label;
        links.appendChild(a);
      });
      wrap.appendChild(links);
      container.appendChild(wrap);
    });
  }

  function buildContentsNav(container) {
    container.innerHTML = "";
    NAV_GROUPS.forEach((group) => {
      const section = document.createElement("div");
      section.className = "contents-group" + (group.id === "pipeline" ? " contents-group-stages" : "");
      const title = document.createElement("div");
      title.className = "contents-group-title";
      title.textContent = group.title;
      section.appendChild(title);

      if (group.id === "pipeline") {
        const list = document.createElement("ol");
        list.className = "contents-list contents-list-stages";
        group.items.forEach((item) => {
          const li = document.createElement("li");
          const a = document.createElement("a");
          a.href = item.href;
          const num = document.createElement("span");
          num.className = "stage-num";
          num.textContent = item.label;
          a.appendChild(num);
          a.appendChild(document.createTextNode(item.title));
          li.appendChild(a);
          list.appendChild(li);
        });
        section.appendChild(list);
      } else {
        const list = document.createElement("ul");
        list.className = "contents-list";
        group.items.forEach((item) => {
          const li = document.createElement("li");
          const a = document.createElement("a");
          a.href = item.href;
          a.textContent = item.label;
          li.appendChild(a);
          list.appendChild(li);
        });
        section.appendChild(list);
      }
      container.appendChild(section);
    });
  }

  function initScrollSpy() {
    const links = document.querySelectorAll(".nav-group-links a, .contents-list a");
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

  function buildPage() {
    renderedVarKeys.clear();
    const container = document.getElementById("pipeline-stages");
    STAGES.forEach((stage) => container.appendChild(renderStage(stage)));

    document.getElementById("export-all")?.addEventListener("click", exportAll);
    document.getElementById("reset-all")?.addEventListener("click", resetAll);
    document.getElementById("load-demo")?.addEventListener("click", resetAll);

    buildTopNav(document.getElementById("nav-steps"));
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
    if (typeof mermaid !== "undefined") {
      mermaid.initialize({ startOnLoad: true, theme: "neutral", securityLevel: "loose" });
    }
  }

  init();
})();
