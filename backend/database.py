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
    # Remove query string parameters like ?sslmode=require because asyncpg accepts ssl param
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
    recorded_bp VARCHAR(32),
    recorded_hb NUMERIC(4, 2),
    danger_signs_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    triage_severity VARCHAR(32) NOT NULL,
    triage_action_hindi TEXT,
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
    whatsapp_row_text TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
"""

async def init_db():
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute(SCHEMA_SQL)
        logger.info("Initialized Neon PostgreSQL database tables successfully.")

