import asyncio
import logging
from datetime import date
from backend.database import get_db_pool, init_db, close_db_pool

logger = logging.getLogger("aaa_setu.seed")
logging.basicConfig(level=logging.INFO)

SYNTHETIC_BENEFICIARIES = [
    {
        "rch_id": "999000104829",
        "mother_name": "Sunita Devi (Synthetic)",
        "village": "Kishanpur",
        "assigned_asha": "Geeta Devi",
        "assigned_anm": "Nurse Kavita",
        "last_vhsnd_date": "2026-10-15",
        "last_subcentre_bp": "142/92",
        "last_subcentre_hb": 8.4,
        "high_risk_red_seal": False,
    },
    {
        "rch_id": "999000104830",
        "mother_name": "Meena Kumari (Synthetic)",
        "village": "Kishanpur",
        "assigned_asha": "Geeta Devi",
        "assigned_anm": "Nurse Kavita",
        "last_vhsnd_date": "2026-10-18",
        "last_subcentre_bp": "118/76",
        "last_subcentre_hb": 11.2,
        "high_risk_red_seal": False,
    },
    {
        "rch_id": "999000104831",
        "mother_name": "Pooja Rani (Synthetic)",
        "village": "Rampur",
        "assigned_asha": "Suman Bai",
        "assigned_anm": "Nurse Kavita",
        "last_vhsnd_date": "2026-10-12",
        "last_subcentre_bp": "110/70",
        "last_subcentre_hb": 6.8,
        "high_risk_red_seal": True,
    },
]

POSHAN_VISITS_SEED = [
    {
        "rch_id": "999000104830",
        "visit_number": 8,
        "joint_asha_aww_verified": True,
        "sync_status": "SYNCED_MWCD",
        "child_or_mother_name": "Meena Kumari (Synthetic)",
        "child_weight_kg": 3.2,
        "thr_packets_verified": 4,
    },
    {
        "rch_id": "999000104831",
        "visit_number": 9,
        "joint_asha_aww_verified": False,
        "sync_status": "CACHED_OFFLINE",
        "child_or_mother_name": "Pooja Rani (Synthetic)",
        "child_weight_kg": 4.1,
        "thr_packets_verified": 2,
    },
]

async def seed_synthetic_data(reset: bool = False):
    await init_db()
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        if reset:
            await conn.execute("TRUNCATE paper_register_records, poshan_joint_visits, anmol_verification_queue, synthetic_mcp_cards RESTART IDENTITY;")
            logger.info("Truncated existing tables.")

        for b in SYNTHETIC_BENEFICIARIES:
            await conn.execute(
                """
                INSERT INTO synthetic_mcp_cards (
                    rch_id, mother_name, village, assigned_asha, assigned_anm,
                    last_vhsnd_date, last_subcentre_bp, last_subcentre_hb, high_risk_red_seal
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT (rch_id) DO UPDATE SET
                    mother_name = EXCLUDED.mother_name,
                    village = EXCLUDED.village,
                    assigned_asha = EXCLUDED.assigned_asha,
                    assigned_anm = EXCLUDED.assigned_anm,
                    last_vhsnd_date = EXCLUDED.last_vhsnd_date,
                    last_subcentre_bp = EXCLUDED.last_subcentre_bp,
                    last_subcentre_hb = EXCLUDED.last_subcentre_hb,
                    high_risk_red_seal = EXCLUDED.high_risk_red_seal;
                """,
                b["rch_id"],
                b["mother_name"],
                b["village"],
                b["assigned_asha"],
                b["assigned_anm"],
                date.fromisoformat(b["last_vhsnd_date"]),
                b["last_subcentre_bp"],
                b["last_subcentre_hb"],
                b["high_risk_red_seal"],
            )

        # Check existing poshan visits count
        count = await conn.fetchval("SELECT COUNT(*) FROM poshan_joint_visits;")
        if count == 0:
            for p in POSHAN_VISITS_SEED:
                await conn.execute(
                    """
                    INSERT INTO poshan_joint_visits (
                        rch_id, visit_number, joint_asha_aww_verified,
                        sync_status, child_or_mother_name, child_weight_kg, thr_packets_verified
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7);
                    """,
                    p["rch_id"],
                    p["visit_number"],
                    p["joint_asha_aww_verified"],
                    p["sync_status"],
                    p["child_or_mother_name"],
                    p["child_weight_kg"],
                    p["thr_packets_verified"],
                )

        logger.info("Synthetic beneficiaries and initial Poshan visits seeded into Neon Postgres.")

if __name__ == "__main__":
    async def main():
        await seed_synthetic_data(reset=True)
        await close_db_pool()
    asyncio.run(main())
