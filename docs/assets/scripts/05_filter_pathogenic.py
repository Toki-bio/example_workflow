#!/usr/bin/env python3
"""Extract ClinVar-flagged calls from an annotated VCF into JSONL (tiers T1a and T1b).

    T1a  ClinVar aggregate Pathogenic / Likely pathogenic
    T1b  ClinVar aggregate "Conflicting classifications" with at least one P/LP submission
         (CLNSIGCONF); the aggregate is not a verdict, so these must be reviewed, not dropped

Calls that fail the caller's FILTER are kept and marked ``"filter_pass": false`` (a filter flags
a call, it does not delete it).

Uses `pysam.VariantFile` (htslib bindings) for VCF parsing instead of hand-rolled text
splitting — the same C library bcftools itself is built on, so field typing (Number=.
multi-value INFO fields, FILTER semantics) is handled by the same code that validated the
VCF in the first place, rather than a second, independent parser that could disagree with
it on edge cases.

This is the CPU-pipeline equivalent of the original `ann.sh` / `ann1.sh` scripts, which used
`jq` to walk Illumina Nirvana's JSON output and select ClinVar significance matching
"pathogenic" (case-insensitive). Here the same selection rule is applied to the CLNSIG field
populated by `bcftools annotate` (or VEP's --custom ClinVar) in stage 04.

Whole ClinVar significance *terms* are matched (not substrings), so
``Conflicting_interpretations_of_pathogenicity`` is not mistaken for a pathogenic call; it is
handled explicitly as tier T1b when CLNSIGCONF shows a P/LP submission.

Usage:
    05_filter_pathogenic.py <annotated.vcf.gz> <sample_id> <case|control> <output.jsonl>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pysam

sys.path.insert(0, str(Path(__file__).resolve().parent))
from clinvar_sig import clinvar_tier, conflict_counts  # noqa: E402


def info_str(record: pysam.VariantRecord, key: str) -> str:
    """Normalize a pysam INFO value back to the raw comma-joined string form that
    clinvar_sig.is_pathogenic_clnsig() and the rest of this pipeline expect - pysam
    auto-splits Number=. INFO fields into tuples, which the original hand-rolled parser
    never did (it always saw the raw, un-split field text)."""
    try:
        value = record.info.get(key)
    except (ValueError, KeyError):
        # key not declared in the VCF header (e.g. ANN when snpEff was skipped): pysam raises
        # instead of returning None; treat as absent rather than skipping the whole record.
        return ""
    if value is None:
        return ""
    if isinstance(value, tuple):
        return ",".join(str(v) for v in value if v is not None)
    return str(value)


def extract_gene(record: pysam.VariantRecord) -> str:
    """Extract gene name from snpEff ANN, else ClinVar GENEINFO."""
    ann = info_str(record, "ANN")
    if ann:
        first_transcript = ann.split(",")[0]
        parts = first_transcript.split("|")
        if len(parts) > 3 and parts[3]:
            return parts[3]
    gi = info_str(record, "GENEINFO")
    if gi and gi != ".":
        return gi.split("|")[0].split(":")[0].strip()
    return ""


def is_pass_filter(record: pysam.VariantRecord) -> bool:
    filter_keys = list(record.filter.keys())
    return not filter_keys or filter_keys == ["PASS"]


def format_qual(qual: float | None) -> str:
    """VCF QUAL is stored as float32 in BCF/htslib; pysam surfaces it as a Python
    float (float64), which exposes float32->float64 conversion noise
    (e.g. 222.41 -> 222.41000366210938). Round back to the precision VCF text
    representations actually use so output matches the source file's text, not an
    artifact of the intermediate binary representation."""
    if qual is None:
        return "."
    return f"{qual:.6g}"


def main() -> None:
    if len(sys.argv) != 5:
        print(f"Usage: {sys.argv[0]} <annotated.vcf.gz> <sample_id> <case|control> <output.jsonl>",
              file=sys.stderr)
        sys.exit(1)

    vcf_path, sample_id, sample_type, out_path = sys.argv[1:5]

    n_total = 0
    n_pathogenic = 0
    n_skipped = 0
    with pysam.VariantFile(vcf_path) as vcf, open(out_path, "w") as out:
        for record in vcf:
            n_total += 1
            try:
                clnsig = info_str(record, "CLNSIG")
                clnsigconf = info_str(record, "CLNSIGCONF")
                tier = clinvar_tier(clnsig, clnsigconf)
                if not tier:
                    continue

                n_pathogenic += 1
                out_record = {
                    "sample_id": sample_id,
                    "sample_type": sample_type,
                    "chromosome": record.chrom,
                    "position": record.pos,
                    "refAllele": record.ref,
                    "altAlleles": list(record.alts) if record.alts else [],
                    "quality": format_qual(record.qual),
                    "filters": ";".join(record.filter.keys()) or ".",
                    "filter_pass": is_pass_filter(record),
                    "tier": tier,
                    "clinvar_conflict_counts": conflict_counts(clnsigconf),
                    "clinvar_id": str(record.id) if record.id else (info_str(record, "CLNVID") or "."),
                    "clinvar_significance": clnsig,
                    "clinvar_phenotypes": info_str(record, "CLNDN"),
                    "clinvar_review_status": info_str(record, "CLNREVSTAT"),
                    "gene": extract_gene(record),
                }
                out.write(json.dumps(out_record) + "\n")
            except (ValueError, KeyError) as exc:
                n_skipped += 1
                print(f"[{sample_id}] WARNING: skipping malformed record at "
                      f"{record.chrom}:{record.pos}: {exc}", file=sys.stderr)

    print(f"[{sample_id}] {n_pathogenic} ClinVar-flagged positions (T1a pathogenic/likely pathogenic, "
          f"T1b conflicting with P/LP submissions) out of {n_total} total records -> {out_path}",
          file=sys.stderr)
    if n_skipped:
        print(f"[{sample_id}] WARNING: skipped {n_skipped} malformed VCF records", file=sys.stderr)


if __name__ == "__main__":
    main()
