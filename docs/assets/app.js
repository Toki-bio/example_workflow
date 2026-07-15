(function () {
  "use strict";

  const STORAGE_KEY = "variant-pipeline-guide-v2";
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

  const VAR_META = {
    refFasta: {
      label: "REF_FASTA",
      help: "Reference FASTA for alignment and calling — any build (GRCh37/hg19, GRCh38/hg38, T2T-CHM13, custom). ClinVar, panel BED, snpEff DB, and BCFTOOLS_PLOIDY must match the same build.",
      group: "reference",
    },
    clinvarVcf: {
      label: "CLINVAR_VCF",
      help: "ClinVar VCF for the same genome build as REF_FASTA (NCBI FTP: vcf_GRCh38, vcf_GRCh37, …). Wrong build = wrong chromosome names/coordinates.",
      group: "reference",
    },
    snpeffDb: {
      label: "SNPEFF_DB",
      help: "snpEff database matching REF_FASTA (e.g. GRCh38.…, GRCh37.…). T2T/other builds depend on what snpEff/VEP provides; skipped if not installed.",
      group: "reference",
    },
    bcftoolsPloidy: {
      label: "BCFTOOLS_PLOIDY",
      help: "bcftools call --ploidy preset matching REF_FASTA (GRCh38, GRCh37, …). See bcftools call -l for available sets.",
      group: "reference",
    },
    panelGenes: {
      label: "PANEL_GENES",
      help: "Plain-text gene list (one HGNC symbol per line). Swappable per clinical panel — see panels/README.md.",
      group: "panel",
    },
    panelBed: {
      label: "PANEL_BED",
      help: "Panel region BED — coordinates must match REF_FASTA build (shipped example is GRCh38). Re-lift or re-annotate for other builds.",
      group: "panel",
    },
    panelName: {
      label: "PANEL_NAME",
      help: "Human-readable panel label shown in HTML report titles.",
      group: "panel",
    },
    threads: {
      label: "THREADS",
      help: "CPU threads for bwa, samtools, bcftools, and fastp.",
      group: "runtime",
    },
    outDir: {
      label: "OUT_DIR",
      help: "Directory for BAMs, VCFs, reports, and JSONL outputs.",
      group: "runtime",
    },
    tmpDir: {
      label: "TMP_DIR",
      help: "Scratch directory for sorted BAMs and intermediate VCFs. Defaults to OUT_DIR/tmp.",
      group: "runtime",
    },
    sampleId: {
      label: "SAMPLE_ID",
      help: "Sample identifier used in output filenames and read-group headers.",
      group: "sample",
    },
    sampleType: {
      label: "SAMPLE_TYPE",
      help: "case or control — tags pathogenic JSONL for cohort aggregation.",
      group: "sample",
      type: "select",
      options: ["case", "control"],
    },
    r1Fastq: {
      label: "R1 FASTQ",
      help: "Forward reads: .fastq, .fastq.gz, .fq, or .fq.gz. Extension auto-resolved if omitted.",
      group: "sample",
    },
    r2Fastq: {
      label: "R2 FASTQ",
      help: "Reverse reads: same format rules as R1. Pipeline accepts plain or gzip without manual unpack.",
      group: "sample",
    },
    caller: {
      label: "CALLER",
      help: "Which hard-filtered VCF to annotate: bcftools (primary) or gatk (secondary).",
      group: "sample",
      type: "select",
      options: ["bcftools", "gatk"],
    },
    manifest: {
      label: "MANIFEST_TSV",
      help: "Tab-separated cohort file: sample_id, case|control, R1 path, R2 path (fastq or fastq.gz).",
      group: "cohort",
    },
  };

  const GROUP_TITLES = {
    reference: "Reference and annotation databases",
    panel: "Gene panel configuration",
    runtime: "Runtime directories and parallelism",
    sample: "Sample input",
    cohort: "Cohort manifest",
  };

  const STAGES = [
    {
      id: "setup",
      num: "0",
      title: "Environment setup",
      desc: "Create the conda environment once. Includes bwa, samtools, bcftools, GATK4, snpEff, fastp.",
      vars: [],
      file: null,
      runName: "setup.sh",
    },
    {
      id: "config",
      num: "00",
      title: "Shared configuration",
      desc: "All pipeline scripts source 00_config.sh. Defaults below are substituted into the script view.",
      vars: ["refFasta", "clinvarVcf", "snpeffDb", "bcftoolsPloidy", "panelGenes", "panelBed", "panelName", "threads", "outDir", "tmpDir"],
      file: "00_config.sh",
      personalize: "config",
      runName: "00_config.sh",
    },
    {
      id: "prepare",
      num: "01",
      title: "Prepare reference",
      desc: "Build BWA index, samtools .fai, GATK dict, and tabix-index ClinVar. Run once per reference.",
      vars: ["refFasta", "clinvarVcf", "snpeffDb", "bcftoolsPloidy", "threads", "outDir", "tmpDir"],
      file: "01_prepare_reference.sh",
      runName: "01_prepare_reference.sh",
    },
    {
      id: "align",
      num: "02",
      title: "Align reads",
      desc: "fastp QC → bwa mem → sort → markdup → index. Accepts .fastq or .fastq.gz (auto-resolved).",
      vars: ["sampleId", "r1Fastq", "r2Fastq", "refFasta", "threads", "outDir", "tmpDir"],
      file: "02_align.sh",
      runName: "02_align.sh",
    },
    {
      id: "call",
      num: "03",
      title: "Call variants",
      desc: "bcftools mpileup+call (primary) and GATK4 HaplotypeCaller (secondary). Both hard-filtered to PASS.",
      vars: ["sampleId", "refFasta", "bcftoolsPloidy", "threads", "outDir", "tmpDir"],
      file: "03_call_variants.sh",
      runName: "03_call_variants.sh",
    },
    {
      id: "annotate",
      num: "04",
      title: "Annotate variants",
      desc: "snpEff (if installed) + ClinVar via bcftools annotate. Optional VEP cross-check.",
      vars: ["sampleId", "caller", "clinvarVcf", "snpeffDb", "refFasta", "outDir", "tmpDir"],
      file: "04_annotate.sh",
      runName: "04_annotate.sh",
    },
    {
      id: "filter",
      num: "05",
      title: "Filter pathogenic calls",
      desc: "Extract ClinVar Pathogenic / Likely pathogenic variants to per-sample JSONL.",
      vars: ["sampleId", "sampleType", "caller", "outDir"],
      file: "05_filter_pathogenic.py",
      runName: "05_filter_pathogenic.py",
      isPython: true,
    },
    {
      id: "report",
      num: "07",
      title: "Generate HTML report",
      desc: "Interactive clinical report with panel highlights and ClinVar significance.",
      vars: ["sampleId", "caller", "panelGenes", "panelName", "outDir"],
      file: "07_generate_report.py",
      runName: "07_generate_report.py",
      isPython: true,
    },
    {
      id: "aggregate",
      num: "06",
      title: "Aggregate cohort",
      desc: "After all samples complete stage 05: case vs control counts per pathogenic variant.",
      vars: ["outDir"],
      file: "06_aggregate_case_control.py",
      runName: "06_aggregate_case_control.py",
      isPython: true,
    },
    {
      id: "fullrun",
      num: "∞",
      title: "Full cohort run",
      desc: "run_pipeline.sh executes stages 01–07 for every manifest row, then aggregates.",
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

  function exportsBlock(s) {
    return `export REF_FASTA="${s.refFasta}"
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
      `conda env create -f envs/environment.yml\nconda activate variant-pipeline\n\n# Verify tools\nbwa && samtools && bcftools && python3 --version`,

    config: (s) => `${exportsBlock(s)}\n\n# Config is sourced automatically by each pipeline/NN_*.sh script`,

    prepare: (s) => `${exportsBlock(s)}\n\npipeline/01_prepare_reference.sh`,

    align: (s) => {
      const r1 = resolveFastq(s.r1Fastq);
      const r2 = resolveFastq(s.r2Fastq);
      return `${exportsBlock(s)}\n\n# R1: ${r1.note}\n# R2: ${r2.note}\npipeline/02_align.sh ${s.sampleId} ${s.r1Fastq} ${s.r2Fastq}`;
    },

    call: (s) => `${exportsBlock(s)}\n\npipeline/03_call_variants.sh ${s.sampleId}`,

    annotate: (s) => `${exportsBlock(s)}\n\npipeline/04_annotate.sh ${s.sampleId} ${s.caller}`,

    filter: (s) =>
      `python3 pipeline/05_filter_pathogenic.py \\\n  "${s.outDir}/${s.sampleId}.${s.caller}.annotated.vcf.gz" \\\n  "${s.sampleId}" \\\n  "${s.sampleType}" \\\n  "${s.outDir}/${s.sampleId}.${s.sampleType}.pathogenic.jsonl"`,

    report: (s) =>
      `python3 pipeline/07_generate_report.py \\\n  "${s.outDir}/${s.sampleId}.${s.caller}.annotated.vcf.gz" \\\n  "${s.sampleId}" \\\n  "${s.panelGenes}" \\\n  "${s.outDir}/${s.sampleId}.report.html" \\\n  "${s.panelName}"`,

    aggregate: (s) =>
      `python3 pipeline/06_aggregate_case_control.py \\\n  "${s.outDir}/*.pathogenic.jsonl" \\\n  "${s.outDir}/aggregated_pathogenic_variants.json"`,

    fullrun: (s) => `${exportsBlock(s)}\n\n# Manifest: sample_id  case|control  R1  R2  (fastq or fastq.gz)\npipeline/run_pipeline.sh ${s.manifest}`,
  };

  function scriptContent(stage, s) {
    const raw = scriptBodies[stage.file] || "";
    if (stage.personalize === "config") {
      return personalizeConfig(raw, s);
    }
    return raw;
  }

  function buildVarField(key) {
    const meta = VAR_META[key];
    const div = document.createElement("div");
    div.className = "field" + (["manifest", "refFasta", "r1Fastq", "r2Fastq", "panelGenes"].includes(key) ? " field-full" : "");

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

    const help = document.createElement("span");
    help.className = "help";
    help.textContent = meta.help;

    label.appendChild(help);
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

  const NAV_ITEMS = [
    { href: "#overview", label: "Overview" },
    ...STAGES.map((s) => ({ href: "#stage-" + s.id, label: s.num + " " + s.title })),
    { href: "#roadmap", label: "Roadmap" },
  ];

  function buildNavLinks(container) {
    container.innerHTML = "";
    NAV_ITEMS.forEach((item) => {
      const a = document.createElement("a");
      a.href = item.href;
      a.textContent = item.label;
      container.appendChild(a);
    });
  }

  function initScrollSpy() {
    const links = document.querySelectorAll(".site-nav .steps a, .contents-links a");
    const sections = NAV_ITEMS.map((item) => document.querySelector(item.href)).filter(Boolean);

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

    buildNavLinks(document.getElementById("nav-steps"));
    buildNavLinks(document.getElementById("contents-links"));
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
