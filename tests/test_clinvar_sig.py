"""Offline unit tests for pipeline/clinvar_sig.py. Run:  python -m unittest discover -s tests -v"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pipeline"))
from clinvar_sig import (  # noqa: E402
    clinical_significance, clinvar_tier, conflict_counts, conflicting_with_pathogenic,
    is_pathogenic_clnsig,
)

CONF = "Conflicting_classifications_of_pathogenicity"


class TestConflictCounts(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(
            conflict_counts("Pathogenic(7)|Likely_pathogenic(1)|Uncertain_significance(1)"),
            {"pathogenic": 7, "likely_pathogenic": 1, "uncertain_significance": 1})

    def test_empty_and_dot(self):
        self.assertEqual(conflict_counts(""), {})
        self.assertEqual(conflict_counts("."), {})

    def test_spaces_and_commas(self):
        self.assertEqual(conflict_counts("Pathogenic(2), Likely benign(1)"),
                         {"pathogenic": 2, "likely_benign": 1})


class TestTiers(unittest.TestCase):
    def test_pathogenic_is_T1a(self):
        self.assertEqual(clinvar_tier("Pathogenic"), "T1a")
        self.assertEqual(clinvar_tier("Likely_pathogenic"), "T1a")
        self.assertEqual(clinvar_tier("Pathogenic/Likely_pathogenic"), "T1a")

    def test_conflicting_with_pathogenic_submissions_is_T1b(self):
        # the failure that hid a real disease variant: P/LP majority + one VUS => "Conflicting"
        conf = "Pathogenic(7)|Likely_pathogenic(1)|Uncertain_significance(1)"
        self.assertEqual(clinvar_tier(CONF, conf), "T1b")
        self.assertEqual(clinvar_tier("Conflicting_interpretations_of_pathogenicity", conf), "T1b")

    def test_conflicting_without_pathogenic_is_not_flagged(self):
        self.assertEqual(clinvar_tier(CONF, "Uncertain_significance(2)|Likely_benign(1)"), "")

    def test_conflicting_label_alone_is_not_pathogenic(self):
        # the substring trap: the label contains "pathogenic" but is not a pathogenic call
        self.assertFalse(is_pathogenic_clnsig(CONF))
        self.assertEqual(clinvar_tier(CONF, ""), "")

    def test_benign_and_vus_are_no_tier(self):
        self.assertEqual(clinvar_tier("Benign"), "")
        self.assertEqual(clinvar_tier("Uncertain_significance"), "")

    def test_helper(self):
        self.assertTrue(conflicting_with_pathogenic(CONF, "Likely_pathogenic(1)|Uncertain_significance(1)"))
        self.assertFalse(conflicting_with_pathogenic("Pathogenic", "Pathogenic(3)"))


class TestClinicalSignificance(unittest.TestCase):
    def test_old_behaviour_kept(self):
        self.assertEqual(clinical_significance("Conflicting_interpretations_of_pathogenicity"), "unknown")
        self.assertEqual(clinical_significance("Pathogenic"), "pathogenic")
        self.assertEqual(clinical_significance("not_provided, Pathogenic"), "pathogenic")

    def test_conflicting_classes(self):
        self.assertEqual(clinical_significance(CONF, "Pathogenic(3)|Uncertain_significance(1)"), "conflicting_pathogenic")
        self.assertEqual(clinical_significance(CONF, "Uncertain_significance(2)|Benign(1)"), "conflicting")


if __name__ == "__main__":
    unittest.main()
