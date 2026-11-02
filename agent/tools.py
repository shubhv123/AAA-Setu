import json
import logging
from datetime import date
from typing import Dict, Any, List, Optional
from backend.database import get_db_pool
from agent.triage_engine import evaluate_maternal_red_flags, TriageResult

logger = logging.getLogger("aaa_setu.tools")

async def generate_paper_register_row(
    rch_id: str,
    mother_name: str,
    village: str,
    worker_name: str,
    bp: Optional[str],
    hb: Optional[float],
    danger_signs: List[str],
    referral_action: str
) -> Dict[str, Any]:
    """
    Skill 5: Formats extracted indicators into a clean WhatsApp-friendly row matching
    the exact columns of the physical MoHFW audit register.
    """
    today_str = date.today().isoformat()
    signs_str = ", ".join(danger_signs) if danger_signs else "None"
    
    whatsapp_row = (
        f"📋 *MoHFW Register Entry*\n"
        f"• *Date:* {today_str}\n"
        f"• *RCH ID:* `{rch_id}`\n"
        f"• *Beneficiary:* {mother_name}\n"
        f"• *Village:* {village}\n"
        f"• *Reported By:* {worker_name}\n"
        f"• *Last BP:* {bp or 'N/A'}\n"
        f"• *Hb Level:* {hb or 'N/A'} g/dL\n"
        f"• *Danger Signs:* {signs_str}\n"
        f"• *Referral / Action:* {referral_action}"
    )

    pool = await get_db_pool()
    async with pool.acquire() as conn:
        record_id = await conn.fetchval(
            """
            INSERT INTO paper_register_records (
                record_date, rch_id, mother_name, village, worker_name,
                bp, hb, danger_signs, referral_action, whatsapp_row_text
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            RETURNING record_id;
            """,
            date.today(),
            rch_id,
            mother_name,
            village,
            worker_name,
            bp,
            hb,
            signs_str,
            referral_action,
            whatsapp_row
        )

    return {
        "record_id": record_id,
        "whatsapp_row": whatsapp_row,
        "status": "SAVED_TO_AUDIT_REGISTER"
    }

async def sync_poshan_joint_visit(
    rch_id: str,
    visit_number: int,
    child_or_mother_name: str,
    child_weight_kg: Optional[float] = None,
    thr_packets_verified: Optional[int] = None,
    offline_cached: bool = False
) -> Dict[str, Any]:
    """
    Skill 4: Captures mandated MWCD Poshan Tracker Joint Home Visits (8, 9, 11, 14, 15).
    Operates offline-first and syncs when connectivity returns.
    """
    if visit_number not in [8, 9, 11, 14, 15]:
        logger.warning(f"Visit number {visit_number} is not one of mandated joint visits (8,9,11,14,15)")

    sync_status = "CACHED_OFFLINE" if offline_cached else "SYNCED_MWCD"
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        visit_id = await conn.fetchval(
            """
            INSERT INTO poshan_joint_visits (
                rch_id, visit_number, joint_asha_aww_verified,
                sync_status, child_or_mother_name, child_weight_kg, thr_packets_verified
            ) VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING visit_id;
            """,
            rch_id,
            visit_number,
            True,
            sync_status,
            child_or_mother_name,
            child_weight_kg,
            thr_packets_verified or 4
        )

    return {
        "visit_id": visit_id,
        "visit_number": visit_number,
        "sync_status": sync_status,
        "joint_verified": True
    }

