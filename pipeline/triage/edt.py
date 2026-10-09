#!/usr/bin/env python3
"""edt.py - exome diagnostic triage: phenotype-driven, ClinVar-label-blind candidate search
plus per-variant evidence dossiers built from ClinVar submissions (SCVs), gnomAD, predictors,
literature and gene-disease curation.

Pure standard library. Public, keyless APIs only. Run with:  python -X utf8 edt.py <command> ...

Commands (run in this order; every step writes into --out DIR and appends to DIR/manifest.json):
  genes    --hpo HP:x [HP:y ...] --keywords kw1 [kw2 ...] [--amber]
           -> genes.tsv  (union of PanelApp UK + PanelApp Australia panels matching keywords,
                          green (+amber with --amber), plus HPO-annotated genes of each HPO term)
  regions  -> regions.tsv  (gene spans from Ensembl REST; pad 5 kb)
  scan     --vcf FILE.vcf[.gz] [--sample NAME] [--min-qual 20]
           -> calls.tsv   (every non-ref genotype inside phenotype-gene spans; nothing else dropped)
           -> allcalls.keys (all non-ref calls genome-wide, for the ClinVar tier)
  clinvar  [--clinvar-vcf URL_or_path]
           -> clinvar_hits.tsv (genome-wide match of ALL sample calls to the ClinVar VCF;
                                records CLNSIG, CLNSIGCONF, CLNREVSTAT, fileDate)
  annotate [--workers 4] [--all-clinvar]
           -> annotated.tsv (Ensembl VEP REST on calls.tsv + ClinVar hits that are P/LP or Conflicting
                             with a P/LP submission (--all-clinvar: every hit). Parallel, cached in
                             annotate_cache.jsonl (re-running resumes), failed chunks are split and
                             retried; unannotatable variants are listed in annotate_failed.tsv)
  rank     [--af-dominant 0.001] [--af-recessive 0.01] [--top 30]
           -> tiers.tsv (union of independent tiers, phenotype genes), candidates.tsv (top N),
              outside_phenotype.tsv (ClinVar-tier variants in genes outside the phenotype set; reported
              separately, never dropped)
  dossier  [--top 15] [--variants chr:pos:ref:alt ...]
           -> dossier/<variant>.md and dossier.md (all SCVs, gnomAD v4, PanelApp/G2P, literature)
  control  -> runs the built-in positive controls through annotate+rank logic and fails loudly

Design rules enforced in code (see SKILL.md):
  * A ClinVar label can ADD a variant to review, never remove one.
  * Tiers are computed independently and UNIONED (never a cascade of filters).
  * Variants VEP cannot annotate are kept and flagged, not dropped.
  * Every external resource version / query date goes into manifest.json.
"""
import argparse, concurrent.futures, csv, gzip, io, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime

UA = {"User-Agent": "exome-diagnostic-triage/1.0 (skill)"}
NCBI_TOOL = "exome-diagnostic-triage"
PANELAPP = {"UK": "https://panelapp.genomicsengland.co.uk/api/v1",
            "AU": "https://panelapp-aus.org/api/v1"}
ENSEMBL = "https://rest.ensembl.org"
CLINVAR_VCF = "https://ftp.ncbi.nlm.nih.gov/pub/clinvar/vcf_GRCh38/clinvar.vcf.gz"
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
GNOMAD = "https://gnomad.broadinstitute.org/api"
PATHO = {"pathogenic", "likely_pathogenic", "pathogenic/likely_pathogenic",
         "pathogenic_low_penetrance", "likely_pathogenic_low_penetrance"}
PROTEIN_ALTERING = {
    "transcript_ablation", "splice_acceptor_variant", "splice_donor_variant", "stop_gained",
    "frameshift_variant", "stop_lost", "start_lost", "transcript_amplification",
    "inframe_insertion", "inframe_deletion", "missense_variant", "protein_altering_variant",
    "splice_region_variant", "splice_donor_5th_base_variant", "splice_donor_region_variant",
    "splice_polypyrimidine_tract_variant", "incomplete_terminal_codon_variant",
    "coding_sequence_variant", "feature_elongation", "feature_truncation"}

# Positive controls (GRCh38). Unrelated to any specific case; extend as needed.
CONTROLS = [
    # recurrent pathogenic de novo variant whose ClinVar aggregate is "Conflicting" (Ragoussis 2022)
    {"id": "6:3154458:G:A", "gene": "TUBB2A", "why": "Conflicting aggregate, P/LP majority",
     "must": "T1b"},
    {"id": "2:166056471:A:G", "gene": "SCN1A", "why": "ClinVar Pathogenic missense", "must": "T1a"},
]


# ----------------------------------------------------------------------------------------- utils
def http(url, data=None, headers=None, tries=5, timeout=120, raw=False):
    # panelapp-aus.org returns 403 for custom User-Agents AND for urllib's default "Python-urllib/x";
    # it accepts curl's (checked 2026-10-08)
    h = {"User-Agent": "curl/8.4.0"} if "panelapp-aus.org" in url else dict(UA)
    if headers:
        h.update(headers)
    body = None
    if data is not None:
        body = json.dumps(data).encode() if not isinstance(data, (bytes, str)) else (
            data.encode() if isinstance(data, str) else data)
        h.setdefault("Content-Type", "application/json")
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, data=body, headers=h)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                b = r.read()
                return b if raw else json.loads(b.decode("utf-8"))
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (400, 404):
                raise
            wait = int(e.headers.get("Retry-After", 0) or 0) or 2 ** i
            time.sleep(min(wait, 60))
        except Exception as e:  # network hiccup
            last = e
            time.sleep(2 ** i)
    raise RuntimeError(f"HTTP failed after {tries} tries: {url} :: {last}")


def manifest(out, key, value):
    p = os.path.join(out, "manifest.json")
    m = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}
    m[key] = value
    json.dump(m, open(p, "w", encoding="utf-8"), indent=2, ensure_ascii=False)


