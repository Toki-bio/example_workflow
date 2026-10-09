#!/usr/bin/env python3
"""Describe a reference bundle: write versions.json, SHA256SUMS and README.md next to the data.

    make_versions.py <bundle_dir> [--verify-nirvana-md5]

Every version is read from the FILE ITSELF (a header line, a JSON field, a manifest written by the
downloader), never from a README or a directory name: a README once said a ClinVar file was the
2024-09-02 release when its header said 2025-07-15. If a value cannot be read, it is recorded as
"UNKNOWN" and the script exits non-zero so the run that depends on it can refuse to start.

Bundle layout (what the triage stage expects):
  clinvar/{clinvar.vcf.gz,.tbi,variant_summary.txt.gz,submission_summary.txt.gz}
  hpo/{hp.obo,genes_to_phenotype.txt,phenotype.hpoa}
  panelapp/{panelapp_uk.json,panelapp_au.json}
  gene_disease/{clingen_gene_validity.csv,G2P_DD_panel.csv}
  gnomad/gnomad_v4.1_constraint.tsv
  nirvana/{data/,config/}       (Illumina Connected Annotations data, config + download summary)
"""
import gzip
import hashlib
import json
import os
import re
import sys
import time

UNKNOWN = "UNKNOWN"
problems = []


def opener(path):
    return gzip.open(path, "rt", encoding="utf-8", errors="replace") if path.endswith(".gz") else open(path, encoding="utf-8", errors="replace")


def head(path, n=60):
    out = []
    with opener(path) as f:
        for _, line in zip(range(n), f):
            out.append(line.rstrip("\n"))
    return out


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 24), b""):
            h.update(chunk)
    return h.hexdigest()


def find(lines, pattern, group=1):
    for ln in lines:
        m = re.search(pattern, ln)
        if m:
            return m.group(group).strip()
    return None


def need(value, what):
    if not value:
        problems.append(what)
        return UNKNOWN
    return value


