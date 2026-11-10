import unittest
import asyncio
from backend.database import get_db_pool, close_db_pool

class TestDatabaseCompliance(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.pool = await get_db_pool()

    async def asyncTearDown(self):
        await close_db_pool()

    async def test_table_connectivity_and_schema(self):
        """Verify database connectivity and required tables exist in Neon PostgreSQL."""
        async with self.pool.acquire() as conn:
            tables = await conn.fetch("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            """)
            table_names = [t["table_name"] for t in tables]
            required_tables = [
                "synthetic_mcp_cards",
                "anmol_verification_queue",
                "poshan_joint_visits",
                "paper_register_records"
            ]
            for req in required_tables:
                self.assertIn(req, table_names, f"Table {req} must exist in database")

    async def test_synthetic_rch_compliance_if_present(self):
        """Zero-tolerance synthetic compliance: All RCH IDs in database must be 12 digits starting with '999'."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT rch_id FROM synthetic_mcp_cards")
            for r in rows:
                rch_id = r["rch_id"]
                self.assertEqual(len(rch_id), 12, f"RCH ID {rch_id} must be 12 digits")
                self.assertTrue(rch_id.startswith("999"), f"RCH ID {rch_id} must be prefixed with 999")
                self.assertTrue(rch_id.isdigit(), f"RCH ID {rch_id} must be numeric")

if __name__ == "__main__":
    unittest.main()