def read_tsv(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def write_tsv(path, rows, cols):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, delimiter="\t", extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def norm_chrom(c):
    c = c[3:] if c.lower().startswith("chr") else c
    return "MT" if c in ("M", "m") else c


def key(c, p, r, a):
    return f"{norm_chrom(c)}:{int(p)}:{r}:{a}"


def open_text(path):
    if path.startswith("http"):
        resp = urllib.request.urlopen(urllib.request.Request(path, headers=UA), timeout=300)
        return io.TextIOWrapper(gzip.GzipFile(fileobj=resp), encoding="utf-8", errors="replace")
    if path.endswith(".gz"):
        return gzip.open(path, "rt", encoding="utf-8", errors="replace")
    return open(path, encoding="utf-8", errors="replace")


# ----------------------------------------------------------------------------------------- genes
def panelapp_panels(site):
    url, out = PANELAPP[site] + "/panels/?page=1", []
    while url:
        d = http(url)
        out += d["results"]
        url = d.get("next")
    return out


def cmd_genes(a):
    os.makedirs(a.out, exist_ok=True)
    genes, panels_used = {}, []
    kws = [k.lower() for k in (a.keywords or [])]
    levels = {"3"} | ({"2"} if a.amber else set())
    for site in PANELAPP:
        try:
            panels = panelapp_panels(site)
        except Exception as e:
            print(f"WARNING PanelApp {site} unavailable: {e}", file=sys.stderr)
            continue
        for p in panels:
            text = " ".join([p.get("name", ""), p.get("disease_group", "") or "",
                             p.get("disease_sub_group", "") or "",
                             " ".join(p.get("relevant_disorders", []) or [])]).lower()
            if not any(k in text for k in kws):
                continue
            if any(x.lower() in p.get("name", "").lower() for x in (a.exclude or [])):
                continue
            d = http(f"{PANELAPP[site]}/panels/{p['id']}/")
            panels_used.append(f"PanelApp{site}:{p['id']}:{d.get('name')}:v{d.get('version')}")
            for g in d.get("genes", []):
                if str(g.get("confidence_level")) not in levels:
                    continue
                sym = g["gene_data"]["gene_symbol"]
                e = genes.setdefault(sym, {"gene": sym, "sources": set(), "moi": set()})
                e["sources"].add(f"PanelApp{site}:{p['id']}:{'green' if str(g['confidence_level'])=='3' else 'amber'}")
                if g.get("mode_of_inheritance"):
                    e["moi"].add(g["mode_of_inheritance"].split(",")[0][:60])
    for hpo in a.hpo or []:
        d = http(f"https://ontology.jax.org/api/network/annotation/{hpo}")
        for g in d.get("genes", []):
            e = genes.setdefault(g["name"], {"gene": g["name"], "sources": set(), "moi": set()})
            e["sources"].add(f"HPO:{hpo}")
        panels_used.append(f"HPO-annotation:{hpo}:{len(d.get('genes', []))} genes")
    rows = [{"gene": k, "n_sources": len(v["sources"]), "sources": ";".join(sorted(v["sources"])),
             "moi": ";".join(sorted(v["moi"]))} for k, v in sorted(genes.items())]
    write_tsv(os.path.join(a.out, "genes.tsv"), rows, ["gene", "n_sources", "sources", "moi"])
    manifest(a.out, "genes", {"date": str(date.today()), "keywords": a.keywords, "hpo": a.hpo,
                              "amber": a.amber, "sources": panels_used, "n_genes": len(rows)})
    print(f"{len(rows)} genes from {len(panels_used)} panels/terms -> genes.tsv")
    for s in panels_used:
        print("  ", s)


# --------------------------------------------------------------------------------------- regions
def hgnc_current(sym):
    for field in ("prev_symbol", "alias_symbol"):
        try:
            d = http(f"https://rest.genenames.org/search/{field}/{urllib.parse.quote(sym)}",
                     headers={"Accept": "application/json"}, tries=3, timeout=30)
            docs = d.get("response", {}).get("docs", [])
            if docs:
                return docs[0]["symbol"]
        except Exception:
            pass
    return ""


def cmd_regions(a):
    genes = [r["gene"] for r in read_tsv(os.path.join(a.out, "genes.tsv"))]
    rows, missing = [], []
    for i in range(0, len(genes), 900):
        chunk = genes[i:i + 900]
        d = http(ENSEMBL + "/lookup/symbol/homo_sapiens", {"symbols": chunk},
                 headers={"Accept": "application/json"})
        for g in chunk:
            r = d.get(g)
            if not r or r.get("seq_region_name", "").startswith(("CHR_", "HSCHR")):
                missing.append(g)
                continue
            rows.append({"gene": g, "chrom": r["seq_region_name"],
                         "start": max(1, r["start"] - 5000), "end": r["end"] + 5000})
    # outdated / alias symbols (e.g. AARS -> AARS1, GBA -> GBA1, H3F3A -> H3-3A): resolve through HGNC
    # so real phenotype genes are not silently left unscanned. Span rows keep the ORIGINAL symbol
    # (the one in genes.tsv); the current symbol is recorded in gene_alias.tsv for matching VEP output.
    alias, still = [], []
    for g in missing:
        new = hgnc_current(g)
        time.sleep(0.15)
        if new and new != g:
            try:
                d = http(ENSEMBL + "/lookup/symbol/homo_sapiens", {"symbols": [new]},
                         headers={"Accept": "application/json"}).get(new)
            except Exception:
                d = None
            if d and not d.get("seq_region_name", "").startswith(("CHR_", "HSCHR")):
                rows.append({"gene": g, "chrom": d["seq_region_name"],
                             "start": max(1, d["start"] - 5000), "end": d["end"] + 5000})
                alias.append({"old": g, "new": new})
                continue
        still.append(g)
    write_tsv(os.path.join(a.out, "regions.tsv"), rows, ["gene", "chrom", "start", "end"])
    write_tsv(os.path.join(a.out, "gene_alias.tsv"), alias, ["old", "new"])
    manifest(a.out, "regions", {"date": str(date.today()), "source": "Ensembl REST lookup/symbol + HGNC prev/alias",
                                "n": len(rows), "resolved_via_hgnc": alias, "unmapped": still})
    print(f"{len(rows)} gene spans ({len(alias)} via HGNC previous/alias symbol); "
          f"{len(still)} still unmapped (listed in manifest): {', '.join(still[:30])}")


# ------------------------------------------------------------------------------------------ scan
def cmd_scan(a):
    regs = {}
    for r in read_tsv(os.path.join(a.out, "regions.tsv")):
        regs.setdefault(r["chrom"], []).append((int(r["start"]), int(r["end"]), r["gene"]))
    calls, allkeys, header_sample, si = [], [], None, None
    n_total = 0
    with open_text(a.vcf) as f:
        for line in f:
            if line.startswith("##"):
                continue
            if line.startswith("#CHROM"):
                cols = line.rstrip("\n").split("\t")
                samples = cols[9:]
                si = samples.index(a.sample) if a.sample else 0
                header_sample = samples[si]
                continue
            t = line.rstrip("\n").split("\t")
            n_total += 1
            fmt = t[8].split(":")
            vals = t[9 + si].split(":")
            fv = dict(zip(fmt, vals))
            gt = fv.get("GT", "./.").replace("|", "/")
            alleles = [x for x in gt.split("/") if x not in (".", "0")]
            if not alleles:
                continue
            alts = t[4].split(",")
            qual = float(t[5]) if t[5] not in (".", "") else 0.0
            chrom = norm_chrom(t[0])
            pos = int(t[1])
            ad = fv.get("AD", "")
            for ai in sorted(set(alleles)):
                alt = alts[int(ai) - 1]
                if alt in ("*", "<NON_REF>"):
                    continue
                k = key(chrom, pos, t[3], alt)
                allkeys.append(k)
                if qual < a.min_qual:
                    flag = "LOWQUAL"
                else:
                    flag = t[6] if t[6] not in (".", "PASS") else ""
                for s, e, g in regs.get(chrom, []):
                    if s <= pos <= e:
                        calls.append({"key": k, "gene_span": g, "gt": gt, "qual": qual,
                                      "filter": t[6], "flag": flag, "ad": ad,
                                      "dp": fv.get("DP", ""), "gq": fv.get("GQ", "")})
                        break
    write_tsv(os.path.join(a.out, "calls.tsv"), calls,
              ["key", "gene_span", "gt", "qual", "filter", "flag", "ad", "dp", "gq"])
    with open(os.path.join(a.out, "allcalls.keys"), "w", encoding="utf-8") as f:
        f.write("\n".join(allkeys) + "\n")
    manifest(a.out, "scan", {"vcf": os.path.abspath(a.vcf), "sample": header_sample,
                             "records": n_total, "nonref_alleles": len(allkeys),
                             "in_phenotype_gene_spans": len(calls), "min_qual_flag": a.min_qual,
                             "note": "low-quality calls are flagged, not dropped"})
    print(f"sample={header_sample} records={n_total} nonref={len(allkeys)} in-gene-spans={len(calls)}")


# --------------------------------------------------------------------------------------- clinvar
def cmd_clinvar(a):
    want = set(open(os.path.join(a.out, "allcalls.keys"), encoding="utf-8").read().split())
    src = a.clinvar_vcf or CLINVAR_VCF
    hits, filedate, n = [], None, 0
    with open_text(src) as f:
        for line in f:
            if line.startswith("##fileDate"):
                filedate = line.strip().split("=", 1)[1]
            if line.startswith("#"):
                continue
            n += 1
            t = line.split("\t", 8)
            for alt in t[4].split(","):
                k = key(t[0], t[1], t[3], alt)
                if k in want:
                    info = dict(kv.split("=", 1) for kv in t[7].strip().split(";") if "=" in kv)
                    hits.append({"key": k, "variation_id": t[2],
                                 "gene": info.get("GENEINFO", "").split(":")[0],
                                 "clnsig": info.get("CLNSIG", ""),
                                 "clnsigconf": info.get("CLNSIGCONF", ""),
                                 "clnrevstat": info.get("CLNREVSTAT", ""),
                                 "clndn": info.get("CLNDN", "")[:300]})
    write_tsv(os.path.join(a.out, "clinvar_hits.tsv"), hits,
              ["key", "variation_id", "gene", "clnsig", "clnsigconf", "clnrevstat", "clndn"])
    manifest(a.out, "clinvar", {"source": src, "fileDate": filedate, "records": n,
                                "matched": len(hits), "queried": str(date.today()),
                                "note": "exact CHROM:POS:REF:ALT match; normalise VCF (bcftools norm -m- -f ref) for indels"})
    print(f"ClinVar fileDate={filedate} records={n} matched={len(hits)}")


# -------------------------------------------------------------------------------------- annotate
def vep_batch(keys, tries=5):
    variants = []
    for k in keys:
        c, p, r, al = k.split(":")
        variants.append(f"{c} {p} . {r} {al} . . .")
    q = "canonical=1&hgvs=1&mane=1&REVEL=1&AlphaMissense=1&numbers=1"
    return http(f"{ENSEMBL}/vep/homo_sapiens/region?{q}", {"variants": variants},
                headers={"Accept": "application/json"}, timeout=300, tries=tries)


def summarise_vep(rec):
    tcs = rec.get("transcript_consequences", []) or []
    try:
        my_alt = rec["input"].split()[4]
    except Exception:
        my_alt = None
    def pick():
        for test in (lambda t: t.get("mane_select"), lambda t: t.get("canonical"), lambda t: True):
            c = [t for t in tcs if test(t) and t.get("biotype") == "protein_coding"]
            if c:
                return c[0]
        return tcs[0] if tcs else {}
    t = pick()
    genes = sorted({x.get("gene_symbol", "") for x in tcs if x.get("gene_symbol")})
    any_pa = sorted({c for x in tcs for c in x.get("consequence_terms", [])} & PROTEIN_ALTERING)
    af, rsids = {}, []
    for cv in rec.get("colocated_variants", []) or []:
        if cv.get("id", "").startswith("rs"):
            rsids.append(cv["id"])
        for al, fr in (cv.get("frequencies") or {}).items():
            # VEP keys frequencies by allele; for indels the key is the trimmed allele or '-'.
            # Only count the sample's own ALT (SNV exact match; indels: accept if single allele listed).
            if my_alt and len(my_alt) == 1 and len(rec["input"].split()[3]) == 1 and al != my_alt:
                continue
            for pop, v in fr.items():
                if pop in ("gnomade", "gnomadg"):
                    af[pop] = max(af.get(pop, 0), v)
    return {"vep_gene": t.get("gene_symbol", ";".join(genes)), "all_genes": ";".join(genes),
            "consequence": ",".join(t.get("consequence_terms", [])) or rec.get("most_severe_consequence", ""),
            "most_severe": rec.get("most_severe_consequence", ""),
            "any_protein_altering": ",".join(any_pa),
            "impact": t.get("impact", ""), "transcript": t.get("mane_select") or t.get("transcript_id", ""),
            "hgvsc": t.get("hgvsc", ""), "hgvsp": t.get("hgvsp", ""),
            "revel": t.get("revel", ""), "alphamissense": (t.get("alphamissense") or {}).get("am_pathogenicity", "") if isinstance(t.get("alphamissense"), dict) else t.get("am_pathogenicity", ""),
            "gnomade_af": af.get("gnomade", ""), "gnomadg_af": af.get("gnomadg", ""),
            "rsid": ";".join(sorted(set(rsids)))}


def vep_robust(chunk, depth=0):
    """Annotate a chunk; on failure split it. HTTP 400 and persistent 5xx (a poison variant makes the
    server fail the whole batch) are split down to single variants to isolate the culprit; plain
    network failures (timeouts, DNS) are split only once, so an outage does not multiply retries.
    Returns (annotations, [(key, error)])."""
    try:
        out = {}
        for rec in vep_batch(chunk, tries=5 if depth == 0 else 2):
            c, p = rec["input"].split()[:2]
            r, al = rec["input"].split()[3:5]
            out[key(c, p, r, al)] = summarise_vep(rec)
        return out, []
    except urllib.error.HTTPError as e:
        err, bad_request = f"HTTP {e.code}", True
    except Exception as e:
        err = str(e)[:160]
        bad_request = bool(re.search(r"HTTP Error 5\d\d", str(e)))
    if len(chunk) == 1:
        return {}, [(chunk[0], err)]
    if not bad_request and depth >= 1:
        return {}, [(k, err) for k in chunk]
    mid = len(chunk) // 2
    o1, f1 = vep_robust(chunk[:mid], depth + 1)
    o2, f2 = vep_robust(chunk[mid:], depth + 1)
    o1.update(o2)
    return o1, f1 + f2


def clinvar_tiers(cv):
    """Tiers T1a / T1b from the ClinVar record alone, plus notes. A label may only ADD a variant."""
    t, notes = [], []
    if not cv:
        return t, notes
    sig = cv["clnsig"].lower()
    terms = set(re.split(r"[|,/]", sig))
    if sig in PATHO or terms & {"pathogenic", "likely_pathogenic"} and "conflicting" not in sig:
        t.append("T1a")
    if "conflicting" in sig:
        conf = clnsigconf_counts(cv["clnsigconf"])
        np_ = sum(v for k, v in conf.items() if "pathogenic" in k and "conflicting" not in k)
        if np_:
            t.append("T1b")
            notes.append(f"ClinVar conflicting: {cv['clnsigconf']}")
    if "benign" in sig and "pathogenic" not in sig:
        notes.append("ClinVar B/LB - verify, NOT excluded")
    return t, notes


# -------------------------------------------------------------------------------------- nirvana
SEVERITY = ["transcript_ablation", "splice_acceptor_variant", "splice_donor_variant", "stop_gained",
            "frameshift_variant", "stop_lost", "start_lost", "transcript_amplification",
            "inframe_insertion", "inframe_deletion", "missense_variant", "protein_altering_variant",
            "splice_region_variant", "splice_donor_5th_base_variant", "splice_donor_region_variant",
            "splice_polypyrimidine_tract_variant", "incomplete_terminal_codon_variant",
            "start_retained_variant", "stop_retained_variant", "synonymous_variant",
            "coding_sequence_variant", "mature_miRNA_variant", "5_prime_UTR_variant", "3_prime_UTR_variant",
            "non_coding_transcript_exon_variant", "intron_variant", "NMD_transcript_variant",
            "non_coding_transcript_variant", "upstream_gene_variant", "downstream_gene_variant",
            "TFBS_ablation", "TFBS_amplification", "TF_binding_site_variant", "regulatory_region_ablation",
            "regulatory_region_amplification", "feature_elongation", "regulatory_region_variant",
            "feature_truncation", "intergenic_variant"]
SEV_RANK = {c: i for i, c in enumerate(SEVERITY)}


def _sev(consequences):
    return min((SEV_RANK.get(c, 99) for c in consequences or []), default=99)


def _trim_prefix(ref, alt):
    k = 0
    while k < min(len(ref), len(alt)) and ref[k] == alt[k]:
        k += 1
    return k


def nirvana_summary(v, t_all):
    """One variant record of Illumina Connected Annotations / Nirvana JSON -> the same summary dict
    that summarise_vep() returns, so annotate/rank/dossier work unchanged."""
    pc = [t for t in t_all if t.get("bioType") in ("mRNA", "protein_coding")]
    pool = [t for t in pc if t.get("isManeSelect")] or [t for t in pc if t.get("isCanonical")] or pc or t_all
    best = min(pool, key=lambda t: _sev(t.get("consequence")), default={})
    any_pa = sorted({c for t in pc for c in (t.get("consequence") or [])} & PROTEIN_ALTERING)
    genes = sorted({t.get("hgnc") for t in pc if t.get("hgnc")})
    g = v.get("gnomad") or {}
    ge = v.get("gnomad-exome") or {}
    am = [a.get("pathogenicity") for a in (v.get("alphaMissense") or []) if a.get("pathogenicity") is not None]
    rs = (v.get("dbsnp") or [])
    rsids = rs if isinstance(rs, list) else [rs]
    hgvsp = (best.get("hgvsp") or "").replace("(", "").replace(")", "")
    return {"vep_gene": best.get("hgnc", ""), "all_genes": ";".join(genes),
            "consequence": ",".join(best.get("consequence") or []),
            "most_severe": min((c for t in t_all for c in (t.get("consequence") or [])),
                               key=lambda c: SEV_RANK.get(c, 99), default=""),
            "any_protein_altering": ",".join(any_pa), "impact": best.get("impact", "") if isinstance(best.get("impact"), str) else "",
            "transcript": best.get("transcript", ""), "hgvsc": best.get("hgvsc", ""), "hgvsp": hgvsp,
            "revel": (v.get("revel") or {}).get("score", ""), "alphamissense": max(am) if am else "",
            "gnomade_af": ge.get("allAf", ""), "gnomadg_af": g.get("allAf", ""),
            "rsid": ";".join(sorted({str(x) for x in rsids if str(x).startswith("rs")}))}


def load_nirvana(path):
    """Read a Nirvana .json.gz and return {CHROM:POS:REF:ALT (VCF representation): summary}.
    Nirvana trims the shared leading base of indels, so each original ALT is matched to its variant
    record by (trimmed begin, trimmed ref, trimmed alt)."""
    d = json.load(gzip.open(path, "rt", encoding="utf-8"))
    out = {}
    for p in d["positions"]:
        chrom, pos, ref = norm_chrom(p["chromosome"]), int(p["position"]), p["refAllele"]
        vs = p.get("variants", []) or []
        for i, alt in enumerate(p["altAlleles"]):
            if alt in ("*", "<NON_REF>"):
                continue
            k = _trim_prefix(ref, alt)
            want = (pos + k, ref[k:] or "-", alt[k:] or "-")
            hit = next((v for v in vs if (int(v["begin"]), v["refAllele"] or "-", v["altAllele"] or "-") == want), None)
            if hit is None:
                hit = next((v for v in vs if v["altAllele"] == alt), None) or \
                    (vs[i] if len(vs) == len(p["altAlleles"]) else None)
            if hit is not None:
                out[key(chrom, pos, ref, alt)] = nirvana_summary(hit, hit.get("transcripts", []) or [])
    return out


def cmd_annotate(a):
    calls = read_tsv(os.path.join(a.out, "calls.tsv"))
    cv = read_tsv(os.path.join(a.out, "clinvar_hits.tsv"))
    # ClinVar hits are annotated only when they can enter a ClinVar tier (T1a/T1b) - annotating every
    # genome-wide benign/VUS hit costs hours and adds nothing. --all-clinvar restores that.
    cv_keys = {h["key"] for h in cv if a.all_clinvar or clinvar_tiers(h)[0]}
    keys = sorted({c["key"] for c in calls} | cv_keys)
    lock = os.path.join(a.out, "annotate.lock")
    if os.path.exists(lock) and time.time() - os.path.getmtime(lock) < 900 and not a.force:
        sys.exit(f"{lock} was updated <15 min ago: another annotate is running (use --force to override)")
    open(lock, "w").write(str(os.getpid()))
    cache_p = os.path.join(a.out, "annotate_cache.jsonl")
    ann, failed = {}, []
    if os.path.exists(cache_p) and not a.nirvana:
        for line in open(cache_p, encoding="utf-8"):
            try:
                o = json.loads(line)
                ann[o["key"]] = o["ann"]
            except Exception:
                pass
    if a.nirvana:
        nv = load_nirvana(a.nirvana)
        for k in keys:
            if k in nv:
                ann[k] = nv[k]
        for k in [k for k in keys if k not in ann]:
            failed.append((k, "not present in the Nirvana output"))
        todo = []
    else:
        todo = [k for k in keys if k not in ann]
    print(f"{len(keys)} variants to annotate ({len(keys) - len(todo)} already cached); "
          f"{len(cv_keys)} from ClinVar hits", file=sys.stderr)
    chunks = [todo[i:i + 200] for i in range(0, len(todo), 200)]
    done = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, a.workers)) as ex,             open(cache_p, "a", encoding="utf-8") as cf:
        for fut in concurrent.futures.as_completed([ex.submit(vep_robust, c) for c in chunks]):
            got, bad = fut.result()
            for k, v in got.items():
                ann[k] = v
                cf.write(json.dumps({"key": k, "ann": v}) + chr(10))
            cf.flush()
            failed += bad
            done += 1
            os.utime(lock, None)
            print(f"  VEP chunks {done}/{len(chunks)}  annotated {len(ann)}  failed {len(failed)}", file=sys.stderr)
    os.remove(lock)
    cols = ["key", "vep_gene", "all_genes", "consequence", "most_severe", "any_protein_altering",
            "impact", "transcript", "hgvsc", "hgvsp", "revel", "alphamissense", "gnomade_af",
            "gnomadg_af", "rsid", "vep_status"]
    rows = []
    for k in keys:
        r = dict(ann.get(k, {}))
        r["key"] = k
        r["vep_status"] = "ok" if k in ann else "NOT_ANNOTATED_KEEP"
        rows.append(r)
    write_tsv(os.path.join(a.out, "annotated.tsv"), rows, cols)
    write_tsv(os.path.join(a.out, "annotate_failed.tsv"), [{"key": k, "error": e} for k, e in failed], ["key", "error"])
    manifest(a.out, "annotate", {"date": str(date.today()), "source": ("Nirvana: " + os.path.abspath(a.nirvana)) if a.nirvana else "Ensembl VEP REST (GRCh38)",
                                 "n": len(keys), "annotated": sum(1 for k in keys if k in ann),
                                 "not_annotated": len(failed), "clinvar_all_hits": bool(a.all_clinvar)})
    print(f"annotated {sum(1 for k in keys if k in ann)}/{len(keys)}; NOT annotated (kept, flagged): {len(failed)}"
          + (f" -> annotate_failed.tsv; re-run `annotate` to retry them" if failed else ""))
    if failed:
        print("WARNING: failed variants stay in T2 as NOT_ANNOTATED_KEEP but with unknown frequency;"
              " resolve them before trusting the ranking.", file=sys.stderr)


