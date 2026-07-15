#!/usr/bin/env python3
"""Extract ClinVar Pathogenic / Likely pathogenic calls from an annotated VCF into JSONL.

This is the CPU-pipeline equivalent of the original `ann.sh` / `ann1.sh` scripts, which used
`jq` to walk Illumina Nirvana's JSON output and select ClinVar significance matching
"pathogenic" (case-insensitive). Here the same selection rule is applied to the CLNSIG field
populated by `bcftools annotate` (or VEP's --custom ClinVar) in stage 04.

Usage:
    05_filter_pathogenic.py <annotated.vcf.gz> <sample_id> <case|control> <output.jsonl>
"""
import gzip
import json
import re
import sys

PATHOGENIC_RE = re.compile(r"pathogenic", re.IGNORECASE)


def open_vcf(path):
    opener = gzip.open if path.endswith(".gz") else open
    return opener(path, "rt")


def parse_info(info_field):
    info = {}
    for kv in info_field.split(";"):
        if "=" in kv:
            k, v = kv.split("=", 1)
            info[k] = v
        else:
            info[kv] = True
    return info


def main():
    if len(sys.argv) != 5:
        print(f"Usage: {sys.argv[0]} <annotated.vcf.gz> <sample_id> <case|control> <output.jsonl>",
              file=sys.stderr)
        sys.exit(1)

    vcf_path, sample_id, sample_type, out_path = sys.argv[1:5]

    n_total = 0
    n_pathogenic = 0
    with open_vcf(vcf_path) as fh, open(out_path, "w") as out:
        for line in fh:
            if line.startswith("#"):
                continue
            n_total += 1
            fields = line.rstrip("\n").split("\t")
            chrom, pos, variant_id, ref, alt, qual, filt, info_str = fields[:8]
            info = parse_info(info_str)

            clnsig = info.get("CLNSIG", "")
            if not PATHOGENIC_RE.search(clnsig):
                continue

            n_pathogenic += 1
            record = {
                "sample_id": sample_id,
                "sample_type": sample_type,
                "chromosome": chrom,
                "position": int(pos),
                "refAllele": ref,
                "altAlleles": alt.split(","),
                "quality": qual,
                "filters": filt,
                "clinvar_id": variant_id if variant_id != "." else info.get("CLNVID", "."),
                "clinvar_significance": clnsig,
                "clinvar_phenotypes": info.get("CLNDN", ""),
                "clinvar_review_status": info.get("CLNREVSTAT", ""),
                "gene": info.get("ANN", "").split("|")[3] if "ANN" in info else info.get("GENEINFO", "").split(":")[0],
            }
            out.write(json.dumps(record) + "\n")

    print(f"[{sample_id}] {n_pathogenic} pathogenic/likely-pathogenic positions "
          f"out of {n_total} total records -> {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
