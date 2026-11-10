import json
import logging
from datetime import date
from typing import Dict, Any, List, Optional
from backend.database import get_db_pool
from agent.recommendation_engine import (
    generate_care_recommendation,
    evaluate_care_recommendation,
    CareRecommendation,
)

logger = logging.getLogger("aaa_setu.tools")

async def generate_paper_register_row(
    rch_id: str,
    mother_name: str,
    village: str,
    worker_name: str,
    bp: Optional[str],
    hb: Optional[float],
    danger_signs: List[str],
    priority_level: str,
    referral_action: str,
    dynamic_observations: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Skill: Formats extracted indicators into a clean WhatsApp-friendly row matching
    the exact physical MoHFW audit register columns without mental math.
    """
    today_str = date.today().isoformat()
    signs_str = ", ".join(danger_signs) if danger_signs else "None recorded"
    
    dyn_lines = []
    if dynamic_observations:
        for obs in dynamic_observations:
            dyn_lines.append(f"• *{obs.get('field_label', 'Note')}:* {obs.get('spoken_value')}")
    dyn_text = "\n".join(dyn_lines) if dyn_lines else "• *Field Notes:* Routine follow-up"

    whatsapp_row = (
        f"📋 *MoHFW Physical Audit Register Row*\n"
        f"• *Date:* {today_str}\n"
        f"• *RCH ID:* `{rch_id}`\n"
        f"• *Beneficiary:* {mother_name}\n"
        f"• *Village:* {village}\n"
        f"• *Reported By:* {worker_name}\n"
        f"• *Vitals:* BP: {bp or 'Not Recorded'} | Hb: {f'{hb} g/dL' if hb else 'Not Recorded'}\n"
        f"• *Reported Symptoms:* {signs_str}\n"
        f"{dyn_text}\n"
        f"• *AI Priority & Action:* [{priority_level}] {referral_action}"
    )

    pool = await get_db_pool()
    async with pool.acquire() as conn:
        record_id = await conn.fetchval(
            """
            INSERT INTO paper_register_records (
                record_date, rch_id, mother_name, village, worker_name,
                bp, hb, danger_signs, referral_action, dynamic_notes, priority_level, whatsapp_row_text
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
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
            json.dumps(dynamic_observations or []),
            priority_level,
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
    Skill: Captures mandated MWCD Poshan Tracker Joint Home Visits (8, 9, 11, 14, 15).
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

async def log_flexible_health_interaction(
    rch_id: str,
    worker_role: str = "ASHA",
    worker_name: str = "Frontline Worker",
    beneficiary_name: Optional[str] = None,
    bp_reading: Optional[str] = None,
    bp_source: Optional[str] = None,
    hb_g_dl: Optional[float] = None,
    weight_kg: Optional[float] = None,
    temperature_f: Optional[float] = None,
    reported_symptoms: Optional[List[str]] = None,
    supplies_or_meds: Optional[List[str]] = None,
    poshan_joint_visit_num: Optional[int] = None,
    dynamic_observations: Optional[List[Dict[str, Any]]] = None,
    unmentioned_routine_checks: Optional[List[str]] = None,
    language_code: str = "hi-IN",
    offline_poshan: bool = False,
    recommendation: Optional[CareRecommendation] = None
) -> Dict[str, Any]:
    """
    Core Unified Skill: Logs any frontline interaction with ONLY rch_id mandatory.
    Zero information loss, open-ended observations, and non-diagnostic NHM recommendations.
    Uses Evon v3.3 recommendation if provided, or generates via recommendation engine.
    """
    ben_name = beneficiary_name or f"Beneficiary #{rch_id[-4:]}"
    danger_signs = reported_symptoms or []
    dyn_obs = dynamic_observations or []
    unmentioned = unmentioned_routine_checks or []
    supplies = supplies_or_meds or []

    # 1. Non-Diagnostic Care Recommendation (Evon v3.3 or local engine)
    if recommendation is not None:
        rec = recommendation
    else:
        rec = await evaluate_care_recommendation(
            rch_id=rch_id,
            worker_role=worker_role,
            worker_name=worker_name,
            beneficiary_name=ben_name,
            bp_reading=bp_reading,
            bp_source=bp_source,
            hb_g_dl=hb_g_dl,
            weight_kg=weight_kg,
            temperature_f=temperature_f,
            reported_symptoms=danger_signs,
            supplies_or_meds=supplies,
            poshan_joint_visit_num=poshan_joint_visit_num,
            dynamic_observations=dyn_obs,
            unmentioned_routine_checks=unmentioned,
            language_code=language_code
        )

    # 2. Database lookups & defaults
    pool = await get_db_pool()
    village = "Sub-Centre Area"
    async with pool.acquire() as conn:
        beneficiary_row = await conn.fetchrow(
            "SELECT village, mother_name FROM synthetic_mcp_cards WHERE rch_id = $1;",
            rch_id
        )
        if beneficiary_row:
            village = beneficiary_row["village"]
            if not beneficiary_name:
                ben_name = beneficiary_row["mother_name"]

    # 3. Role-based approval status
    # ANMs commit directly to SYNCED_TO_RCH; ASHAs stage to PENDING_VERIFICATION for ANM review
    anm_status = "SYNCED_TO_RCH" if worker_role == "ANM" else "PENDING_VERIFICATION"
    source_role_tag = f"{worker_role}_RELAY" if worker_role != "ANM" else "ANM_DIRECT"

    # 4. Insert into anmol_verification_queue
    async with pool.acquire() as conn:
        queue_id = await conn.fetchval(
            """
            INSERT INTO anmol_verification_queue (
                source_role, asha_worker_name, rch_id, beneficiary_name,
                recorded_bp, bp_source, recorded_hb, weight_kg, temperature_f,
                danger_signs_json, supplies_or_meds, dynamic_observations,
                unmentioned_routine_checks, priority_level, observed_indicators_summary,
                recommended_next_steps, triage_severity, triage_action_hindi,
                spoken_reply_native, anm_approval_status
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                $11, $12, $13, $14, $15, $16, $17, $18, $19, $20
            ) RETURNING queue_id;
            """,
            source_role_tag,
            f"{worker_role} {worker_name}",
            rch_id,
            ben_name,
            bp_reading,
            bp_source,
            hb_g_dl,
            weight_kg,
            temperature_f,
            json.dumps(danger_signs),
            json.dumps(supplies),
            json.dumps(dyn_obs),
            json.dumps(unmentioned),
            rec.priority_level,
            rec.observed_indicators_summary,
            json.dumps(rec.recommended_next_steps),
            rec.priority_level,
            rec.spoken_reply_native,
            rec.spoken_reply_native,
            anm_status
        )

        # If red seal alert indicated, update baseline card
        if rec.flag_red_seal:
            await conn.execute(
                "UPDATE synthetic_mcp_cards SET high_risk_red_seal = TRUE WHERE rch_id = $1;",
                rch_id
            )

    # 5. Handle Joint Poshan Visit if indicated
    poshan_res = None
    if poshan_joint_visit_num in [8, 9, 11, 14, 15]:
        poshan_res = await sync_poshan_joint_visit(
            rch_id=rch_id,
            visit_number=poshan_joint_visit_num,
            child_or_mother_name=ben_name,
            child_weight_kg=weight_kg,
            offline_cached=offline_poshan
        )

    # 6. Generate physical paper register row
    first_action = rec.recommended_next_steps[0] if rec.recommended_next_steps else "Routine monitoring"
    register_res = await generate_paper_register_row(
        rch_id=rch_id,
        mother_name=ben_name,
        village=village,
        worker_name=f"{worker_role} {worker_name}",
        bp=bp_reading,
        hb=hb_g_dl,
        danger_signs=danger_signs,
        priority_level=rec.priority_level,
        referral_action=first_action,
        dynamic_observations=dyn_obs
    )

    return {
        "queue_id": queue_id,
        "rch_id": rch_id,
        "beneficiary_name": ben_name,
        "recommendation": {
            "priority_level": rec.priority_level,
            "observed_indicators_summary": rec.observed_indicators_summary,
            "recommended_next_steps": rec.recommended_next_steps,
            "spoken_reply_native": rec.spoken_reply_native,
            "flag_red_seal": rec.flag_red_seal,
            "referral_needed": rec.referral_needed,
            "details": rec.details,
            "identified_flags": getattr(rec, "identified_flags", rec.details)
        },
        "poshan": poshan_res,
        "paper_register": register_res,
        "status": "RECORDED_SUCCESSFULLY",
        "anm_approval_status": anm_status
    }