# ------------------------------------------------------------------------------------------ rank
def clnsigconf_counts(s):
    out = {}
    for part in s.split("|"):
        m = re.match(r"([A-Za-z_/ ]+)\((\d+)\)", part.strip())
        if m:
            out[m.group(1).strip().lower()] = int(m.group(2))
    return out


def fnum(x, d=None):
    try:
        return float(x)
    except Exception:
        return d


def tiers_for(call, ann, cv, genes, af_dom, af_rec):
    t, notes = clinvar_tiers(cv)
    ae, ag = fnum(ann.get("gnomade_af")), fnum(ann.get("gnomadg_af"))
    vals = [v for v in (ae, ag) if v is not None]
    af = max(vals) if vals else 0.0
    af_max = af
    if ae is not None and ag is not None and min(ae, ag) > 0 and max(ae, ag) / min(ae, ag) > 100:
        # exome/genome discordance is a known artifact signature (filtered genome calls, e.g. TUBB2A
        # p.Ala248Val); never demote on one discordant source - tier on the lower value and flag it.
        af = min(ae, ag)
        notes.append(f"gnomAD exome/genome AF discordant ({ae:g} vs {ag:g}) - check gnomAD filter flags")
    gene = ann.get("vep_gene") or (call or {}).get("gene_span", "")
    in_pheno = any(g in genes for g in (ann.get("all_genes", "") or gene).split(";") if g) or \
        (call and call.get("gene_span") in genes)
    pa = bool(ann.get("any_protein_altering"))
    if in_pheno and (pa or ann.get("vep_status") != "ok"):
        if af < af_dom:
            t.append("T2")
        elif af < af_rec:
            t.append("T2r")
            notes.append(f"AF {af:g} only plausible for recessive")
        if ann.get("vep_status") != "ok":
            notes.append("VEP failed - review manually")
    return t, af, in_pheno, notes, af_max