def human(n):
    for u in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or u == "TB":
            return f"{n:.1f} {u}" if u != "B" else f"{n} B"
        n /= 1024


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    B = os.path.abspath(sys.argv[1])
    verify_md5 = "--verify-nirvana-md5" in sys.argv
    P = lambda *a: os.path.join(B, *a)  # noqa: E731
    v = {"bundle": os.path.basename(B), "generated": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "sources": {}}
    S = v["sources"]

    # ---- ClinVar
    h = head(P("clinvar", "clinvar.vcf.gz"), 40)
    S["clinvar_vcf"] = {"file": "clinvar/clinvar.vcf.gz",
                        "release_fileDate": need(find(h, r"##fileDate=(\S+)"), "ClinVar fileDate"),
                        "reference": need(find(h, r"##reference=(\S+)"), "ClinVar reference"),
                        "origin": "https://ftp.ncbi.nlm.nih.gov/pub/clinvar/vcf_GRCh38/clinvar.vcf.gz",
                        "provides": "CLNSIG, CLNSIGCONF (per-class submission counts), CLNREVSTAT, CLNDN, CLNVID"}
    for name, what in (("variant_summary.txt.gz", "per-variant summary, one row per allele and assembly"),
                       ("submission_summary.txt.gz", "every current submission (SCV): classification, date, submitter, evidence")):
        p = P("clinvar", name)
        S["clinvar_" + name.split(".")[0]] = {"file": "clinvar/" + name, "downloaded_mtime": time.strftime("%Y-%m-%d", time.localtime(os.path.getmtime(p))),
                                              "origin": "https://ftp.ncbi.nlm.nih.gov/pub/clinvar/tab_delimited/" + name, "provides": what,
                                              "note": "tab-delimited tables carry no release date in the file; matched by download date to the VCF above"}
    # ---- HPO
    h = head(P("hpo", "hp.obo"), 10)
    S["hpo_ontology"] = {"file": "hpo/hp.obo", "release": need(find(h, r"data-version: (\S+)"), "hp.obo data-version"),
                         "origin": "https://purl.obolibrary.org/obo/hp.obo"}
    h = head(P("hpo", "phenotype.hpoa"), 8)
    S["hpo_annotations"] = {"file": "hpo/phenotype.hpoa", "annotation_version": need(find(h, r"#version: (\S+)"), "phenotype.hpoa version"),
                            "hpo_version_used": find(h, r"#hpo-version: (\S+)") or UNKNOWN,
                            "origin": "https://purl.obolibrary.org/obo/hp/hpoa/phenotype.hpoa"}
    S["hpo_genes_to_phenotype"] = {"file": "hpo/genes_to_phenotype.txt", "origin": "https://purl.obolibrary.org/obo/hp/hpoa/genes_to_phenotype.txt",
                                   "note": "no version inside the file; same HPO build as phenotype.hpoa above if downloaded the same day",
                                   "downloaded_mtime": time.strftime("%Y-%m-%d", time.localtime(os.path.getmtime(P("hpo", "genes_to_phenotype.txt"))))}
    # ---- PanelApp
    for tag, label in (("uk", "PanelApp UK (Genomics England)"), ("au", "PanelApp Australia")):
        d = json.load(open(P("panelapp", f"panelapp_{tag}.json"), encoding="utf-8"))
        S["panelapp_" + tag] = {"file": f"panelapp/panelapp_{tag}.json", "source": label, "fetched": need(d.get("fetched"), f"PanelApp {tag} fetched date"),
                                "api": d.get("source"), "n_panels": len(d.get("panels", [])),
                                "panel_versions": {str(p.get("id")): f"{p.get('name')} v{p.get('version')}" for p in d.get("panels", [])}}
    # ---- gene-disease tables
    h = head(P("gene_disease", "clingen_gene_validity.csv"), 4)
    S["clingen_gene_validity"] = {"file": "gene_disease/clingen_gene_validity.csv", "file_created": need(find(h, r"FILE CREATED: (\S+?)[\",]"), "ClinGen FILE CREATED"),
                                  "origin": "https://search.clinicalgenome.org/kb/gene-validity/download"}
    S["gene2phenotype_dd"] = {"file": "gene_disease/G2P_DD_panel.csv", "origin": "https://www.ebi.ac.uk/gene2phenotype/api/panel/DD/download/",
                              "downloaded_mtime": time.strftime("%Y-%m-%d", time.localtime(os.path.getmtime(P("gene_disease", "G2P_DD_panel.csv")))),
                              "note": "Developmental Disorders panel only"}
    S["gnomad_constraint"] = {"file": "gnomad/gnomad_v4.1_constraint.tsv", "release": "v4.1 (from the file name; no version field inside)",
                              "origin": "https://storage.googleapis.com/gcp-public-data--gnomad/release/4.1/constraint/gnomad.v4.1.constraint_metrics.tsv"}
    # ---- Nirvana
    summ = P("nirvana", "config", "download_summary.json")
    nv = {"data_dir": "nirvana/data", "files": []}
    if os.path.exists(summ):
        d = json.load(open(summ, encoding="utf-8"))
        nv["assembly"] = d.get("assembly")
        nv["downloader_run"] = d.get("timestampEnd")
        nv["download_errors"] = d.get("errors")
        for f in d.get("files", []):
            nv["files"].append({k: f.get(k) for k in ("fileName", "dataSource", "annotationType", "version", "localSize", "md5Hash", "status")})
        if d.get("errors"):
            problems.append(f"Nirvana download reported errors: {d['errors']}")
    else:
        problems.append("nirvana download_summary.json missing")
    if verify_md5:
        bad = []
        for f in nv["files"]:
            cand = [os.path.join(B, "nirvana", "data", sub, f["fileName"]) for sub in ("SupplementaryAnnotation/GRCh38", "Cache", "References", "")]
            path = next((c for c in cand if os.path.exists(c)), None)
            f["md5_verified"] = (md5(path) == f["md5Hash"]) if path else False
            if not f["md5_verified"]:
                bad.append(f["fileName"])
        if bad:
            problems.append("Nirvana md5 mismatch: " + ", ".join(bad))
    S["nirvana_data"] = nv
    S["nirvana_program"] = {"note": "Illumina Connected Annotations 3.27.0 (DRAGEN 4.5.4: /opt/dragen/4.5.4/share/nirvana). "
                                    "Run with -c <data>/Cache (a DIRECTORY), --sd <data>/SupplementaryAnnotation/GRCh38, "
                                    "-r <data>/References/Homo_sapiens.GRCh38.Nirvana.dat, --versions-config <config>/trim_config.json, "
                                    "-l <DRAGEN credentials.json>."}
    v["problems"] = problems
    json.dump(v, open(P("versions.json"), "w", encoding="utf-8"), indent=2, ensure_ascii=False)

    # ---- SHA256SUMS (everything except the large Nirvana data; those carry the downloader's md5)
    with open(P("SHA256SUMS"), "w", encoding="utf-8") as out:
        for root, _, files in os.walk(B):
            if os.path.relpath(root, B).startswith(os.path.join("nirvana", "data")):
                continue
            for fn in sorted(files):
                if fn in ("SHA256SUMS", "versions.json", "README.md"):
                    continue
                path = os.path.join(root, fn)
                out.write(f"{sha256(path)}  {os.path.relpath(path, B)}\n")

    # ---- README.md
    L = [f"# Reference bundle {v['bundle']}", "",
         "Frozen lookup data for the phenotype-driven exome triage (pipeline stage 08) and for Nirvana annotation. "
         "Do not edit in place: a refresh creates a new dated folder and `current` is re-pointed.", "",
         "Every version below was read from the files themselves by `pipeline/refs/make_versions.py` and is stored "
         "in `versions.json`. A triage report must quote these, not this README.", "",
         "## Contents", "", "| Item | File | Version / date (from the file) | Provides |", "|---|---|---|---|"]
    for name, e in S.items():
        if name.startswith("nirvana"):
            continue
        ver = e.get("release_fileDate") or e.get("release") or e.get("annotation_version") or e.get("file_created") or e.get("fetched") or e.get("downloaded_mtime") or ""
        extra = e.get("provides") or e.get("note") or (f"{e.get('n_panels')} panels" if "n_panels" in e else "")
        L.append(f"| {name} | `{e.get('file', '')}` | {ver} | {extra} |")
    L += ["", "### Nirvana (Illumina Connected Annotations) data", "",
          f"Assembly {nv.get('assembly')}, downloaded {nv.get('downloader_run')}. Free tier fetched with the DRAGEN server's own licence key; "
          "the data is Illumina's and stays on the server (never commit it, do not redistribute).", "",
          "| Source | Version | Size | Status | md5 (downloader) |", "|---|---|---|---|---|"]
    for f in sorted(nv["files"], key=lambda x: x["fileName"]):
        L.append(f"| {f['fileName']} | {f['version']} | {human(f['localSize'] or 0)} | {f['status']}{' / md5 ok' if f.get('md5_verified') else ''} | `{f['md5Hash']}` |")
    L += ["", "Not included: SpliceAI, PrimateAI-3D, OMIM, COSMIC (licensed tier; not in the downloadable config), "
          "structural-variant, fusion, mitochondrial and legacy sources.", "",
          "## How it is used", "",
          "```bash", "B=/staging/refs/exome_triage/current",
          "# annotate a whole VCF offline (about 4 min per exome)",
          "N=/opt/dragen/4.5.4/share/nirvana",
          "$N/Nirvana -i sample.vcf.gz -c $B/nirvana/data/Cache --sd $B/nirvana/data/SupplementaryAnnotation/GRCh38 \\",
          "  -r $B/nirvana/data/References/Homo_sapiens.GRCh38.Nirvana.dat -o sample_nv \\",
          "  -l /opt/dragen/4.4.4/share/nirvana/credentials.json --versions-config $B/nirvana/config/trim_config.json",
          "# triage (gene set from PanelApp + HPO, ClinVar tiers, dossiers)",
          "TRIAGE_HPO='HP:0001250' TRIAGE_KEYWORDS='epilep' TRIAGE_NIRVANA=sample_nv.json.gz \\",
          "  TRIAGE_CLINVAR=$B/clinvar/clinvar.vcf.gz bash pipeline/08_triage.sh SAMPLE sample.vcf.gz out/",
          "```", "",
          "## Refresh and verification", "",
          "* ClinVar monthly, everything else quarterly. Download into a NEW dated folder, run `make_versions.py`, "
          "compare `versions.json` of the two bundles, re-point `current`. Re-run past cases when the ClinVar date, "
          "a PanelApp panel version or the HPO release changed and diff the tiers.",
          "* `sha256sum -c SHA256SUMS` (small files) and `make_versions.py <dir> --verify-nirvana-md5` (Nirvana data).",
          "* VEP (Ensembl VEP 115) conda environment: `/staging/tmp/vep_env` (no cache yet); conda environments cannot be moved, so it is "
          "described here, not stored in the bundle.", "",
          "## Known limits", "",
          "* ClinVar tab-delimited tables carry no release date inside the file; pair them with the VCF of the same download.",
          "* Gene2Phenotype is the Developmental Disorders panel only. gnomAD constraint is the gene-level table, not variant frequencies "
          "(those come from the Nirvana gnomAD 4.1 data).",
          "* PanelApp is a snapshot: panel contents change weekly; the per-panel versions are in `versions.json`.", ""]
    if problems:
        L += ["## PROBLEMS (resolve before using this bundle)", ""] + [f"* {p}" for p in problems] + [""]
    open(P("README.md"), "w", encoding="utf-8").write("\n".join(L))
    print(f"wrote versions.json, SHA256SUMS, README.md in {B}; problems: {len(problems)}")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
