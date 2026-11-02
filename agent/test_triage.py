import unittest
from agent.triage_engine import evaluate_maternal_red_flags

class TestTriageEngine(unittest.TestCase):
    def test_preeclampsia_critical_red_seal(self):
        """Sunita Devi scenario: BP 142/92, Hb 8.4, pedal edema and severe headache."""
        res = evaluate_maternal_red_flags(
            bp_str="142/92",
            hb_level=8.4,
            danger_signs=["pedal_edema", "severe_headache"],
            asha_worker_name="Geeta",
            beneficiary_name="Sunita Devi",
            anm_worker_name="Nurse Kavita"
        )
        self.assertEqual(res.severity, "CRITICAL_RED_SEAL")
        self.assertTrue(res.flag_red_seal)
        self.assertTrue(res.referral_needed)
        self.assertIn("Pre-Eclampsia", res.action_hindi)
        self.assertIn("PHC le jaayein", res.action_hindi)

    def test_borderline_hypertension_watch(self):
        """Borderline BP 136/86 with headache."""
        res = evaluate_maternal_red_flags(
            bp_str="136/86",
            hb_level=10.5,
            danger_signs=["severe_headache"]
        )
        self.assertEqual(res.severity, "URGENT")
        self.assertFalse(res.flag_red_seal)
        self.assertIn("Borderline BP", res.action_hindi)

    def test_severe_anemia(self):
        """Hb 6.5 g/dL (< 7.0 g/dL) is critical."""
        res = evaluate_maternal_red_flags(
            bp_str="110/70",
            hb_level=6.5,
            danger_signs=[]
        )
        self.assertEqual(res.severity, "CRITICAL_RED_SEAL")
        self.assertTrue(res.flag_red_seal)
        self.assertIn("Severe", res.condition_name)
        self.assertIn("Anemia", res.condition_name)

    def test_normal_vitals(self):
        """Normal BP 118/76, Hb 11.2, no danger signs."""
        res = evaluate_maternal_red_flags(
            bp_str="118/76",
            hb_level=11.2,
            danger_signs=[]
        )
        self.assertEqual(res.severity, "NORMAL")
        self.assertFalse(res.flag_red_seal)
        self.assertFalse(res.referral_needed)

if __name__ == "__main__":
    unittest.main()
