import unittest
from agent.evon_client import extract_spoken_entities
from agent.recommendation_engine import (
    generate_care_recommendation,
    evaluate_care_recommendation,
    CareRecommendation,
)

class TestFlexibleRecommendationEngine(unittest.TestCase):
    def test_missing_mandatory_rch_id(self):
        """Utterance without 12-digit RCH ID triggers polite request for ID."""
        transcript = "Main ASHA Rekha bol rahi hoon, aaj grah bhet kiya hai."
        res = extract_spoken_entities(transcript)
        self.assertTrue(res.get("missing_mandatory_id"))
        self.assertIn("RCH ID", res.get("prompt_message", ""))

    def test_open_ended_child_illness_and_nutrition_no_vitals(self):
        """Utterance with RCH ID, child illness and nutrition but NO BP or Hb succeeds with zero information loss."""
        transcript = (
            "Main ASHA Rekha. RCH ID 999000104829, Sunita Devi. "
            "Bachhe ko 2 din se dast aur loose motion hai. "
            "ORS packet ghol pilaya hai. Ration mein chana dal mil gayi hai."
        )
        res = extract_spoken_entities(transcript)
        self.assertFalse(res.get("missing_mandatory_id"))
        self.assertEqual(res["rch_id"], "999000104829")
        self.assertIsNone(res["bp_reading"])
        self.assertIsNone(res["hb_g_dl"])

        # Dynamic observations captured
        dyn_obs = res["dynamic_observations"]
        self.assertGreater(len(dyn_obs), 0)
        labels = [d["field_label"] for d in dyn_obs]
        self.assertTrue(any("diarrhe" in l.lower() or "dast" in l.lower() for l in labels))

        # Unmentioned routine checks noted
        unmentioned = res["unmentioned_routine_checks"]
        self.assertIn("Blood Pressure (BP)", unmentioned)
        self.assertIn("Hemoglobin (Hb)", unmentioned)

        # Recommendation evaluation
        rec = generate_care_recommendation(
            rch_id=res["rch_id"],
            worker_role=res["worker_role"],
            worker_name=res["worker_name"],
            beneficiary_name=res["beneficiary_name"],
            bp_reading=res["bp_reading"],
            hb_g_dl=res["hb_g_dl"],
            dynamic_observations=res["dynamic_observations"],
            unmentioned_routine_checks=res["unmentioned_routine_checks"]
        )
        self.assertEqual(rec.priority_level, "ATTENTION_NEEDED")
        self.assertTrue(any("ORS" in step for step in rec.recommended_next_steps))
        self.assertGreater(len(rec.identified_flags), 0)

    def test_strictly_non_diagnostic_elevated_vitals(self):
        """Elevated BP with edema generates URGENT_PHC_REFERRAL without claiming medical diagnosis."""
        rec = generate_care_recommendation(
            rch_id="999000104829",
            worker_role="ASHA",
            worker_name="Geeta Devi",
            beneficiary_name="Sunita Devi",
            bp_reading="142/92",
            bp_source="MCP_CARD_HISTORY",
            hb_g_dl=8.4,
            reported_symptoms=["pedal_edema", "severe_headache"],
            unmentioned_routine_checks=[]
        )
        self.assertEqual(rec.priority_level, "URGENT_PHC_REFERRAL")
        self.assertTrue(rec.flag_red_seal)
        self.assertTrue(rec.referral_needed)

        # Non-diagnostic medical safety check
        self.assertNotIn("diagnosed with", rec.observed_indicators_summary.lower())
        self.assertNotIn("she has pre-eclampsia", rec.observed_indicators_summary.lower())
        self.assertIn("elevated blood pressure", rec.observed_indicators_summary.lower())
        self.assertTrue(any("Medical Officer" in step for step in rec.recommended_next_steps))
        self.assertGreater(len(rec.identified_flags), 0)

    def test_routine_visit_with_unmentioned_checks_reminder(self):
        """Routine visit without vitals notes unmentioned checks as a gentle reminder."""
        rec = generate_care_recommendation(
            rch_id="999000104829",
            worker_role="ASHA",
            worker_name="Kavita",
            beneficiary_name="Meena Kumari",
            bp_reading=None,
            hb_g_dl=None,
            reported_symptoms=[],
            unmentioned_routine_checks=["Blood Pressure (BP)", "Hemoglobin (Hb)"]
        )
        self.assertEqual(rec.priority_level, "ROUTINE")
        self.assertFalse(rec.flag_red_seal)
        self.assertTrue(any("VHSND" in step for step in rec.recommended_next_steps))

    def test_multilingual_spoken_confirmation(self):
        """Verifies dynamic spoken confirmation in Marathi, Odia, Kannada, and English."""
        # Marathi
        rec_mr = generate_care_recommendation(
            rch_id="999000104829",
            beneficiary_name="Pooja Patil",
            bp_reading="142/92",
            reported_symptoms=["pedal_edema"],
            language_code="mr-IN"
        )
        self.assertIn("नोंद केली आहे", rec_mr.spoken_reply_native)
        self.assertIn("प्राथमिक आरोग्य केंद्रात", rec_mr.spoken_reply_native)

        # Odia
        rec_or = generate_care_recommendation(
            rch_id="999000104829",
            beneficiary_name="Minati Sahoo",
            bp_reading="142/92",
            reported_symptoms=["pedal_edema"],
            language_code="or-IN"
        )
        self.assertIn("ତଥ୍ୟ ସୁରକ୍ଷିତ", rec_or.spoken_reply_native)
        self.assertIn("ଡାକ୍ତରଖାନା", rec_or.spoken_reply_native)

        # Kannada
        rec_kn = generate_care_recommendation(
            rch_id="999000104829",
            beneficiary_name="Deepa Gowda",
            bp_reading="142/92",
            reported_symptoms=["pedal_edema"],
            language_code="kn-IN"
        )
        self.assertIn("ವಿವರ ದಾಖಲಾಗಿದೆ", rec_kn.spoken_reply_native)
        self.assertIn("ಪ್ರಾಥಮಿಕ ಆರೋಗ್ಯ ಕೇಂದ್ರಕ್ಕೆ", rec_kn.spoken_reply_native)

        # English
        rec_en = generate_care_recommendation(
            rch_id="999000104829",
            beneficiary_name="Mary Fernandez",
            bp_reading="142/92",
            reported_symptoms=["pedal_edema"],
            language_code="en-IN"
        )
        self.assertIn("Record for Mary Fernandez has been saved", rec_en.spoken_reply_native)

    def test_dynamic_flag_identification_and_prioritization(self):
        """Verifies that flags are identified dynamically and prioritized by severity."""
        # Critical flag (Hemorrhage) overrides moderate flags
        rec = generate_care_recommendation(
            rch_id="999000104829",
            beneficiary_name="Anjali Sharma",
            bp_reading="120/80",
            hb_g_dl=10.2,  # Moderate
            reported_symptoms=["vaginal_bleeding"],  # Critical
            language_code="hi-IN"
        )
        self.assertEqual(rec.priority_level, "URGENT_PHC_REFERRAL")
        self.assertTrue(rec.flag_red_seal)
        self.assertTrue(rec.referral_needed)
        self.assertTrue(any("bleeding" in f.lower() for f in rec.identified_flags))

class TestAsyncRecommendations(unittest.IsolatedAsyncioTestCase):
    async def test_async_evaluate_entrypoint(self):
        rec = await evaluate_care_recommendation(
            rch_id="999000104829",
            beneficiary_name="Kavita Devi",
            bp_reading="144/94",
            reported_symptoms=["pedal_edema"],
            language_code="hi-IN"
        )
        self.assertEqual(rec.priority_level, "URGENT_PHC_REFERRAL")
        self.assertTrue(rec.flag_red_seal)

if __name__ == "__main__":
    unittest.main()