def moi_class(genes_row):
    m = (genes_row or {}).get("moi", "").lower()
    if "x-linked" in m or "x linked" in m:
        return "X"
    rec = "biallelic" in m or "recessive" in m
    dom = "monoallelic" in m or "dominant" in m
    return "both" if rec and dom else ("AR" if rec else ("AD" if dom else ""))


def call_adjust(call, genes_row, af_max):
    """Score adjustments from genotype, inheritance and call quality. Never removes a variant;
    only reorders and explains."""
    adj, notes = 0.0, []
    gt = (call or {}).get("gt", "")
    het = gt in ("0/1", "1/0")
    hom = gt in ("1/1",)
    moi = moi_class(genes_row)
    if het and moi == "AR":
        adj -= 2
        notes.append("single het in recessive-only gene: carrier unless a second hit exists")
    elif hom and moi == "AR":
        adj += 1
    elif het and moi in ("AD", "X"):
        adj += 1
    ad = (call or {}).get("ad", "")
    try:
        nums = [int(x) for x in ad.split(",")]
        vaf = nums[1] / max(1, nums[0] + nums[1]) if len(nums) == 2 else None
    except Exception:
        vaf = None
    if het and vaf is not None:
        if vaf < 0.2:
            adj -= 2
            notes.append(f"low allele balance {vaf:.2f} for a het (artifact or mosaic)")
        elif vaf > 0.8:
            adj -= 1
            notes.append(f"high allele balance {vaf:.2f} for a het")
    dp, qual = fnum((call or {}).get("dp")), fnum((call or {}).get("qual"))
    if dp is not None and dp < 10:
        adj -= 1
        notes.append(f"DP {dp:g} < 10")
    if qual is not None and qual < 50:
        adj -= 1
        notes.append(f"QUAL {qual:g} < 50")
    if af_max is not None and af_max >= 0.01:
        adj -= 4
        notes.append(f"COMMON in a gnomAD source (max AF {af_max:g}): a rare-disease label is implausible, "
                     "suspect mapping artifact or low-penetrance; kept for review")
    return adj, notes


