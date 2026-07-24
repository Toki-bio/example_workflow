#!/usr/bin/env python3
"""Sanity-check the demo pipeline output: case1 must show the spiked MYBPC3 pathogenic
variant, control1 must not. Used both interactively and by the CI workflow.

Usage: check_demo.py <results_dir>
"""
import json
import sys

EXPECTED_CONTIG = "demo_chr11_mybpc3"
EXPECTED_POS = 12292


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

    if "case1" not in variant["case_samples"]:
        fail(f"case1 should carry the pathogenic variant: {variant}")
    if "control1" in variant["control_samples"]:
        fail(f"control1 should NOT carry the pathogenic variant: {variant}")
    if "pathogenic" not in variant["clinvar_significance"].lower():
        fail(f"Expected Pathogenic significance: {variant}")

    print("OK: case1 carries the spiked MYBPC3 p.Arg502Trp pathogenic variant; control1 does not.")
    print(json.dumps(variant, indent=2))


if __name__ == "__main__":
    main()
