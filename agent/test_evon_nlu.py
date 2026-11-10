import unittest
from unittest.mock import AsyncMock, patch
from agent.evon_client import EvonClient

class TestEvonNLUIntegration(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.client = EvonClient()

    async def test_extract_and_recommend_local_fallback(self):
        """Verifies unified single-pass extraction and recommendation in local mode."""
        transcript = (
            "RCH ID 999000104829, Sunita Devi. "
            "Pichle camp ka BP 142/92 mila tha aur aaj pairon mein sujan hai."
        )
        res = await self.client.extract_and_recommend(transcript)

        self.assertFalse(res.get("missing_mandatory_id"))
        extracted = res["extracted"]
        rec = res["recommendation"]

        self.assertEqual(extracted["rch_id"], "999000104829")
        self.assertEqual(extracted["beneficiary_name"], "Sunita Devi")
        self.assertIn("pedal_edema", extracted["reported_symptoms"])

        # Recommendation checks
        self.assertEqual(rec.priority_level, "URGENT_PHC_REFERRAL")
        self.assertTrue(rec.flag_red_seal)
        self.assertIn("blood pressure", rec.observed_indicators_summary.lower())

    async def test_extract_and_recommend_missing_rch_id(self):
        """Verifies missing RCH ID triggers polite prompt in unified pipeline."""
        transcript = "Mata ko ulti aur chakkar aa raha hai."
        res = await self.client.extract_and_recommend(transcript)

        self.assertTrue(res.get("missing_mandatory_id"))
        self.assertIn("RCH ID", res["prompt_message"])

    async def test_evon_hosted_api_mock_response(self):
        """Verifies EvonClient parses live JSON response from Evon v3.3 endpoint."""
        client_with_api = EvonClient(base_url="http://mock-evon-host:8001/v1")

        mock_evon_json = {
            "choices": [{
                "message": {
                    "content": """{
                        "missing_mandatory_id": false,
                        "rch_id": "999000104830",
                        "worker_role": "ASHA",
                        "worker_name": "Geeta",
                        "beneficiary_name": "Priya",
                        "bp_reading": null,
                        "bp_source": null,
                        "hb_g_dl": null,
                        "weight_kg": null,
                        "temperature_f": null,
                        "reported_symptoms": [],
                        "supplies_or_meds": ["ORS packet given"],
                        "poshan_joint_visit_num": null,
                        "dynamic_observations": [
                            {
                                "category": "Child_Health",
                                "field_label": "Child Diarrheal Episode",
                                "spoken_value": "Bachhe ko loose motions hai",
                                "status": "Attention"
                            }
                        ],
                        "unmentioned_routine_checks": ["Blood Pressure (BP)", "Hemoglobin (Hb)", "Weight"],
                        "recommendation": {
                            "priority_level": "ATTENTION_NEEDED",
                            "observed_indicators_summary": "Child diarrhea episode reported with hydration counseling.",
                            "recommended_next_steps": ["Ensure continuous ORS administration", "Follow up within 24 hours"],
                            "spoken_reply_native": "Priya ke liye ORS jari rakhein aur kal dubara check karein.",
                            "flag_red_seal": false,
                            "referral_needed": false
                        }
                    }"""
                }
            }]
        }

        with patch.object(client_with_api, 'chat_completion', new=AsyncMock(return_value=mock_evon_json)):
            res = await client_with_api.extract_and_recommend("Sample transcript")
            self.assertFalse(res["missing_mandatory_id"])
            self.assertEqual(res["extracted"]["rch_id"], "999000104830")
            self.assertEqual(res["recommendation"].priority_level, "ATTENTION_NEEDED")
            self.assertIn("ORS", res["recommendation"].recommended_next_steps[0])

if __name__ == "__main__":
    unittest.main()