def score(tiers, ann, af, genes_row, adj=0.0):
    s = 0.0
    s += 4 if "T1a" in tiers else 0
    s += 3 if "T1b" in tiers else 0
    s += 3 if "T2" in tiers else (1 if "T2r" in tiers else 0)
    imp = ann.get("impact", "")
    s += {"HIGH": 3, "MODERATE": 1.5, "LOW": 0.3}.get(imp, 0)
    s += 1.5 if af == 0 else (1 if af < 1e-5 else 0)
    rv, am = fnum(ann.get("revel")), fnum(ann.get("alphamissense"))
    if rv is not None:
        s += 2 * rv
    if am is not None:
        s += 2 * am
    if genes_row:
        s += min(int(genes_row.get("n_sources", 0)), 4) * 0.5
        if "green" in genes_row.get("sources", ""):
            s += 1
    return round(s + adj, 2)


def cmd_rank(a):
    from collections import Counter
    genes = {r["gene"]: r for r in read_tsv(os.path.join(a.out, "genes.tsv"))}
    alias_p = os.path.join(a.out, "gene_alias.tsv")
    if os.path.exists(alias_p):                      # current HGNC symbol inherits the old symbol's row
        for r in read_tsv(alias_p):
            if r["old"] in genes:
                genes.setdefault(r["new"], genes[r["old"]])
    calls = {}
    for c in read_tsv(os.path.join(a.out, "calls.tsv")):
        calls.setdefault(c["key"], c)
    cv = {h["key"]: h for h in read_tsv(os.path.join(a.out, "clinvar_hits.tsv"))}
    ann = {r["key"]: r for r in read_tsv(os.path.join(a.out, "annotated.tsv"))}
    rows, outside = [], []
    for k in sorted(set(calls) | set(cv)):
        an = ann.get(k, {"vep_status": "NOT_ANNOTATED_KEEP"})
        tiers, af, in_pheno, notes, af_max = tiers_for(calls.get(k), an, cv.get(k), genes, a.af_dominant, a.af_recessive)
        if not tiers:
            continue
        c = calls.get(k, {})
        g = an.get("vep_gene") or c.get("gene_span") or (cv.get(k) or {}).get("gene", "")
        if c.get("flag"):
            notes.append(f"call flag: {c['flag']}")
        adj, n2 = call_adjust(c, genes.get(g), af_max)
        notes += n2
        row = {"key": k, "gene": g, "tiers": ",".join(tiers), "score": score(tiers, an, af, genes.get(g), adj),
               "gt": c.get("gt", ""), "ad": c.get("ad", ""), "dp": c.get("dp", ""), "qual": c.get("qual", ""),
               "consequence": an.get("consequence", ""), "hgvsc": an.get("hgvsc", ""), "hgvsp": an.get("hgvsp", ""),
               "max_gnomad_af": af_max, "revel": an.get("revel", ""), "alphamissense": an.get("alphamissense", ""),
               "in_phenotype_genes": in_pheno, "gene_sources": (genes.get(g) or {}).get("sources", ""),
               "moi": (genes.get(g) or {}).get("moi", ""),
               "clinvar_vcv": (cv.get(k) or {}).get("variation_id", ""),
               "clinvar_aggregate": (cv.get(k) or {}).get("clnsig", ""),
               "clinvar_counts": (cv.get(k) or {}).get("clnsigconf", ""),
               "rsid": an.get("rsid", ""), "notes": " | ".join(notes)}
        (rows if in_pheno else outside).append(row)
    # several hits in one recessive gene: flag possible compound heterozygosity (phase unknown)
    per_gene = Counter(r["gene"] for r in rows
                       if moi_class(genes.get(r["gene"])) in ("AR", "both") and r["gt"] in ("0/1", "1/0"))
    for r in rows:
        if per_gene.get(r["gene"], 0) >= 2:
            r["notes"] += (" | " if r["notes"] else "") + \
                f"{per_gene[r['gene']]} candidate hits in recessive gene: check phase (compound het)"
            r["score"] = round(r["score"] + 2, 2)
    rows.sort(key=lambda r: -r["score"])
    outside.sort(key=lambda r: -r["score"])
    cols = ["key", "gene", "tiers", "score", "gt", "ad", "dp", "qual", "consequence", "hgvsc", "hgvsp",
            "max_gnomad_af", "revel", "alphamissense", "in_phenotype_genes", "gene_sources", "moi",
            "clinvar_vcv", "clinvar_aggregate", "clinvar_counts", "rsid", "notes"]
    write_tsv(os.path.join(a.out, "tiers.tsv"), rows, cols)
    write_tsv(os.path.join(a.out, "candidates.tsv"), rows[:a.top], cols)
    write_tsv(os.path.join(a.out, "outside_phenotype.tsv"), outside, cols)
    tc = Counter(t for r in rows for t in r["tiers"].split(","))
    n_unann = sum(1 for r in rows if "VEP failed" in r["notes"])
    manifest(a.out, "rank", {"af_dominant": a.af_dominant, "af_recessive": a.af_recessive,
                             "tier_counts": dict(tc), "n_union": len(rows), "n_outside_phenotype": len(outside),
                             "n_unannotated_in_union": n_unann, "top": a.top})
    print(f"union of tiers (phenotype genes): {len(rows)} variants; tier counts {dict(tc)}; "
          f"{len(outside)} ClinVar-tier variants outside the phenotype genes -> outside_phenotype.tsv")
    if n_unann:
        print(f"WARNING: {n_unann} variants in the union were never annotated (see annotate_failed.tsv)", file=sys.stderr)
    for r in rows[:a.top]:
        print(f"{r['score']:6} {r['tiers']:10} {r['gene']:10} {r['key']:22} {r['hgvsp'][-22:]:22} AF={r['max_gnomad_af']} {r['clinvar_aggregate'][:40]}")