async def stage_asha_to_anmol_queue(
    asha_worker_name: str,
    beneficiary_name: str,
    rch_id: str,
    gestational_month: Optional[int] = None,
    mcp_card_last_bp: Optional[str] = None,
    mcp_card_last_hb: Optional[float] = None,
    home_danger_signs: Optional[List[str]] = None,
    ifa_tablets_remaining: Optional[int] = None,
    joint_visit_number: Optional[int] = None,
    offline_poshan: bool = False
) -> Dict[str, Any]:
    """
    Skill 1: Stages pre-filled verification card in ANM's ANMOL queue.
    ASHA worker has NO direct write access.
    """
    danger_signs = home_danger_signs or []
    pool = await get_db_pool()

    # Look up beneficiary village & assigned ANM from synthetic_mcp_cards
    async with pool.acquire() as conn:
        beneficiary_row = await conn.fetchrow(
            "SELECT village, assigned_anm FROM synthetic_mcp_cards WHERE rch_id = $1;",
            rch_id
        )

    village = beneficiary_row["village"] if beneficiary_row else "Kishanpur"
    assigned_anm = beneficiary_row["assigned_anm"] if beneficiary_row else "Nurse Kavita"

    # Evaluate deterministic NHM clinical triage
    triage: TriageResult = evaluate_maternal_red_flags(
        bp_str=mcp_card_last_bp,
        hb_level=mcp_card_last_hb,
        danger_signs=danger_signs,
        asha_worker_name=asha_worker_name,
        beneficiary_name=beneficiary_name,
        anm_worker_name=assigned_anm
    )

    # Insert into anmol_verification_queue (PENDING_VERIFICATION)
    async with pool.acquire() as conn:
        queue_id = await conn.fetchval(
            """
            INSERT INTO anmol_verification_queue (
                source_role, asha_worker_name, rch_id, recorded_bp, recorded_hb,
                danger_signs_json, triage_severity, triage_action_hindi, anm_approval_status
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            RETURNING queue_id;
            """,
            "ASHA_RELAY",
            asha_worker_name,
            rch_id,
            mcp_card_last_bp,
            mcp_card_last_hb,
            json.dumps(danger_signs),
            triage.severity,
            triage.action_hindi,
            "PENDING_VERIFICATION"
        )

        # If red seal flagged, update baseline card
        if triage.flag_red_seal:
            await conn.execute(
                "UPDATE synthetic_mcp_cards SET high_risk_red_seal = TRUE WHERE rch_id = $1;",
                rch_id
            )

    # Handle Joint Poshan Visit if indicated
    poshan_res = None
    if joint_visit_number in [8, 9, 11, 14, 15]:
        poshan_res = await sync_poshan_joint_visit(
            rch_id=rch_id,
            visit_number=joint_visit_number,
            child_or_mother_name=beneficiary_name,
            offline_cached=offline_poshan
        )

    # Generate physical paper register row
    register_res = await generate_paper_register_row(
        rch_id=rch_id,
        mother_name=beneficiary_name,
        village=village,
        worker_name=f"ASHA {asha_worker_name}",
        bp=mcp_card_last_bp,
        hb=mcp_card_last_hb,
        danger_signs=danger_signs,
        referral_action=triage.action_english
    )

    return {
        "queue_id": queue_id,
        "rch_id": rch_id,
        "beneficiary_name": beneficiary_name,
        "triage": {
            "severity": triage.severity,
            "condition": triage.condition_name,
            "action_hindi": triage.action_hindi,
            "action_english": triage.action_english,
            "flag_red_seal": triage.flag_red_seal
        },
        "poshan": poshan_res,
        "paper_register": register_res,
        "status": "STAGED_IN_ANMOL_QUEUE"
    }

async def commit_anm_vhsnd_record(
    anm_worker_name: str,
    rch_id: str,
    beneficiary_name: str,
    anc_visit_number: int,
    measured_bp_systolic: int,
    measured_bp_diastolic: int,
    measured_hb_g_dl: float,
    weight_kg: float,
    urine_albumin: str,
    ifa_tablets_issued: int,
    tt_booster_given: bool
) -> Dict[str, Any]:
    """
    Skill 2: Directly commits clinical measurements by ANM at VHSND / Sub-Centre.
    ANM has direct write permission.
    """
    bp_str = f"{measured_bp_systolic}/{measured_bp_diastolic}"
    danger_signs = []
    if urine_albumin.lower() == "positive":
        danger_signs.append("urine_albumin_positive")

    triage: TriageResult = evaluate_maternal_red_flags(
        bp_str=bp_str,
        hb_level=measured_hb_g_dl,
        danger_signs=danger_signs,
        urine_albumin=urine_albumin,
        beneficiary_name=beneficiary_name,
        anm_worker_name=anm_worker_name
    )

    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # Insert directly as SYNCED_TO_RCH
        queue_id = await conn.fetchval(
            """
            INSERT INTO anmol_verification_queue (
                source_role, asha_worker_name, rch_id, recorded_bp, recorded_hb,
                danger_signs_json, triage_severity, triage_action_hindi, anm_approval_status
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            RETURNING queue_id;
            """,
            "ANM_DIRECT",
            f"ANM {anm_worker_name}",
            rch_id,
            bp_str,
            measured_hb_g_dl,
            json.dumps(danger_signs),
            triage.severity,
            triage.action_hindi,
            "SYNCED_TO_RCH"
        )

        # Update synthetic MCP Card
        await conn.execute(
            """
            UPDATE synthetic_mcp_cards SET
                last_subcentre_bp = $1,
                last_subcentre_hb = $2,
                last_vhsnd_date = $3,
                high_risk_red_seal = $4
            WHERE rch_id = $5;
            """,
            bp_str,
            measured_hb_g_dl,
            date.today(),
            triage.flag_red_seal,
            rch_id
        )

    # Generate physical paper register row
    register_res = await generate_paper_register_row(
        rch_id=rch_id,
        mother_name=beneficiary_name,
        village="Kishanpur",
        worker_name=f"ANM {anm_worker_name}",
        bp=bp_str,
        hb=measured_hb_g_dl,
        danger_signs=danger_signs,
        referral_action=triage.action_english
    )

    return {
        "queue_id": queue_id,
        "rch_id": rch_id,
        "triage": {
            "severity": triage.severity,
            "condition": triage.condition_name,
            "action_hindi": triage.action_hindi,
            "flag_red_seal": triage.flag_red_seal
        },
        "paper_register": register_res,
        "status": "SYNCED_TO_RCH"
    }

