"""Shared ClinVar CLNSIG parsing — avoid substring false positives.

ClinVar values like ``Conflicting_interpretations_of_pathogenicity`` contain the
substring "pathogenic" but are *not* pathogenic calls. Match whole significance
terms only (split on ``/``, ``,``, ``|``).
"""
from __future__ import annotations

import re

PATHOGENIC_TERMS = {
    "pathogenic",
    "likely_pathogenic",
    "pathogenic_low_penetrance",
    "likely_pathogenic_low_penetrance",
}
BENIGN_TERMS = {
    "benign",
    "likely_benign",
}


def clnsig_terms(clnsig: str) -> set[str]:
    if not clnsig or clnsig == ".":
        return set()
    text = clnsig.replace(" ", "_")
    return {p.strip().lower() for p in re.split(r"[,/|]", text) if p.strip()}


def is_pathogenic_clnsig(clnsig: str) -> bool:
    return bool(clnsig_terms(clnsig) & PATHOGENIC_TERMS)


def clinical_significance(clnsig: str) -> str:
    if not clnsig or clnsig == ".":
        return "unknown"
    terms = clnsig_terms(clnsig)
    if "pathogenic" in terms or "pathogenic_low_penetrance" in terms:
        return "pathogenic"
    if "likely_pathogenic" in terms or "likely_pathogenic_low_penetrance" in terms:
        return "likely_pathogenic"
    if "benign" in terms:
        return "benign"
    if "likely_benign" in terms:
        return "likely_benign"
    joined = " ".join(terms)
    if "uncertain" in joined or "uncertain_significance" in terms:
        return "uncertain"
    return "unknown"