# --------------------------------------------------------------------------------------- dossier
def ncbi(url_tail, raw=False):
    time.sleep(0.4)  # stay under 3 req/s without an API key
    sep = "&" if "?" in url_tail else "?"
    return http(EUTILS + url_tail + f"{sep}tool={NCBI_TOOL}", raw=raw)


def clinvar_scvs(vid):
    xml = ncbi(f"efetch.fcgi?db=clinvar&id={vid}&rettype=vcv&is_variationid", raw=True)
    root = ET.fromstring(xml)
    va = root.find(".//VariationArchive")
    head = {"vcv": va.get("Accession") + "." + va.get("Version") if va is not None else "",
            "name": va.get("VariationName") if va is not None else ""}
    agg = root.find(".//Classifications/GermlineClassification")
    if agg is not None:
        head["aggregate"] = agg.findtext("Description")
        head["review"] = agg.findtext("ReviewStatus")
        ex = agg.find("Explanation")
        head["explanation"] = ex.text if ex is not None else ""
        head["last_evaluated"] = agg.get("DateLastEvaluated")
    rcvs = []
    for rcv in root.iter("RCVAccession"):
        cls = rcv.find(".//GermlineClassification")
        conds = [c.text for c in rcv.iter("ClassifiedCondition") if c.text]
        rcvs.append({"rcv": rcv.get("Accession"), "conditions": "; ".join(conds),
                     "classification": cls.findtext("Description") if cls is not None else "",
                     "review": cls.findtext("ReviewStatus") if cls is not None else ""})
    scvs = []
    for ca in root.iter("ClinicalAssertion"):
        acc = ca.find("ClinVarAccession")
        cl = ca.find("Classification")
        if acc is None or cl is None:
            continue
        pmids = sorted({i.text for i in ca.iter("ID") if i.get("Source") == "PubMed" and i.text})
        traits = [t.findtext(".//ElementValue") for t in ca.iter("Trait")]
        origin = [o.text for o in ca.iter("Origin") if o.text]
        method = [m.text for m in ca.iter("MethodType") if m.text]
        scvs.append({"scv": f"{acc.get('Accession')}.{acc.get('Version')}", "submitter": acc.get("SubmitterName"),
                     "classification": cl.findtext("GermlineClassification") or "",
                     "last_evaluated": cl.get("DateLastEvaluated") or "", "review": cl.findtext("ReviewStatus") or "",
                     "contributes": ca.get("ContributesToAggregateClassification") or "",
                     "condition": "; ".join(t for t in traits if t)[:120],
                     "origin": ",".join(sorted(set(origin))), "method": ",".join(sorted(set(method))),
                     "pmids": ",".join(pmids), "comment": (cl.findtext("Comment") or "").replace("\n", " ")[:400]})
    aliases = sorted({e.text for e in root.iter("ProteinChange") if e.text} |
                     {e.text for e in root.iter("OtherName") if e.text and e.text.startswith("p.")})
    return head, rcvs, scvs, aliases


