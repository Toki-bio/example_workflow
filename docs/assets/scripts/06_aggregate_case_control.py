#!/usr/bin/env python3
"""Aggregate per-sample pathogenic-variant JSONL files into a case-vs-control summary.

Equivalent of the `jq -s 'group_by(...)'` aggregation step in the original `ann.sh`, which
grouped every pathogenic ClinVar call by (chromosome, position, refAllele, altAlleles) and
counted how many case vs. control samples carried each variant.

Usage:
    06_aggregate_case_control.py <jsonl_dir_glob_pattern...> <output.json>

Example:
    06_aggregate_case_control.py 'results/*.pathogenic.jsonl' results/aggregated_pathogenic_variants.json
"""
import glob
import json
import sys
from collections import defaultdict


def variant_key(rec):
    return (rec["chromosome"], rec["position"], rec["refAllele"], tuple(rec["altAlleles"]))


def main():
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <jsonl_glob> <output.json>", file=sys.stderr)
        sys.exit(1)

    jsonl_glob, out_path = sys.argv[1:3]
    groups = defaultdict(list)

    for path in sorted(glob.glob(jsonl_glob)):
        with open(path) as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                groups[variant_key(rec)].append(rec)

    aggregated = []
    for key, records in groups.items():
        chrom, pos, ref, alts = key
        case_samples = sorted({r["sample_id"] for r in records if r["sample_type"] == "case"})
        control_samples = sorted({r["sample_id"] for r in records if r["sample_type"] == "control"})
        aggregated.append({
            "chr": chrom,
            "pos": pos,
            "ref": ref,
            "alt": list(alts),
            "total_count": len(records),
            "case_count": len(case_samples),
            "control_count": len(control_samples),
            "case_samples": case_samples,
            "control_samples": control_samples,
            "gene": records[0].get("gene", ""),
            "clinvar_significance": records[0].get("clinvar_significance", ""),
        })

    aggregated.sort(key=lambda r: r["total_count"], reverse=True)

    with open(out_path, "w") as out:
        json.dump(aggregated, out, indent=2)

    print(f"{len(aggregated)} distinct pathogenic variants aggregated -> {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
