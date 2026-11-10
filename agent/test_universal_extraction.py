import unittest
from agent.evon_client import (
    extract_spoken_entities,
    extract_rch_id,
    extract_beneficiary_name,
    extract_visit_number,
    extract_supplies_or_medications,
    extract_blood_pressure
)

class TestUniversalIndicExtraction(unittest.TestCase):

    def test_universal_names_without_hardcoded_surnames(self):
        """Tests that any Indian name is extracted without hardcoded surname restrictions."""
        # 1. Non-North Indian names
        t1 = "RCH ID 999000104829, Mata Fatima Begum ka home visit kiya."
        res1 = extract_spoken_entities(t1)
        self.assertEqual(res1["beneficiary_name"], "Fatima Begum")

        t2 = "RCH ID 999000104830, Mary Thomas ka checkup kiya."
        res2 = extract_spoken_entities(t2)
        self.assertEqual(res2["beneficiary_name"], "Mary Thomas")

        t3 = "RCH ID 999000104831, Labharthi Swapna Gowda ka BP 120/80 mila."
        res3 = extract_spoken_entities(t3)
        self.assertEqual(res3["beneficiary_name"], "Swapna Gowda")

        # 2. Single-word names
        t4 = "RCH ID 999000104832, bache Priya ko ORS packet diya."
        res4 = extract_spoken_entities(t4)
        self.assertEqual(res4["beneficiary_name"], "Priya")

        t5 = "RCH ID 999000104833, Shishu Aarav ka vajan 8.2 kg hai."
        res5 = extract_spoken_entities(t5)
        self.assertEqual(res5["beneficiary_name"], "Aarav")

    def test_name_with_gestational_months_and_ordinals(self):
        """Tests that ordinal words like 'satva' (7th) or 'aathva' (8th) don't break name extraction."""
        t1 = "RCH ID 999000104829, Mata Sunita ka satva mahina chal raha hai."
        res1 = extract_spoken_entities(t1)
        self.assertEqual(res1["beneficiary_name"], "Sunita")

        t2 = "RCH ID 999000104829, Sunita Devi ka aathva mahina hai, BP 140/90 mila."
        res2 = extract_spoken_entities(t2)
        self.assertEqual(res2["beneficiary_name"], "Sunita Devi")

    def test_universal_ordinals_and_visit_numbers(self):
        """Tests that visit numbers are extracted across words, ordinals, and digits."""
        # Word ordinals
        self.assertEqual(extract_visit_number("aathva daura kiya"), 8)
        self.assertEqual(extract_visit_number("satva visit"), 7)
        self.assertEqual(extract_visit_number("gyarahvi bhet"), 11)
        self.assertEqual(extract_visit_number("chaudahva daura"), 14)
        self.assertEqual(extract_visit_number("pandrahvi visit"), 15)

        # English ordinals
        self.assertEqual(extract_visit_number("completed 8th visit today"), 8)
        self.assertEqual(extract_visit_number("visit number 9"), 9)
        self.assertEqual(extract_visit_number("visit 11"), 11)

    def test_authentic_spoken_clause_dynamic_observations(self):
        """Tests that dynamic observations capture the EXACT spoken words, not fake canned strings."""
        transcript = (
            "RCH ID 999000104830, Sunita Devi. "
            "Bache ko 2 din se patla dast ho raha hai. "
            "Mata ko chakkar aa raha hai aur khana nahi kha rahi hain. "
            "Ghar me saaf ubla paani peene ki salah di."
        )
        res = extract_spoken_entities(transcript)
        obs = res["dynamic_observations"]
        self.assertGreater(len(obs), 0)

        # Check Child Health observation has authentic spoken words
        child_obs = next(o for o in obs if o["category"] == "Child_Health")
        self.assertIn("patla dast", child_obs["spoken_value"].lower())

        # Check Maternal observation has authentic spoken words
        mat_obs = next(o for o in obs if o["category"] == "Maternal")
        self.assertIn("chakkar", mat_obs["spoken_value"].lower())

        # Check Sanitation observation has authentic spoken words
        san_obs = next(o for o in obs if o["category"] == "General")
        self.assertIn("paani", san_obs["spoken_value"].lower())

    def test_universal_blood_pressure_phrases(self):
        """Tests that blood pressure is parsed across spoken formats and physiological ranges."""
        bp1, src1 = extract_blood_pressure("BP 142/92 recorded")
        self.assertEqual(bp1, "142/92")

        bp2, src2 = extract_blood_pressure("raktchaap 140 by 90 mila")
        self.assertEqual(bp2, "140/90")

        bp3, src3 = extract_blood_pressure("pichle MCP card par BP 138/88 likha tha")
        self.assertEqual(bp3, "138/88")
        self.assertEqual(src3, "MCP_CARD_HISTORY")

    def test_dynamic_supplies_and_quantities(self):
        """Tests that medication counts are parsed dynamically without hardcoded amounts."""
        s1 = extract_supplies_or_medications("aaj 30 IFA tablets di")
        self.assertTrue(any("30 IFA tablets" in item for item in s1))

        s2 = extract_supplies_or_medications("ghar me 10 goli bachi hai")
        self.assertTrue(any("10" in item and "remaining" in item for item in s2))

        s3 = extract_supplies_or_medications("ORS packet diya aur calcium tablets di")
        self.assertTrue(any("ORS" in item for item in s3))
        self.assertTrue(any("Calcium" in item for item in s3))

if __name__ == "__main__":
    unittest.main()

