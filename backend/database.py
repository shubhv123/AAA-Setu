import os
import json
import logging
from typing import Optional
import asyncpg
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("aaa_setu.database")

_pool: Optional[asyncpg.Pool] = None

def get_database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise ValueError("DATABASE_URL is not set in environment or .env file.")
    if "?" in url:
        url = url.split("?")[0]
    return url

async def get_db_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        db_url = get_database_url()
        _pool = await asyncpg.create_pool(
            db_url,
            ssl="require",
            min_size=1,
            max_size=10,
            command_timeout=60,
        )
        logger.info("Connected to Neon PostgreSQL pool.")
    return _pool

async def close_db_pool():
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("Closed Neon PostgreSQL pool.")

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS synthetic_mcp_cards (
    rch_id VARCHAR(32) PRIMARY KEY,
    mother_name VARCHAR(128) NOT NULL,
    village VARCHAR(128) NOT NULL,
    assigned_asha VARCHAR(128) NOT NULL,
    assigned_anm VARCHAR(128) NOT NULL,
    last_vhsnd_date DATE NOT NULL,
    last_subcentre_bp VARCHAR(32) NOT NULL,
    last_subcentre_hb NUMERIC(4, 2) NOT NULL,
    high_risk_red_seal BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS anmol_verification_queue (
    queue_id SERIAL PRIMARY KEY,
    source_role VARCHAR(32) NOT NULL,
    asha_worker_name VARCHAR(128) NOT NULL,
    rch_id VARCHAR(32) NOT NULL,
    beneficiary_name VARCHAR(128),
    recorded_bp VARCHAR(32),
    bp_source VARCHAR(32),
    recorded_hb NUMERIC(4, 2),
    weight_kg NUMERIC(4, 2),
    temperature_f NUMERIC(4, 1),
    danger_signs_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    supplies_or_meds JSONB NOT NULL DEFAULT '[]'::jsonb,
    dynamic_observations JSONB NOT NULL DEFAULT '[]'::jsonb,
    unmentioned_routine_checks JSONB NOT NULL DEFAULT '[]'::jsonb,
    priority_level VARCHAR(32) NOT NULL DEFAULT 'ROUTINE',
    observed_indicators_summary TEXT,
    recommended_next_steps JSONB NOT NULL DEFAULT '[]'::jsonb,
    triage_severity VARCHAR(32) NOT NULL DEFAULT 'NORMAL',
    triage_action_hindi TEXT,
    spoken_reply_native TEXT,
    anm_approval_status VARCHAR(32) DEFAULT 'PENDING_VERIFICATION',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS poshan_joint_visits (
    visit_id SERIAL PRIMARY KEY,
    rch_id VARCHAR(32) NOT NULL,
    visit_number INT NOT NULL,
    joint_asha_aww_verified BOOLEAN DEFAULT FALSE,
    sync_status VARCHAR(32) DEFAULT 'CACHED_OFFLINE',
    child_or_mother_name VARCHAR(128),
    child_weight_kg NUMERIC(4, 2),
    thr_packets_verified INT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS paper_register_records (
    record_id SERIAL PRIMARY KEY,
    record_date DATE DEFAULT CURRENT_DATE,
    rch_id VARCHAR(32) NOT NULL,
    mother_name VARCHAR(128) NOT NULL,
    village VARCHAR(128) NOT NULL,
    worker_name VARCHAR(128) NOT NULL,
    bp VARCHAR(32),
    hb NUMERIC(4, 2),
    danger_signs TEXT,
    referral_action TEXT,
    dynamic_notes TEXT,
    priority_level VARCHAR(32) DEFAULT 'ROUTINE',
    whatsapp_row_text TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS whatsapp_frontline_sessions (
    phone_number VARCHAR(32) PRIMARY KEY,
    worker_name VARCHAR(128) NOT NULL,
    worker_role VARCHAR(32) NOT NULL,
    village VARCHAR(128) NOT NULL,
    active_otp VARCHAR(6),
    is_authenticated BOOLEAN DEFAULT FALSE,
    last_interaction TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
"""

MIGRATION_SQL = """
ALTER TABLE anmol_verification_queue ADD COLUMN IF NOT EXISTS beneficiary_name VARCHAR(128);
ALTER TABLE anmol_verification_queue ADD COLUMN IF NOT EXISTS bp_source VARCHAR(32);
ALTER TABLE anmol_verification_queue ADD COLUMN IF NOT EXISTS weight_kg NUMERIC(4, 2);
ALTER TABLE anmol_verification_queue ADD COLUMN IF NOT EXISTS temperature_f NUMERIC(4, 1);
ALTER TABLE anmol_verification_queue ADD COLUMN IF NOT EXISTS supplies_or_meds JSONB NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE anmol_verification_queue ADD COLUMN IF NOT EXISTS dynamic_observations JSONB NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE anmol_verification_queue ADD COLUMN IF NOT EXISTS unmentioned_routine_checks JSONB NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE anmol_verification_queue ADD COLUMN IF NOT EXISTS priority_level VARCHAR(32) NOT NULL DEFAULT 'ROUTINE';
ALTER TABLE anmol_verification_queue ADD COLUMN IF NOT EXISTS observed_indicators_summary TEXT;
ALTER TABLE anmol_verification_queue ADD COLUMN IF NOT EXISTS recommended_next_steps JSONB NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE anmol_verification_queue ADD COLUMN IF NOT EXISTS spoken_reply_native TEXT;

ALTER TABLE paper_register_records ADD COLUMN IF NOT EXISTS dynamic_notes TEXT;
ALTER TABLE paper_register_records ADD COLUMN IF NOT EXISTS priority_level VARCHAR(32) DEFAULT 'ROUTINE';
"""

async def init_db():
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute(SCHEMA_SQL)
        await conn.execute(MIGRATION_SQL)
        
        # Seed exactly 1 ASHA and 1 ANM for clean testing
        await conn.execute("""
            INSERT INTO whatsapp_frontline_sessions (phone_number, worker_name, worker_role, village, is_authenticated)
            VALUES 
                ('+919000012345', 'Geeta Devi', 'ASHA', 'Kishanpur', FALSE),
                ('+919000098765', 'Nurse Kavita', 'ANM', 'Kishanpur Sub-Centre', FALSE)
            ON CONFLICT (phone_number) DO NOTHING;
        """)
        logger.info("Initialized Neon PostgreSQL database tables, migrations, and WhatsApp sessions.")

async def get_whatsapp_session(phone_number: str) -> Optional[dict]:
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM whatsapp_frontline_sessions WHERE phone_number = $1;",
            phone_number
        )
        return dict(row) if row else None

async def set_whatsapp_otp(phone_number: str, otp: str, worker_name: str = "Frontline Worker", worker_role: str = "ASHA", village: str = "Sub-Centre Area"):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO whatsapp_frontline_sessions (phone_number, worker_name, worker_role, village, active_otp, is_authenticated, last_interaction)
            VALUES ($1, $2, $3, $4, $5, FALSE, NOW())
            ON CONFLICT (phone_number) DO UPDATE
            SET active_otp = $5, is_authenticated = FALSE, last_interaction = NOW();
        """, phone_number, worker_name, worker_role, village, otp)

async def verify_whatsapp_otp(phone_number: str, otp: str) -> bool:
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT active_otp FROM whatsapp_frontline_sessions WHERE phone_number = $1;",
            phone_number
        )
        if row and row["active_otp"] == otp:
            await conn.execute("""
                UPDATE whatsapp_frontline_sessions
                SET is_authenticated = TRUE, active_otp = NULL, last_interaction = NOW()
                WHERE phone_number = $1;
            """, phone_number)
            return True
        return False

async def reset_whatsapp_session(phone_number: str):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE whatsapp_frontline_sessions
            SET is_authenticated = FALSE, active_otp = NULL, last_interaction = NOW()
            WHERE phone_number = $1;
        """, phone_number)

async def clear_database():
    """Clear all records from all tables and reset sessions with 1 unauthenticated ASHA and 1 ANM."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute("TRUNCATE TABLE paper_register_records RESTART IDENTITY CASCADE;")
        await conn.execute("TRUNCATE TABLE poshan_joint_visits RESTART IDENTITY CASCADE;")
        await conn.execute("TRUNCATE TABLE anmol_verification_queue RESTART IDENTITY CASCADE;")
        await conn.execute("TRUNCATE TABLE synthetic_mcp_cards RESTART IDENTITY CASCADE;")
        
        # Reset WhatsApp sessions to only 1 ASHA and 1 ANM, both unauthenticated
        await conn.execute("DELETE FROM whatsapp_frontline_sessions;")
        await conn.execute("""
            INSERT INTO whatsapp_frontline_sessions (phone_number, worker_name, worker_role, village, is_authenticated)
            VALUES 
                ('+919000012345', 'Geeta Devi', 'ASHA', 'Kishanpur', FALSE),
                ('+919000098765', 'Nurse Kavita', 'ANM', 'Kishanpur Sub-Centre', FALSE);
        """)
        logger.info("All database tables truncated and cleared. 1 ASHA and 1 ANM registered as unauthenticated.")
