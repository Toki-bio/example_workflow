"""Offline unit tests for edt.py (no network). Run:  python -X utf8 -m unittest discover -s tests"""
import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pipeline", "triage"))
import edt


class TestClinvarTiers(unittest.TestCase):
    def test_pathogenic(self):
        self.assertEqual(edt.clinvar_tiers({"clnsig": "Pathogenic", "clnsigconf": ""})[0], ["T1a"])
        self.assertEqual(edt.clinvar_tiers({"clnsig": "Pathogenic/Likely_pathogenic", "clnsigconf": ""})[0], ["T1a"])

    def test_conflicting_with_pathogenic_submissions_is_T1b_not_T1a(self):
        # the substring trap: "Conflicting_classifications_of_pathogenicity" contains "pathogenic"
        cv = {"clnsig": "Conflicting_classifications_of_pathogenicity",
              "clnsigconf": "Pathogenic(7)|Likely_pathogenic(1)|Uncertain_significance(1)"}
        self.assertEqual(edt.clinvar_tiers(cv)[0], ["T1b"])

    def test_conflicting_without_pathogenic_is_no_tier(self):
        cv = {"clnsig": "Conflicting_classifications_of_pathogenicity",
              "clnsigconf": "Uncertain_significance(2)|Likely_benign(1)"}
        self.assertEqual(edt.clinvar_tiers(cv)[0], [])

    def test_benign_is_flagged_not_excluded(self):
        t, notes = edt.clinvar_tiers({"clnsig": "Benign", "clnsigconf": ""})
        self.assertEqual(t, [])
        self.assertTrue(any("NOT excluded" in n for n in notes))


class TestTiersFor(unittest.TestCase):
    genes = {"GENE1": {"gene": "GENE1"}}

    def ann(self, **kw):
        d = {"vep_status": "ok", "vep_gene": "GENE1", "all_genes": "GENE1",
             "any_protein_altering": "missense_variant", "gnomade_af": "", "gnomadg_af": ""}
        d.update(kw)
        return d

    def test_benign_label_does_not_remove_t2(self):
        t, af, inp, notes, _ = edt.tiers_for({"gene_span": "GENE1"}, self.ann(), {"clnsig": "Benign", "clnsigconf": ""},
                                             self.genes, 0.001, 0.01)
        self.assertIn("T2", t)
        self.assertTrue(inp)

    def test_unannotated_variant_in_pheno_gene_is_kept(self):
        t, *_ = edt.tiers_for({"gene_span": "GENE1"}, {"vep_status": "NOT_ANNOTATED_KEEP"}, None, self.genes, 0.001, 0.01)
        self.assertIn("T2", t)

    def test_discordant_exome_genome_uses_lower_af_and_flags(self):
        t, af, inp, notes, af_max = edt.tiers_for({"gene_span": "GENE1"}, self.ann(gnomade_af="1e-5", gnomadg_af="0.016"),
                                                  None, self.genes, 0.001, 0.01)
        self.assertIn("T2", t)
        self.assertEqual(af_max, 0.016)
        self.assertTrue(any("discordant" in n for n in notes))

    def test_common_variant_not_T2(self):
        t, *_ = edt.tiers_for({"gene_span": "GENE1"}, self.ann(gnomade_af="0.05", gnomadg_af="0.05"), None, self.genes, 0.001, 0.01)
        self.assertNotIn("T2", t)


class TestScoringAdjust(unittest.TestCase):
    def test_single_het_in_recessive_gene_is_penalised(self):
        adj, notes = edt.call_adjust({"gt": "0/1", "ad": "30,30", "dp": "60", "qual": "500"}, {"moi": "BIALLELIC, autosomal"}, 1e-5)
        self.assertLess(adj, 0)
        self.assertTrue(any("carrier" in n for n in notes))

    def test_dominant_het_gets_bonus(self):
        adj, _ = edt.call_adjust({"gt": "0/1", "ad": "30,30", "dp": "60", "qual": "500"}, {"moi": "MONOALLELIC, autosomal"}, 0)
        self.assertGreater(adj, 0)

    def test_low_allele_balance_flagged(self):
        adj, notes = edt.call_adjust({"gt": "0/1", "ad": "88,12", "dp": "100", "qual": "500"}, {"moi": "MONOALLELIC"}, 0)
        self.assertTrue(any("allele balance" in n for n in notes))

    def test_common_variant_demoted_but_kept(self):
        adj, notes = edt.call_adjust({"gt": "0/1", "ad": "10,10", "dp": "20", "qual": "100"}, {}, 0.016)
        self.assertLessEqual(adj, -4)
        self.assertTrue(any("COMMON" in n for n in notes))


