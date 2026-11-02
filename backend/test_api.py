import unittest
import httpx
from httpx import ASGITransport
from backend.app import app
from backend.database import close_db_pool, init_db

class TestBackendAPI(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        await init_db()
        self.client = httpx.AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        )

    async def asyncTearDown(self):
        await self.client.aclose()
        await close_db_pool()

    async def test_health_check(self):
        resp = await self.client.get("/api/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "healthy")
        self.assertTrue(data["database_connected"])

    async def test_get_beneficiaries(self):
        resp = await self.client.get("/api/beneficiaries")
        self.assertEqual(resp.status_code, 200)
        beneficiaries = resp.json()
        self.assertGreater(len(beneficiaries), 0)
        for b in beneficiaries:
            self.assertTrue(b["rch_id"].startswith("999"))
            self.assertIn("Synthetic", b["mother_name"])

    async def test_anmol_queue_flow(self):
        resp = await self.client.get("/api/anmol/queue")
        self.assertEqual(resp.status_code, 200)
        queue = resp.json()
        self.assertIsInstance(queue, list)

    async def test_poshan_visits(self):
        resp = await self.client.get("/api/poshan/visits")
        self.assertEqual(resp.status_code, 200)
        visits = resp.json()
        self.assertIsInstance(visits, list)

if __name__ == "__main__":
    unittest.main()
