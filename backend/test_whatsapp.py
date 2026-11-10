import unittest
import asyncio
from backend.database import get_db_pool, close_db_pool, init_db, reset_whatsapp_session
from backend.whatsapp_handler import WhatsAppFrontlineHandler

class TestWhatsAppIntegration(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await init_db()
        self.handler = WhatsAppFrontlineHandler()
        self.test_phone = "+919000012345"  # ASHA Geeta
        await reset_whatsapp_session(self.test_phone)

    async def asyncTearDown(self):
        await close_db_pool()

    async def test_otp_authentication_flow(self):
        """Worker sends 'Hi', receives OTP, replies with OTP to login."""
        # Step 1: Send 'Hi'
        res1 = await self.handler.handle_incoming_text(self.test_phone, "Hi")
        self.assertEqual(res1["type"], "otp_prompt")
        self.assertFalse(res1["is_authenticated"])
        otp = res1["otp"]
        self.assertEqual(len(otp), 4)

        # Step 2: Send wrong OTP
        res_wrong = await self.handler.handle_incoming_text(self.test_phone, "0000")
        self.assertFalse(res_wrong["is_authenticated"])
        self.assertIn("Galat OTP", res_wrong["text"])

        # Step 3: Send correct OTP
        res2 = await self.handler.handle_incoming_text(self.test_phone, otp)
        self.assertTrue(res2["is_authenticated"])
        self.assertIn("Login Safal", res2["text"])

    async def test_whatsapp_text_visit_processing_and_anm_alert(self):
        """Authenticated ASHA sends visit text on WhatsApp, receives register row and ANM alert."""
        # Authenticate first
        res1 = await self.handler.handle_incoming_text(self.test_phone, "Hi")
        otp = res1["otp"]
        await self.handler.handle_incoming_text(self.test_phone, otp)

        # Send visit update
        visit_text = (
            "RCH ID 999000104829, Sunita Devi, Joint Visit number 8. "
            "MCP card BP 142 by 92 aur pairon mein sujan hai. Das IFA goli bachi hain."
        )
        res_visit = await self.handler.handle_incoming_text(self.test_phone, visit_text)
        self.assertEqual(res_visit["type"], "visit_recorded")
        self.assertIn("MoHFW Register Entry Recorded", res_visit["text"])
        self.assertIn("URGENT_PHC_REFERRAL", res_visit["text"])

        # Verify ANM Alert was generated
        anm_alert = res_visit.get("anm_alert")
        self.assertIsNotNone(anm_alert)
        self.assertEqual(anm_alert["anm_phone"], "+919000098765")
        self.assertTrue(any(b["title"].startswith("✅ Approve") for b in anm_alert["buttons"]))

        # Step 4: ANM 1-Tap Approval via WhatsApp
        queue_id = anm_alert["queue_id"]
        res_app = await self.handler.handle_anm_approval("+919000098765", queue_id)
        self.assertTrue(res_app["success"])
        self.assertIn("Approval Successful", res_app["text"])

if __name__ == "__main__":
    unittest.main()

