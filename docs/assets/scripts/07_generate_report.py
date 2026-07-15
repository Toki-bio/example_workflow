#!/usr/bin/env python3
"""Generate a self-contained clinical HTML report for one sample.

Adapted from the original DRAGEN-pipeline `single_sample_report.py`, which read Illumina
Nirvana JSON; this version reads the snpEff + ClinVar annotated VCF produced by stage 04 and
keeps the same panel-based clinical filtering logic (panel is a config, not a fixed gene list --
see panels/README.md):

  - Pathogenic / Likely pathogenic ClinVar calls: always included
  - Uncertain significance (VUS): included
  - Any variant inside a panel gene (unless Benign/Likely benign): included
  - HIGH-impact variants (frameshift, stop-gain, etc.), anywhere: included
  - Everything else: excluded

Usage:
    07_generate_report.py <annotated.vcf.gz> <sample_id> <panel_genes.txt> <output.html> [panel_name]
"""
import gzip
import html
import json
import re
import sys

PATHOGENIC_RE = re.compile(r"pathogenic", re.IGNORECASE)
BENIGN_RE = re.compile(r"benign", re.IGNORECASE)
HIGH_IMPACT_CONSEQUENCES = {
    "frameshift_variant", "stop_gained", "stop_lost", "start_lost",
    "splice_acceptor_variant", "splice_donor_variant", "transcript_ablation",
}


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


def parse_ann(info):
    """snpEff ANN field: Allele|Annotation|Impact|Gene_Name|Gene_ID|Feature_Type|Feature_ID|..."""
    ann = info.get("ANN", "")
    if not ann:
        return {"gene": "", "consequence": "", "impact": "", "hgvsc": "", "hgvsp": ""}
    first = ann.split(",")[0].split("|")
    first += [""] * (11 - len(first))
    return {
        "gene": first[3],
        "consequence": first[1],
        "impact": first[2],
        "hgvsc": first[9],
        "hgvsp": first[10],
    }


def load_panel(panel_path):
    with open(panel_path) as fh:
        return {line.strip().upper() for line in fh if line.strip()}


def clinical_significance(clnsig):
    if not clnsig:
        return "unknown"
    if PATHOGENIC_RE.search(clnsig):
        return "likely_pathogenic" if "likely" in clnsig.lower() else "pathogenic"
    if BENIGN_RE.search(clnsig):
        return "likely_benign" if "likely" in clnsig.lower() else "benign"
    if "uncertain" in clnsig.lower():
        return "uncertain"
    return "unknown"


SIG_STYLE = {
    "pathogenic": ("Pathogenic", "#d9534f"),
    "likely_pathogenic": ("Likely Pathogenic", "#f0ad4e"),
    "uncertain": ("VUS", "#5bc0de"),
    "likely_benign": ("Likely Benign", "#5cb85c"),
    "benign": ("Benign", "#4cae4c"),
    "unknown": ("Unknown", "#777777"),
}

IMPACT_STYLE = {
    "HIGH": "#d9534f", "MODERATE": "#f0ad4e", "LOW": "#5bc0de", "MODIFIER": "#aaaaaa",
}


def should_include(gene, impact, sig, panel_genes):
    if sig in ("benign", "likely_benign"):
        return gene.upper() in panel_genes and False  # never show benign panel hits either
    if sig in ("pathogenic", "likely_pathogenic", "uncertain"):
        return True
    if gene.upper() in panel_genes:
        return True
    if impact == "HIGH":
        return True
    return False


def build_rows(vcf_path, panel_genes):
    rows = []
    with open_vcf(vcf_path) as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            fields = line.rstrip("\n").split("\t")
            chrom, pos, variant_id, ref, alt, qual, filt, info_str = fields[:8]
            info = parse_info(info_str)
            ann = parse_ann(info)
            clnsig = info.get("CLNSIG", "")
            sig = clinical_significance(clnsig)

            if not should_include(ann["gene"], ann["impact"], sig, panel_genes):
                continue

            genotype = ""
            if len(fields) > 9:
                sample_fields = fields[9].split(":")
                genotype = sample_fields[0] if sample_fields else ""

            rows.append({
                "gene": ann["gene"] or "Unknown",
                "in_panel": ann["gene"].upper() in panel_genes,
                "variant": ann["hgvsp"] or ann["hgvsc"] or f"{ref}>{alt}",
                "chr_pos": f"{chrom}:{pos}",
                "consequence": ann["consequence"],
                "impact": ann["impact"] or "MODIFIER",
                "significance": sig,
                "clinvar_id": variant_id if variant_id != "." else "",
                "clinvar_phenotypes": info.get("CLNDN", "").replace("_", " "),
                "genotype": genotype,
                "quality": qual,
                "filters": filt,
            })
    return rows


ROW_TEMPLATE = """<tr class="{row_class}">
  <td>{gene}{panel_badge}</td>
  <td>{variant}</td>
  <td>{chr_pos}</td>
  <td>{consequence}</td>
  <td><span class="badge" style="background:{impact_color}">{impact}</span></td>
  <td><span class="badge" style="background:{sig_color}">{sig_label}</span></td>
  <td>{genotype}</td>
  <td>{quality}</td>
  <td>{filters}</td>
  <td>{clinvar_link}</td>
  <td>{phenotypes}</td>
</tr>"""

HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>{panel_name} panel report -- {sample_id}</title>
<style>
  body {{ font-family: -apple-system, Segoe UI, Arial, sans-serif; margin: 2rem; color: #222; }}
  h1 {{ font-size: 1.4rem; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 0.85rem; }}
  th, td {{ border: 1px solid #ddd; padding: 6px 8px; text-align: left; }}
  th {{ background: #f4f4f4; cursor: pointer; position: sticky; top: 0; }}
  tr.panel-gene {{ background: #f5eefc; }}
  .badge {{ color: white; border-radius: 4px; padding: 2px 6px; font-size: 0.75rem; }}
  .panel-tag {{ color: #6c3fc5; font-weight: bold; font-size: 0.7rem; margin-left: 4px; }}
  #search {{ margin-bottom: 1rem; padding: 6px; width: 300px; }}
  .meta {{ color: #666; font-size: 0.85rem; margin-bottom: 1rem; }}
</style>
</head>
<body>
<h1>{panel_name} panel report</h1>
<div class="meta">
  Sample: <strong>{sample_id}</strong> &middot;
  Variants shown: {n_rows} (clinical filter: pathogenic/likely-pathogenic/VUS, panel genes, HIGH impact) &middot;
  Generated by the open-source replacement pipeline (see docs/DRAGEN_TO_OSS_MAPPING.md)
</div>
<input id="search" type="text" placeholder="Filter by gene, variant, significance...">
<table id="report">
<thead>
<tr>
  <th>Gene</th><th>Variant</th><th>Chr:Pos</th><th>Consequence</th><th>Impact</th>
  <th>Significance</th><th>Genotype</th><th>Quality</th><th>Filters</th><th>ClinVar</th><th>Phenotypes</th>
</tr>
</thead>
<tbody>
{rows}
</tbody>
</table>
<script>
document.getElementById('search').addEventListener('input', function (e) {{
  var q = e.target.value.toLowerCase();
  document.querySelectorAll('#report tbody tr').forEach(function (tr) {{
    tr.style.display = tr.textContent.toLowerCase().includes(q) ? '' : 'none';
  }});
}});
document.querySelectorAll('#report th').forEach(function (th, idx) {{
  th.addEventListener('click', function () {{
    var tbody = document.querySelector('#report tbody');
    var rows = Array.from(tbody.querySelectorAll('tr'));
    var asc = th.dataset.asc !== 'true';
    rows.sort(function (a, b) {{
      var av = a.children[idx].textContent.trim();
      var bv = b.children[idx].textContent.trim();
      return asc ? av.localeCompare(bv) : bv.localeCompare(av);
    }});
    th.dataset.asc = asc;
    rows.forEach(function (r) {{ tbody.appendChild(r); }});
  }});
}});
</script>
</body>
</html>
"""


def render_html(sample_id, rows, panel_name):
    row_html = []
    for r in rows:
        sig_label, sig_color = SIG_STYLE.get(r["significance"], SIG_STYLE["unknown"])
        impact_color = IMPACT_STYLE.get(r["impact"], "#aaaaaa")
        clinvar_link = (
            f'<a href="https://www.ncbi.nlm.nih.gov/clinvar/variation/{html.escape(r["clinvar_id"])}" target="_blank">{html.escape(r["clinvar_id"])}</a>'
            if r["clinvar_id"] else ""
        )
        row_html.append(ROW_TEMPLATE.format(
            row_class="panel-gene" if r["in_panel"] else "",
            gene=html.escape(r["gene"]),
            panel_badge='<span class="panel-tag">PANEL</span>' if r["in_panel"] else "",
            variant=html.escape(r["variant"]),
            chr_pos=html.escape(r["chr_pos"]),
            consequence=html.escape(r["consequence"]),
            impact=html.escape(r["impact"]),
            impact_color=impact_color,
            sig_label=sig_label,
            sig_color=sig_color,
            genotype=html.escape(r["genotype"]),
            quality=html.escape(r["quality"]),
            filters=html.escape(r["filters"]),
            clinvar_link=clinvar_link,
            phenotypes=html.escape(r["clinvar_phenotypes"]),
        ))
    return HTML_TEMPLATE.format(
        sample_id=html.escape(sample_id),
        panel_name=html.escape(panel_name),
        n_rows=len(rows),
        rows="\n".join(row_html),
    )


def main():
    if len(sys.argv) not in (5, 6):
        print(f"Usage: {sys.argv[0]} <annotated.vcf.gz> <sample_id> <panel_genes.txt> <output.html> [panel_name]",
              file=sys.stderr)
        sys.exit(1)

    vcf_path, sample_id, panel_path, out_path = sys.argv[1:5]
    panel_name = sys.argv[5] if len(sys.argv) == 6 else "Gene panel"
    panel_genes = load_panel(panel_path)
    rows = build_rows(vcf_path, panel_genes)
    rows.sort(key=lambda r: (r["significance"] not in ("pathogenic", "likely_pathogenic"), not r["in_panel"]))

    with open(out_path, "w") as out:
        out.write(render_html(sample_id, rows, panel_name))

    print(f"[{sample_id}] {len(rows)} clinically-relevant variants -> {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