def clinvar_vid_by_position(k):
    """VariationID for an exact GRCh38 CHROM:POS:REF:ALT via E-utilities position search,
    then matching ref/alt in the summary. Returns '' if none."""
    c, p, r, al = k.split(":")
    ids = ncbi("esearch.fcgi?" + urllib.parse.urlencode(
        {"db": "clinvar", "term": f"{c}[chr] AND {p}[chrpos38]", "retmax": 50, "retmode": "json"}))["esearchresult"]["idlist"]
    if not ids:
        return ""
    s = ncbi("esummary.fcgi?" + urllib.parse.urlencode({"db": "clinvar", "id": ",".join(ids), "retmode": "json"}))["result"]
    for i in ids:
        for vs in s.get(i, {}).get("variation_set", []):
            for loc in vs.get("variation_loc", []):
                if loc.get("assembly_name") == "GRCh38" and str(loc.get("start")) == p and \
                        loc.get("ref") == r and loc.get("alt") == al:
                    return i
            spdi = vs.get("canonical_spdi", "")
            if spdi.endswith(f":{int(p)-1}:{r}:{al}"):
                return i
    return ""


def gnomad_v4(k):
    c, p, r, al = k.split(":")
    q = ('query{variant(variantId:"%s-%s-%s-%s", dataset: gnomad_r4){variant_id '
         'exome{ac an faf95{popmax popmax_population}} genome{ac an faf95{popmax popmax_population}}}}') % (c, p, r, al)
    try:
        d = http(GNOMAD, {"query": q})
        if d.get("errors"):
            return "not found in gnomAD v4 (" + d["errors"][0].get("message", "")[:60] + ")"
        v = d["data"]["variant"]
        parts = []
        for s in ("exome", "genome"):
            x = v.get(s)
            if x:
                parts.append(f"{s} AC={x['ac']} AN={x['an']} FAF95popmax={x['faf95']['popmax']}")
        return "; ".join(parts) or "present, no exome/genome data"
    except Exception as e:
        return f"query failed: {e}"


def gene_curation(sym):
    out = []
    for site in PANELAPP:
        try:
            d = http(f"{PANELAPP[site]}/genes/{sym}/")
            for g in d.get("results", []):
                lvl = {"3": "green", "2": "amber", "1": "red"}.get(str(g.get("confidence_level")), str(g.get("confidence_level")))
                out.append(f"PanelApp{site} {g['panel']['name']} (id {g['panel']['id']} v{g['panel']['version']}): {lvl}, {g.get('mode_of_inheritance','')[:50]}")
        except Exception as e:
            out.append(f"PanelApp{site}: query failed {e}")
    try:
        d = http(f"https://www.ebi.ac.uk/gene2phenotype/api/search/?query={sym}")
        for r in (d.get("results") or [])[:8]:
            out.append(f"G2P: {r.get('disease','')} | {r.get('genotype','') or r.get('allelic_requirement','')} | {r.get('confidence','')} | panels {r.get('panel','')}")
    except urllib.error.HTTPError as e:
        out.append("G2P: no entry (HTTP 404)" if e.code == 404 else f"G2P: query failed HTTP {e.code}")
    except Exception as e:
        out.append(f"G2P: query failed {e}")
    return out


def literature(rsid, gene, aliases):
    pm, notes = set(), []
    if rsid:
        try:
            ac = http(f"https://www.ncbi.nlm.nih.gov/research/litvar2-api/variant/autocomplete/?query={rsid}")
            for v in ac[:3]:
                vid = urllib.parse.quote(v.get("_id", ""), safe="")
                d = http(f"https://www.ncbi.nlm.nih.gov/research/litvar2-api/variant/get/{vid}/publications")
                pm |= set(map(str, d.get("pmids", []) or []))
            notes.append(f"LitVar2({rsid})")
        except Exception as e:
            notes.append(f"LitVar2 failed: {e}")
    for al in aliases[:6]:
        short = al.replace("p.", "")
        three = {"Ala":"A","Arg":"R","Asn":"N","Asp":"D","Cys":"C","Gln":"Q","Glu":"E","Gly":"G","His":"H","Ile":"I",
                 "Leu":"L","Lys":"K","Met":"M","Phe":"F","Pro":"P","Ser":"S","Thr":"T","Trp":"W","Tyr":"Y","Val":"V","Ter":"X"}
        for k3, v1 in three.items():
            short = short.replace(k3, v1)
        try:
            d = http("https://www.ncbi.nlm.nih.gov/research/pubtator3-api/search/?" +
                     urllib.parse.urlencode({"text": f"@VARIANT_p.{short}_{gene}_human"}))
            for r in d.get("results", []) or []:
                if r.get("pmid"):
                    pm.add(str(r["pmid"]))
            notes.append(f"PubTator3(p.{short})")
        except Exception as e:
            notes.append(f"PubTator3 p.{short} failed: {e}")
    return sorted(pm, key=int), notes


