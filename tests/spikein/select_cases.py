"""Select solved single-variant cases from GA4GH phenopacket-store (release 0.1.27, hg38) for the spike-in test.

Rules (fixed seed, written down so the selection is reproducible):
  * exactly one genomic interpretation, status CAUSATIVE, with an hg38 vcfRecord (plain ACGT alleles)
  * allelic state heterozygous / homozygous / hemizygous (mapped to GT 0/1, 1/1, 1/1)
  * >= 3 observed (non-excluded) phenotypic features
  * at most one case per gene, random sample with seed 42
Output: spike_cases.tsv  (case_id, gene, key, ref/alt, gt, acmg, disease, hpo terms)
"""
import collections, csv, json, random, re, sys, zipfile

N = int(sys.argv[1]) if len(sys.argv) > 1 else 200
z = zipfile.ZipFile("all_phenopackets.zip")   # from https://github.com/monarch-initiative/phenopacket-store/releases
cases, why = [], collections.Counter()
for n in sorted(z.namelist()):
    if not n.endswith(".json"):
        continue
    d = json.loads(z.read(n))
    gis = [gi for it in d.get("interpretations", []) for gi in it.get("diagnosis", {}).get("genomicInterpretations", [])]
    if len(gis) != 1:
        why["not exactly one genomic interpretation"] += 1
        continue
    gi = gis[0]
    if gi.get("interpretationStatus") != "CAUSATIVE":
        why["not CAUSATIVE"] += 1
        continue
    vi = gi.get("variantInterpretation", {})
    vd = vi.get("variationDescriptor", {})
    vcf = vd.get("vcfRecord") or {}
    if vcf.get("genomeAssembly") not in ("hg38", "GRCh38"):
        why["no hg38 vcfRecord"] += 1
        continue
    ref, alt = vcf.get("ref", ""), vcf.get("alt", "")
    if not (re.fullmatch("[ACGT]+", ref) and re.fullmatch("[ACGT]+", alt)):
        why["non-ACGT alleles"] += 1
        continue
    state = (vd.get("allelicState") or {}).get("label", "").lower()
    gt = {"heterozygous": "0/1", "homozygous": "1/1", "hemizygous": "1/1"}.get(state)
    if gt is None:
        why["allelic state not het/hom/hemi"] += 1
        continue
    hpo = [f["type"]["id"] for f in d.get("phenotypicFeatures", []) if not f.get("excluded")]
    if len(hpo) < 3:
        why["< 3 observed features"] += 1
        continue
    chrom = vcf["chrom"][3:] if vcf["chrom"].startswith("chr") else vcf["chrom"]
    cases.append({"case_id": d["id"], "gene": (vd.get("geneContext") or {}).get("symbol", ""),
                  "key": f"{chrom}:{int(vcf['pos'])}:{ref}:{alt}", "gt": gt, "state": state,
                  "acmg": vi.get("acmgPathogenicityClassification", ""),
                  "disease": (d["interpretations"][0].get("diagnosis", {}).get("disease") or {}).get("label", ""),
                  "n_hpo": len(hpo), "hpo": " ".join(sorted(set(hpo)))})
print("eligible cases:", len(cases), dict(why))
random.seed(42)
by_gene = collections.defaultdict(list)
for c in cases:
    by_gene[c["gene"]].append(c)
one_per_gene = [random.choice(v) for g, v in sorted(by_gene.items()) if g]
random.shuffle(one_per_gene)
sel = sorted(one_per_gene[:N], key=lambda c: c["case_id"])
cols = ["case_id", "gene", "key", "gt", "state", "acmg", "disease", "n_hpo", "hpo"]
with open("spike_cases.tsv", "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=cols, delimiter="\t")
    w.writeheader()
    w.writerows(sel)
print(f"genes available {len(one_per_gene)}; selected {len(sel)}")
print(collections.Counter(c["state"] for c in sel), collections.Counter(c["acmg"] for c in sel))
print("indels:", sum(1 for c in sel if len(c["key"].split(":")[2]) != len(c["key"].split(":")[3]) or len(c["key"].split(":")[2]) > 1))
