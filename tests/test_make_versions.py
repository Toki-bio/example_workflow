"""make_versions.py must read versions from the files, not from a README, and must fail when it cannot."""
import gzip
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "pipeline" / "refs" / "make_versions.py"


def build(root, clinvar_date="2025-07-15", with_readme_lie=True):
    def w(rel, text, gz=False):
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        if gz:
            with gzip.open(p, "wt") as f:
                f.write(text)
        else:
            p.write_text(text)
    w("clinvar/clinvar.vcf.gz", f"##fileformat=VCFv4.1\n##fileDate={clinvar_date}\n##reference=GRCh38\n#CHROM\n", gz=True)
    w("clinvar/clinvar.vcf.gz.tbi", "x")
    w("clinvar/variant_summary.txt.gz", "#AlleleID\n", gz=True)
    w("clinvar/submission_summary.txt.gz", "#VariationID\n", gz=True)
    w("hpo/hp.obo", "format-version: 1.2\ndata-version: hp/releases/2026-09-01\n")
    w("hpo/genes_to_phenotype.txt", "x\n")
    w("hpo/phenotype.hpoa", "#description: x\n#version: 2026-09-02\n#hpo-version: v\n")
    for tag in ("uk", "au"):
        w(f"panelapp/panelapp_{tag}.json", json.dumps({"fetched": "2026-10-08", "source": "s", "panels": [{"id": 1, "name": "Epilepsy", "version": "9.9"}]}))
    w("gene_disease/clingen_gene_validity.csv", '"CLINGEN GENE DISEASE VALIDITY CURATIONS","",""\n"FILE CREATED: 2026-10-08","",""\n')
    w("gene_disease/G2P_DD_panel.csv", "g2p id,gene\n")
    w("gnomad/gnomad_v4.1_constraint.tsv", "gene\n")
    w("nirvana/config/download_summary.json", json.dumps({"assembly": "GRCh38", "timestampEnd": "t", "errors": [], "files": [
        {"fileName": "ClinVar_20260804.nsa", "dataSource": "clinvar", "annotationType": "SmallVariant", "version": "20260804",
         "localSize": 10, "md5Hash": "abc", "status": "UpToDate"}]}))
    if with_readme_lie:
        w("clinvar/README.md", "ClinVar release 2024-09-02\n")


class TestMakeVersions(unittest.TestCase):
    def run_it(self, root):
        return subprocess.run([sys.executable, str(SCRIPT), str(root)], capture_output=True, text=True)

    def test_version_comes_from_the_file_header_not_a_readme(self):
        root = Path(tempfile.mkdtemp())
        build(root)
        r = self.run_it(root)
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        v = json.loads((root / "versions.json").read_text())
        self.assertEqual(v["sources"]["clinvar_vcf"]["release_fileDate"], "2025-07-15")
        self.assertNotIn("2024-09-02", json.dumps(v))
        self.assertEqual(v["sources"]["hpo_ontology"]["release"], "hp/releases/2026-09-01")
        self.assertEqual(v["sources"]["panelapp_uk"]["fetched"], "2026-10-08")
        self.assertTrue((root / "README.md").exists() and (root / "SHA256SUMS").exists())

    def test_unreadable_version_fails_loudly(self):
        root = Path(tempfile.mkdtemp())
        build(root)
        with gzip.open(root / "clinvar" / "clinvar.vcf.gz", "wt") as f:
            f.write("##fileformat=VCFv4.1\n#CHROM\n")        # no ##fileDate
        r = self.run_it(root)
        self.assertNotEqual(r.returncode, 0)
        v = json.loads((root / "versions.json").read_text())
        self.assertTrue(any("fileDate" in p for p in v["problems"]))
        self.assertEqual(v["sources"]["clinvar_vcf"]["release_fileDate"], "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