def cmd_dossier(a):
    cands = read_tsv(os.path.join(a.out, "tiers.tsv"))
    if a.variants:
        sel = [r for r in cands if r["key"] in set(a.variants)]
    else:
        sel = cands[:a.top]
    os.makedirs(os.path.join(a.out, "dossier"), exist_ok=True)
    index = [f"# Evidence dossiers ({date.today()})\n",
             "Every ClinVar submission is listed individually. The aggregate label is shown but is NOT a verdict.\n"]
    for r in sel:
        k, g = r["key"], r["gene"]
        print(f"dossier {g} {k}", file=sys.stderr)
        vid = r.get("clinvar_vcv", "")
        if not vid:
            try:
                vid = clinvar_vid_by_position(k)
            except Exception:
                vid = ""
        md = [f"# {g} {r['hgvsc']} {r['hgvsp']}", "",
              f"- Variant (GRCh38): `{k}`  genotype {r['gt']}  AD {r['ad']}  DP {r['dp']}  QUAL {r['qual']}",
              f"- Tiers: {r['tiers']}  score {r['score']}  consequence {r['consequence']}",
              f"- Pipeline AF (VEP gnomAD max): {r['max_gnomad_af']}  REVEL {r['revel']}  AlphaMissense {r['alphamissense']}",
              f"- gnomAD v4 (live): {gnomad_v4(k)}",
              f"- Notes: {r['notes']}", ""]
        aliases = []
        if vid:
            try:
                head, rcvs, scvs, aliases = clinvar_scvs(vid)
                md += [f"## ClinVar {head.get('vcv')} ({head.get('name')})", "",
                       f"Aggregate (pointer only): **{head.get('aggregate')}** - {head.get('explanation','')} - {head.get('review')} - last evaluated {head.get('last_evaluated')}", "",
                       "### Per-condition records (RCV)", "", "| RCV | condition | classification | review |", "|---|---|---|---|"]
                md += [f"| {x['rcv']} | {x['conditions']} | {x['classification']} | {x['review']} |" for x in rcvs]
                md += ["", "### Every submission (SCV) - read these, not the aggregate", "",
                       "| SCV | submitter | classification | last evaluated | review | counts? | origin | method | condition | PMIDs |",
                       "|---|---|---|---|---|---|---|---|---|---|"]
                for s in sorted(scvs, key=lambda s: s["last_evaluated"] or ""):
                    md.append(f"| {s['scv']} | {s['submitter']} | {s['classification']} | {s['last_evaluated']} | {s['review']} | {s['contributes']} | {s['origin']} | {s['method']} | {s['condition']} | {s['pmids']} |")
                from collections import Counter
                cnt = Counter(s["classification"] for s in scvs)
                md += ["", f"Submission tally (all SCVs, including non-contributing): {dict(cnt)}", "", "Comments:"]
                md += [f"- {s['scv']} ({s['classification']}, {s['last_evaluated']}): {s['comment']}" for s in scvs if s["comment"]]
                md += ["", f"Protein-change aliases in ClinVar: {', '.join(aliases)}", ""]
            except Exception as e:
                md += [f"ClinVar SCV fetch failed: {e}", ""]
        else:
            md += ["## ClinVar", "", "No ClinVar record found (absence of a record is not evidence of benignity).", ""]
        if not aliases and r.get("hgvsp"):
            aliases = [r["hgvsp"].split(":")[-1]]
        md += ["## Gene-disease curation", ""] + [f"- {x}" for x in gene_curation(g)] + [""]
        pm, notes = literature(r.get("rsid", "").split(";")[0] if r.get("rsid") else "", g, aliases)
        md += ["## Literature", "", f"Sources queried: {', '.join(notes)}",
               f"PMIDs ({len(pm)}): {', '.join(pm) if pm else 'none found by these queries (search ALL numberings manually)'}", "",
               "## Reviewer checklist (fill in; do not skip)", "",
               "- [ ] Gene-disease validity and inheritance match the patient's phenotype?",
               "- [ ] Genotype fits inheritance (het for AD / biallelic for AR; de novo if trio)?",
               "- [ ] ACMG/AMP criteria scored from primary evidence (not from ClinVar labels; PP5/BP6 not used)",
               "- [ ] Every SCV read, with dates; dissenting/old SCVs explained",
               "- [ ] Call quality checked in IGV (AD, strand, mapping)", ""]
        safe = re.sub(r"[^A-Za-z0-9_.-]", "_", f"{g}_{k}")
        open(os.path.join(a.out, "dossier", safe + ".md"), "w", encoding="utf-8").write("\n".join(md))
        index.append(f"- [{g} {r['hgvsp'] or k}](dossier/{safe}.md) - tiers {r['tiers']}, score {r['score']}, ClinVar aggregate: {r['clinvar_aggregate'] or 'none'}")
    open(os.path.join(a.out, "dossier.md"), "w", encoding="utf-8").write("\n".join(index) + "\n")
    manifest(a.out, "dossier", {"date": str(datetime.now()), "n": len(sel)})
    print(f"wrote {len(sel)} dossiers -> {os.path.join(a.out, 'dossier.md')}")


# --------------------------------------------------------------------------------------- control
def cmd_control(a):
    """Positive controls: check that each control variant lands in its expected tier using live
    ClinVar + VEP. Fails (exit 1) if a control is lost -> the pipeline logic or a resource broke."""
    keys = [c["id"] for c in CONTROLS]
    ann = {}
    for rec in vep_batch(keys):
        c, p = rec["input"].split()[:2]
        r, al = rec["input"].split()[3:5]
        ann[key(c, p, r, al)] = summarise_vep(rec)
    ok = True
    for c in CONTROLS:
        k = c["id"]
        an = ann.get(k, {"vep_status": "NOT_ANNOTATED_KEEP"})
        an.setdefault("vep_status", "ok")
        vid = clinvar_vid_by_position(k)
        cv = None
        if vid:
            head, rcvs, scvs, al = clinvar_scvs(vid)
            agg = (head.get("aggregate") or "").replace(" ", "_")
            conf = "|".join(f"{cls.replace(' ', '_')}({n})" for cls, n in
                            __import__("collections").Counter(s["classification"] for s in scvs if s["contributes"] != "false").items())
            cv = {"clnsig": agg, "clnsigconf": conf}
        tiers, af, inp, notes, _ = tiers_for(None, an, cv, {c["gene"]: {}}, 0.001, 0.01)
        hit = c["must"] in tiers
        ok &= hit
        print(f"{'PASS' if hit else 'FAIL'} {c['gene']} {k} expected {c['must']} got {tiers} ({c['why']}; ClinVar {cv})")
    sys.exit(0 if ok else 1)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    def add(name, f):
        p = sp.add_parser(name)
        p.add_argument("--out", required=(name != "control"), default=".")
        p.set_defaults(func=f)
        return p
    p = add("genes", cmd_genes); p.add_argument("--hpo", nargs="*"); p.add_argument("--keywords", nargs="*"); p.add_argument("--amber", action="store_true"); p.add_argument("--exclude", nargs="*", help="drop matched PanelApp panels whose name contains any of these substrings")
    add("regions", cmd_regions)
    p = add("scan", cmd_scan); p.add_argument("--vcf", required=True); p.add_argument("--sample"); p.add_argument("--min-qual", type=float, default=20)
    p = add("clinvar", cmd_clinvar); p.add_argument("--clinvar-vcf")
    p = add("annotate", cmd_annotate); p.add_argument("--workers", type=int, default=4); p.add_argument("--all-clinvar", action="store_true"); p.add_argument("--force", action="store_true"); p.add_argument("--nirvana", help="annotate from a Nirvana .json.gz (run on the whole VCF) instead of Ensembl VEP REST")
    p = add("rank", cmd_rank); p.add_argument("--af-dominant", type=float, default=0.001); p.add_argument("--af-recessive", type=float, default=0.01); p.add_argument("--top", type=int, default=30)
    p = add("dossier", cmd_dossier); p.add_argument("--top", type=int, default=15); p.add_argument("--variants", nargs="*")
    add("control", cmd_control)
    a = ap.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()
