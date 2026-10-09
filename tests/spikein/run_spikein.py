"""Spike-in test of the triage logic (edt.py): insert known causal variants from solved cases
(GA4GH phenopacket-store) into a real exome background and ask where the causal variant ranks
when the gene set comes ONLY from the case's HPO terms.

Background: any real exome VCF (for the published run: a patient exome with the two genes that carried
its own candidates excluded, so the background holds no known candidate). Annotation: Nirvana (gnomAD 4.1, REVEL, AlphaMissense).
Per case: gene set = union of genes annotated to the case's observed HPO terms (n_sources = number of
terms annotating the gene); tiers/score from edt.py unchanged. Baseline 'old logic' = the causal variant is
reported only if ClinVar's aggregate is Pathogenic / Likely pathogenic.
Caveats: one background; spike-ins overstate real performance; HPO-only gene sets (no PanelApp panel) are a
lower bound on what a clinician-chosen panel would give.
"""
import argparse, collections, csv, gzip, json, os, sys, time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "pipeline", "triage"))
import edt  # noqa: E402

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--background-vcf", required=True, help="exome VCF(.gz) used as background (GATK-style GT:AD:DP)")
ap.add_argument("--background-nirvana", required=True, help="Nirvana .json.gz of the background VCF")
ap.add_argument("--background-clinvar-hits", required=True, help="clinvar_hits.tsv from `edt.py clinvar` on the background")
ap.add_argument("--exclude-genes", nargs="*", default=[], help="genes removed from the background pool (known candidates)")
ap.add_argument("--spike-nirvana", default="spike_nv.json.gz", help="Nirvana JSON of spike.vcf")
ap.add_argument("--spike-clinvar-hits", default="spikeclin/clinvar_hits.tsv")
ARGS = None
BG_VCF = BG_NV = BG_CLIN = None
EXCLUDE_BG_GENES = set()


class AllGenes:
    def __contains__(self, g):
        return True


def parse_bg_calls(path, wanted):
    calls = {}
    with gzip.open(path, "rt", encoding="utf-8") as f:
        for line in f:
            if line[0] == "#":
                continue
            t = line.rstrip("\n").split("\t")
            fv = dict(zip(t[8].split(":"), t[9].split(":")))
            gt = fv.get("GT", "./.").replace("|", "/")
            alleles = [x for x in gt.split("/") if x not in (".", "0")]
            alts = t[4].split(",")
            for ai in set(alleles):
                alt = alts[int(ai) - 1]
                k = edt.key(t[0], t[1], t[3], alt)
                if k in wanted:
                    calls[k] = {"gt": gt, "ad": fv.get("AD", ""), "dp": fv.get("DP", ""), "qual": t[5],
                                "flag": "" if t[6] in (".", "PASS") else t[6], "gene_span": ""}
    return calls


