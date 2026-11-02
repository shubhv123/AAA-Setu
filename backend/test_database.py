import unittest
import asyncio
from backend.database import get_db_pool, close_db_pool

class TestDatabaseCompliance(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.pool = await get_db_pool()

    async def asyncTearDown(self):
        await close_db_pool()

    async def test_synthetic_rch_compliance(self):
        """Zero-tolerance synthetic compliance: All RCH IDs must be 12 digits starting with '999'."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT rch_id, mother_name FROM synthetic_mcp_cards")
            self.assertGreater(len(rows), 0, "Should have seeded synthetic MCP cards")
            for r in rows:
                rch_id = r["rch_id"]
                mother_name = r["mother_name"]
                self.assertEqual(len(rch_id), 12, f"RCH ID {rch_id} must be 12 digits")
                self.assertTrue(rch_id.startswith("999"), f"RCH ID {rch_id} must be prefixed with 999")
                self.assertTrue(rch_id.isdigit(), f"RCH ID {rch_id} must be numeric")
                self.assertIn("Synthetic", mother_name, f"Beneficiary {mother_name} must be clearly flagged as synthetic")

    async def test_poshan_visits_seeded(self):
        """Verify seeded Poshan joint visits."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT rch_id, visit_number, sync_status FROM poshan_joint_visits")
            self.assertGreater(len(rows), 0, "Should have seeded poshan joint visits")
            for r in rows:
                self.assertIn(r["visit_number"], [8, 9, 11, 14, 15], "Joint visit number must be 8, 9, 11, 14, or 15")

if __name__ == "__main__":
    unittest.main()

