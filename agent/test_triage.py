import unittest
from agent.triage_engine import (
    evaluate_maternal_red_flags,
    evaluate_maternal_triage_with_evon,
    TriageResult,
)

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

    def test_patient_history_acute_bp_surge(self):
        """
        Patient's baseline MCP card had BP 105/65.
        Current BP 138/88 represents a massive acute surge (+33/+23 mmHg),
        which combined with reported swelling triggers CRITICAL_RED_SEAL.
        """
        history = {
            "last_subcentre_bp": "105/65",
            "last_subcentre_hb": 11.0,
            "high_risk_red_seal": False
        }
        res = evaluate_maternal_red_flags(
            bp_str="138/88",
            hb_level=10.2,
            danger_signs=["swelling"],
            patient_history=history
        )
        self.assertEqual(res.severity, "CRITICAL_RED_SEAL")
        self.assertTrue(res.flag_red_seal)
        self.assertIsNotNone(res.patient_history_comparison)
        self.assertIn("Acute BP surge", res.patient_history_comparison)

    def test_symptom_negation_awareness(self):
        """
        Worker reports 'BP 142/92 hai lekin sujan nahi hai aur sar dard nahi hai'.
        The engine recognizes negation and does not claim pre-eclampsia symptoms.
        """
        res = evaluate_maternal_red_flags(
            bp_str="142/92",
            hb_level=11.5,
            danger_signs=[],
            spoken_utterance="Mata ka BP 142/92 hai lekin sujan nahi hai aur sar dard nahi hai"
        )
        # Without symptoms, high BP alone is flagged for urgent monitoring rather than pre-eclampsia crisis
        self.assertNotEqual(res.condition_name, "Severe Pre-Eclampsia Risk Alert")

class TestAsyncTriage(unittest.IsolatedAsyncioTestCase):
    async def test_async_evon_triage_signature(self):
        """Verifies evaluate_maternal_triage_with_evon accepts patient history."""
        # When GNANI_EVON_API_BASE is empty, it raises ValueError as expected
        with self.assertRaises(ValueError):
            await evaluate_maternal_triage_with_evon(
                bp_str="142/92",
                hb_level=8.4,
                danger_signs=["pedal_edema"],
                patient_history={"last_subcentre_bp": "110/70"}
            )

if __name__ == "__main__":
    unittest.main()
