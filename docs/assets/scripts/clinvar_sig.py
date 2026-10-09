"""Shared ClinVar CLNSIG parsing — avoid substring false positives.

ClinVar values like ``Conflicting_interpretations_of_pathogenicity`` contain the
substring "pathogenic" but are *not* pathogenic calls. Match whole significance
terms only (split on ``/``, ``,``, ``|``).

A ClinVar *aggregate* label is NOT a verdict. ClinVar sets "Conflicting classifications of
pathogenicity" as soon as one contributing submission falls in a different tier (P/LP vs VUS
vs B/LB) than the others, whatever its age or evidence. A filter that keeps only
Pathogenic/Likely_pathogenic therefore silently drops variants with, say, 9 P/LP submissions and
one old VUS. CLNSIGCONF carries the per-tier submission counts, so ``clinvar_tier`` reports:

    T1a  aggregate is Pathogenic / Likely_pathogenic
    T1b  aggregate is Conflicting, but at least one submission is P/LP (review the submissions)

A label may ADD a variant to review; it must never remove one.
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
    return {p.strip().strip("_").lower() for p in re.split(r"[,/|]", text) if p.strip()}


def is_pathogenic_clnsig(clnsig: str) -> bool:
    return bool(clnsig_terms(clnsig) & PATHOGENIC_TERMS)


_CONF_RE = re.compile(r"([A-Za-z_/ ]+?)\s*\((\d+)\)")


def conflict_counts(clnsigconf: str) -> dict:
    """Parse CLNSIGCONF, e.g. ``Pathogenic(7)|Likely_pathogenic(1)|Uncertain_significance(1)``,
    into {"pathogenic": 7, "likely_pathogenic": 1, "uncertain_significance": 1}."""
    out: dict = {}
    if not clnsigconf or clnsigconf == ".":
        return out
    for term, n in _CONF_RE.findall(clnsigconf.replace(" ", "_")):
        key = term.strip("_|,; ").lower()
        if key:
            out[key] = out.get(key, 0) + int(n)
    return out


def is_conflicting(clnsig: str) -> bool:
    return "conflicting" in (clnsig or "").lower()


def conflicting_with_pathogenic(clnsig: str, clnsigconf: str) -> bool:
    if not is_conflicting(clnsig):
        return False
    for term, n in conflict_counts(clnsigconf).items():
        if n and {t for t in re.split(r"[/]", term) if t} & PATHOGENIC_TERMS:
            return True
    return False


def clinvar_tier(clnsig: str, clnsigconf: str = "") -> str:
    """T1a / T1b / "" (see module docstring)."""
    if is_pathogenic_clnsig(clnsig):
        return "T1a"
    if conflicting_with_pathogenic(clnsig, clnsigconf):
        return "T1b"
    return ""


def clinical_significance(clnsig: str, clnsigconf: str = "") -> str:
    if not clnsig or clnsig == ".":
        return "unknown"
    terms = clnsig_terms(clnsig)
    if clnsigconf and is_conflicting(clnsig):
        return "conflicting_pathogenic" if conflicting_with_pathogenic(clnsig, clnsigconf) else "conflicting"
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
