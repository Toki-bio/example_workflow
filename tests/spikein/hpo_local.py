"""Build hpo_genes.json (term -> genes, with ontology propagation) from hp.obo + genes_to_phenotype.txt."""
import collections, csv, json
parents = collections.defaultdict(set)
cur = None
for line in open("hp.obo", encoding="utf-8"):
    line = line.strip()
    if line == "[Term]":
        cur = None
    elif line.startswith("id: HP:"):
        cur = line[4:]
    elif line.startswith("is_a: HP:") and cur:
        parents[cur].add(line[6:16])
    elif line.startswith("alt_id: HP:") and cur:
        parents[line[8:]].add(cur)          # alt id behaves like the term itself (treated as child)
children = collections.defaultdict(set)
for c, ps in parents.items():
    for p in ps:
        children[p].add(c)
gene_terms = collections.defaultdict(set)
for r in csv.DictReader(open("genes_to_phenotype.txt", encoding="utf-8"), delimiter="\t"):
    gene_terms[r["hpo_id"]].add(r["gene_symbol"])
cases = list(csv.DictReader(open("spike_cases.tsv", encoding="utf-8"), delimiter="\t"))
terms = sorted({t for c in cases for t in c["hpo"].split()})
out, memo = {}, {}
def genes_of(t):
    if t in memo: return memo[t]
    seen, stack, genes = set(), [t], set()
    while stack:
        x = stack.pop()
        if x in seen: continue
        seen.add(x); genes |= gene_terms.get(x, set()); stack.extend(children.get(x, ()))
    memo[t] = genes; return genes
for t in terms:
    out[t] = sorted(genes_of(t))
json.dump(out, open("hpo_genes.json", "w"))
sizes = sorted(len(v) for v in out.values())
print("terms", len(terms), "empty", sum(1 for v in out.values() if not v), "median genes", sizes[len(sizes)//2], "max", sizes[-1])
