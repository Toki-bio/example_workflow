"""End-to-end check of the ClinVar tier logic through stages 05 -> 07 on a tiny annotated VCF.
Needs pysam (stage 05); skipped when it is not installed. Run:  python -m unittest discover -s tests -v"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

try:
    import pysam  # noqa: F401
    HAVE_PYSAM = True
except ImportError:
    HAVE_PYSAM = False

PIPE = Path(__file__).resolve().parent.parent / "pipeline"
CONF = "Conflicting_classifications_of_pathogenicity"
HEADER = """##fileformat=VCFv4.2
##contig=<ID=chr1,length=1000000>
##FILTER=<ID=LowQual,Description="low quality">
##INFO=<ID=CLNSIG,Number=.,Type=String,Description="x">
##INFO=<ID=CLNSIGCONF,Number=.,Type=String,Description="x">
##INFO=<ID=CLNDN,Number=.,Type=String,Description="x">
##INFO=<ID=CLNVID,Number=1,Type=String,Description="x">
##INFO=<ID=GENEINFO,Number=1,Type=String,Description="x">
##FORMAT=<ID=GT,Number=1,Type=String,Description="x">
#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tS1
"""
ROWS = [
    # pos, filter, CLNSIG, CLNSIGCONF, gene
    (100, "PASS", "Pathogenic", "", "PANELGENE"),                                              # T1a
    (200, "PASS", CONF, "Pathogenic(7)|Likely_pathogenic(1)|Uncertain_significance(1)", "PANELGENE"),  # T1b
    (300, "PASS", CONF, "Uncertain_significance(2)|Likely_benign(1)", "PANELGENE"),            # not a tier
    (400, "PASS", "Benign", "", "PANELGENE"),                                                  # benign inside a panel gene
    (500, "LowQual", "Pathogenic", "", "OTHERGENE"),                                           # T1a, failed FILTER
    (600, "PASS", "Benign", "", "OTHERGENE"),                                                  # benign outside the panel
]


def make_vcf(path):
    lines = [HEADER.rstrip("\n")]
    for pos, filt, sig, conf, gene in ROWS:
        info = f"CLNSIG={sig};CLNDN=Some_disease;CLNVID={pos};GENEINFO={gene}:1"
        if conf:
            info += f";CLNSIGCONF={conf}"
        lines.append(f"chr1\t{pos}\t.\tA\tG\t100\t{filt}\t{info}\tGT\t0/1")
    Path(path).write_text("\n".join(lines) + "\n")


@unittest.skipUnless(HAVE_PYSAM, "pysam not installed")
class TestTierPipeline(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.vcf = self.tmp / "s1.vcf"
        make_vcf(self.vcf)

    def test_stage05_tiers_and_nothing_dropped_by_filter(self):
        out = self.tmp / "s1.jsonl"
        subprocess.run([sys.executable, str(PIPE / "05_filter_pathogenic.py"), str(self.vcf), "s1", "case", str(out)],
                       check=True, capture_output=True)
        recs = {r["position"]: r for r in map(json.loads, out.read_text().splitlines())}
        self.assertEqual(set(recs), {100, 200, 500})                 # 300/400/600 are not ClinVar tiers
        self.assertEqual(recs[100]["tier"], "T1a")
        self.assertEqual(recs[200]["tier"], "T1b")
        self.assertEqual(recs[200]["clinvar_conflict_counts"]["pathogenic"], 7)
        self.assertTrue(recs[100]["filter_pass"])
        self.assertFalse(recs[500]["filter_pass"])                    # kept, flagged

    def test_stage07_report_keeps_panel_gene_benign_and_failed_filter(self):
        panel = self.tmp / "panel.txt"
        panel.write_text("PANELGENE\n")
        html = self.tmp / "r.html"
        subprocess.run([sys.executable, str(PIPE / "07_generate_report.py"), str(self.vcf), "s1", str(panel), str(html)],
                       check=True, capture_output=True)
        text = html.read_text()
        for pos in ("chr1:100", "chr1:200", "chr1:500", "chr1:400"):   # P, conflicting+P, failed-filter P, panel benign
            self.assertIn(pos, text)
        self.assertNotIn("chr1:600", text)                              # benign outside the panel stays out
        self.assertIn("Conflicting (has P/LP submissions)", text)
        self.assertIn("Scope and limits", text)


if __name__ == "__main__":
    unittest.main()