class TestVepSummary(unittest.TestCase):
    def test_frequency_uses_only_the_samples_alt_allele(self):
        rec = {"input": "1 100 . A G . . .", "most_severe_consequence": "missense_variant",
               "transcript_consequences": [{"gene_symbol": "G", "biotype": "protein_coding", "consequence_terms": ["missense_variant"], "impact": "MODERATE"}],
               "colocated_variants": [{"id": "rs1", "frequencies": {"G": {"gnomade": 1e-5}, "T": {"gnomade": 0.3}}}]}
        self.assertEqual(edt.summarise_vep(rec)["gnomade_af"], 1e-5)


class TestNirvana(unittest.TestCase):
    def _write(self, positions):
        import gzip, json, tempfile
        path = os.path.join(tempfile.mkdtemp(), "t.json.gz")
        with gzip.open(path, "wt", encoding="utf-8") as f:
            json.dump({"header": {}, "positions": positions}, f)
        return path

    def test_snv_indel_keys_and_transcript_choice(self):
        tx_mane = {"transcript": "NM_1.1", "bioType": "mRNA", "hgnc": "GENEA", "isManeSelect": True, "isCanonical": True,
                   "consequence": ["missense_variant"], "hgvsp": "NP_1.1:p.(Arg7Gln)", "hgvsc": "NM_1.1:c.20G>A"}
        tx_other = {"transcript": "ENST9.1", "bioType": "lncRNA", "hgnc": "OVERLAPGENE", "isCanonical": True,
                    "consequence": ["upstream_gene_variant"]}
        pos = [
            {"chromosome": "chr1", "position": 100, "refAllele": "G", "altAlleles": ["A"],
             "variants": [{"begin": 100, "refAllele": "G", "altAllele": "A", "transcripts": [tx_other, tx_mane],
                           "gnomad-exome": {"allAf": 1e-6}, "revel": {"score": 0.9}}]},
            # VCF deletion CAG>C at 200 : Nirvana drops the anchor base -> begin 201, ref AG, alt -
            {"chromosome": "chr2", "position": 200, "refAllele": "CAG", "altAlleles": ["C"],
             "variants": [{"begin": 201, "refAllele": "AG", "altAllele": "-", "transcripts": [tx_mane]}]},
        ]
        out = edt.load_nirvana(self._write(pos))
        self.assertEqual(set(out), {"1:100:G:A", "2:200:CAG:C"})
        a = out["1:100:G:A"]
        self.assertEqual(a["vep_gene"], "GENEA")                       # MANE protein-coding gene, not the lncRNA overlap
        self.assertEqual(a["hgvsp"], "NP_1.1:p.Arg7Gln")                 # parentheses stripped for literature search
        self.assertEqual(a["gnomade_af"], 1e-6)
        self.assertEqual(a["revel"], 0.9)
        self.assertIn("missense_variant", a["any_protein_altering"])


class TestMoi(unittest.TestCase):
    def test_classes(self):
        self.assertEqual(edt.moi_class({"moi": "BIALLELIC, autosomal or pseudoautosomal"}), "AR")
        self.assertEqual(edt.moi_class({"moi": "MONOALLELIC, autosomal or pseudoautosomal, NOT imprinted"}), "AD")
        self.assertEqual(edt.moi_class({"moi": "X-LINKED: hemizygous mutation in males"}), "X")
        self.assertEqual(edt.moi_class({}), "")


if __name__ == "__main__":
    unittest.main()
