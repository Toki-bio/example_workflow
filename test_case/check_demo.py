#!/usr/bin/env python3
"""Sanity-check the demo pipeline output: case1 must show the spiked MYBPC3 pathogenic
variant, control1 must not, and nothing else pathogenic should show up. Used both
interactively and by the CI workflow.

Usage: check_demo.py <results_dir>
"""
import json
import sys
from pathlib import Path

EXPECTED_CONTIG = "demo_chr11_mybpc3"
EXPECTED_POS = 12292
# Must match MYBPC3_VARIANT_REF/ALT in simulate_reads.py -- a REF/ALT mismatch here
# (e.g. an allele-normalization bug) would otherwise pass silently.
EXPECTED_REF = "G"
EXPECTED_ALT = "A"


def fail(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def main():
    results_dir = sys.argv[1] if len(sys.argv) > 1 else "results"
    agg_path = f"{results_dir}/aggregated_pathogenic_variants.json"

    try:
        with open(agg_path) as fh:
            aggregated = json.load(fh)
    except FileNotFoundError:
        print(
            f"ERROR: {agg_path} not found.\n"
            "The demo did not finish. Fix the error from bash run_demo.sh, then re-run:\n"
            "  bash run_demo.sh\n"
            "  python3 check_demo.py results",
            file=sys.stderr,
        )
        sys.exit(1)

    hits = [
        v for v in aggregated
        if v["chr"].lower() == EXPECTED_CONTIG and v["pos"] == EXPECTED_POS
    ]

    if not hits:
        fail(f"Expected pathogenic variant at {EXPECTED_CONTIG}:{EXPECTED_POS} not found in {agg_path}")
    variant = hits[0]

    if variant["ref"] != EXPECTED_REF or EXPECTED_ALT not in variant["alt"]:
        fail(f"Expected {EXPECTED_REF}>{EXPECTED_ALT}, got ref={variant['ref']!r} alt={variant['alt']!r}: {variant}")
    if "case1" not in variant["case_samples"]:
        fail(f"case1 should carry the pathogenic variant: {variant}")
    if "control1" in variant["control_samples"]:
        fail(f"control1 should NOT carry the pathogenic variant: {variant}")
    if "pathogenic" not in variant["clinvar_significance"].lower():
        fail(f"Expected Pathogenic significance: {variant}")

    other_hits = [v for v in aggregated if v is not variant]
    if other_hits:
        fail(
            f"Expected exactly one pathogenic variant in the demo output, found "
            f"{len(aggregated)}. Unexpected extra pathogenic call(s) (false positives?): "
            f"{other_hits}"
        )

    report_path = Path(results_dir) / "case1.report.html"
    try:
        report_html = report_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        fail(f"{report_path} not found -- 07_generate_report.py did not produce case1's report.")
    if "MYBPC3" not in report_html or str(EXPECTED_POS) not in report_html:
        fail(
            f"{report_path} exists but does not appear to mention MYBPC3 / position "
            f"{EXPECTED_POS} -- report content check failed."
        )

    control_report_path = Path(results_dir) / "control1.report.html"
    if not control_report_path.exists():
        fail(f"{control_report_path} not found -- 07_generate_report.py did not produce control1's report.")

    print("OK: case1 carries the spiked MYBPC3 p.Arg502Trp pathogenic variant (and only that "
          "one); control1 does not. Both HTML reports were generated and case1's mentions MYBPC3.")
    print(json.dumps(variant, indent=2))


if __name__ == "__main__":
    main()