def main():
    global ARGS, BG_VCF, BG_NV, BG_CLIN, EXCLUDE_BG_GENES
    ARGS = ap.parse_args()
    BG_VCF, BG_NV, BG_CLIN = ARGS.background_vcf, ARGS.background_nirvana, ARGS.background_clinvar_hits
    EXCLUDE_BG_GENES = set(ARGS.exclude_genes)
    t0 = time.time()
    cases = list(csv.DictReader(open("spike_cases.tsv", encoding="utf-8"), delimiter="\t"))
    hpo = json.load(open("hpo_genes.json"))
    cases = [c for c in cases if all(hpo.get(t) is not None for t in c["hpo"].split())]
    print("cases with complete HPO gene lists:", len(cases), flush=True)

    ann = edt.load_nirvana(BG_NV)
    print("background annotated:", len(ann), f"{time.time()-t0:.0f}s", flush=True)
    spike_ann = edt.load_nirvana(ARGS.spike_nirvana)
    clin = {r["key"]: r for r in edt.read_tsv(BG_CLIN)}
    clin_sp = {r["key"]: r for r in edt.read_tsv(ARGS.spike_clinvar_hits)}

    allg = AllGenes()
    pool = {}
    for k, a in ann.items():
        if set(a["all_genes"].split(";")) & EXCLUDE_BG_GENES or a["vep_gene"] in EXCLUDE_BG_GENES:
            continue
        a = dict(a, vep_status="ok")
        tiers, *_ = edt.tiers_for({"gene_span": ""}, a, clin.get(k), allg, 0.001, 0.01)
        if tiers:
            pool[k] = a
    print("background pool (any tier if every gene were a phenotype gene):", len(pool), flush=True)
    bg_calls = parse_bg_calls(BG_VCF, set(pool))
    print("background calls parsed:", len(bg_calls), f"{time.time()-t0:.0f}s", flush=True)

    out, spike_cv = [], {}
    for n, c in enumerate(cases, 1):
        gcount = collections.Counter(g for t in c["hpo"].split() for g in hpo[t])
        genes = {g: {"gene": g, "n_sources": n_, "sources": f"HPO x{n_}", "moi": ""} for g, n_ in gcount.items()}
        k = c["key"]
        sa = dict(spike_ann.get(k, {}), vep_status="ok") if k in spike_ann else None
        if sa is None:
            out.append({**{x: c[x] for x in ("case_id", "gene", "key", "gt")}, "rank": "", "tiers": "", "reason": "not annotated by Nirvana",
                        "union": "", "old_logic": "", "clinvar": ""})
            continue
        spike_call = {"gt": c["gt"], "ad": "30,30" if c["gt"] == "0/1" else "0,60", "dp": "60", "qual": "500", "flag": "", "gene_span": ""}
        rows = []
        for key_, a in list(pool.items()) + [(k, sa)]:
            cv = clin_sp.get(key_) if key_ == k else clin.get(key_)
            call = spike_call if key_ == k else bg_calls.get(key_, {"gene_span": ""})
            tiers, af, inp, notes, af_max = edt.tiers_for(call, a, cv, genes, 0.001, 0.01)
            if not tiers:
                continue
            g = a.get("vep_gene", "")
            adj, _ = edt.call_adjust(call, genes.get(g), af_max)
            rows.append((edt.score(tiers, a, af, genes.get(g), adj), key_, tiers))
        rows.sort(key=lambda r: -r[0])
        rank = next((i for i, r in enumerate(rows, 1) if r[1] == k), None)
        cv = clin_sp.get(k)
        sig = (cv or {}).get("clnsig", "") if cv else ""
        old = bool(cv) and edt.clinvar_tiers({"clnsig": sig, "clnsigconf": ""})[0] == ["T1a"]
        reason = ""
        if rank is None:
            tiers_all, af, inp, notes, af_max = edt.tiers_for(spike_call, sa, cv, genes, 0.001, 0.01)
            gene_ok = sa.get("vep_gene") in genes or any(g in genes for g in sa.get("all_genes", "").split(";") if g)
            reason = ("gene not in HPO gene set" if not gene_ok else
                      f"no tier: consequence {sa.get('consequence')}, AF {af_max}")
        out.append({"case_id": c["case_id"], "gene": c["gene"], "key": k, "gt": c["gt"], "rank": rank or "",
                    "tiers": ",".join(next((r[2] for r in rows if r[1] == k), [])), "reason": reason,
                    "union": len(rows), "old_logic": int(old), "clinvar": sig or ("none" if not cv else "?")})
        if n % 20 == 0:
            print(f"{n}/{len(cases)} {time.time()-t0:.0f}s", flush=True)

    cols = ["case_id", "gene", "key", "gt", "rank", "tiers", "union", "old_logic", "clinvar", "reason"]
    edt.write_tsv("spike_results.tsv", out, cols)

    N = len(out)
    rk = [int(r["rank"]) for r in out if r["rank"] != ""]
    def at(n_):
        return sum(1 for x in rk if x <= n_)
    lines = [f"cases {N}; causal variant in the candidate union: {len(rk)} ({100*len(rk)/N:.0f}%)",
             f"top1 {at(1)} ({100*at(1)/N:.0f}%), top5 {at(5)} ({100*at(5)/N:.0f}%), top10 {at(10)} ({100*at(10)/N:.0f}%), "
             f"top30 {at(30)} ({100*at(30)/N:.0f}%)",
             f"old logic (ClinVar aggregate P/LP only) would report: {sum(r['old_logic'] for r in out)} ({100*sum(r['old_logic'] for r in out)/N:.0f}%)",
             f"median union size {sorted(r['union'] for r in out if r['union'] != '')[len([1 for r in out if r['union'] != ''])//2]}"]
    by = collections.defaultdict(list)
    for r in out:
        by[r["clinvar"] if r["clinvar"] in ("Pathogenic", "Likely_pathogenic", "Pathogenic/Likely_pathogenic", "none") else
           ("Conflicting" if "onflicting" in r["clinvar"] else r["clinvar"])].append(r)
    lines.append("by ClinVar aggregate of the causal variant (n, in union, top10):")
    for k_, v in sorted(by.items(), key=lambda kv: -len(kv[1])):
        lines.append(f"  {k_:34s} n={len(v):3d} in-union={sum(1 for r in v if r['rank']!=''):3d} top10={sum(1 for r in v if r['rank']!='' and int(r['rank'])<=10):3d}")
    miss = collections.Counter(r["reason"].split(":")[0] for r in out if r["rank"] == "")
    lines.append(f"not in union - reasons: {dict(miss)}")
    open("spike_summary.txt", "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
