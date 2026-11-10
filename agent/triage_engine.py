import re
import json
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any
import httpx
from agent.gnani_config import (
    get_auth_headers,
    GNANI_EVON_API_BASE,
    GNANI_EVON_MODEL,
)

logger = logging.getLogger("aaa_setu.triage")

# ==============================================================================
# 1. CORE DATA STRUCTURE
# ==============================================================================

@dataclass
class TriageResult:
    """
    Deterministic & Evon-driven maternal triage result.
    Synthesizes clinical vitals, spoken danger signs, and historical MCP card readings.
    """
    severity: str  # "NORMAL", "URGENT", "CRITICAL_RED_SEAL"
    condition_name: str
    action_hindi: str
    action_english: str
    flag_red_seal: bool = False
    referral_needed: bool = False
    details: List[str] = field(default_factory=list)
    patient_history_comparison: Optional[str] = None

# ==============================================================================
# 2. HELPER UTILITIES
# ==============================================================================

def parse_bp(bp_str: Optional[str]) -> Tuple[Optional[int], Optional[int]]:
    if not bp_str:
        return None, None
    clean = str(bp_str).replace("by", "/").replace(" ", "").strip()
    if "/" in clean:
        parts = clean.split("/")
        try:
            return int(parts[0]), int(parts[1])
        except ValueError:
            return None, None
    return None, None

# ==============================================================================
# 3. EVON v3.3 CLINICAL TRIAGE & HISTORY EVALUATION PROMPT
# ==============================================================================

EVON_CLINICAL_TRIAGE_PROMPT = """You are Gnani Evon v3.3, a sovereign medical decision-support AI built for India's frontline healthcare workers (ASHA, ANM, AWW).
Your task is to analyze frontline maternal health interactions, UNDERSTAND THE NATURAL LANGUAGE MEANING of spoken symptoms and clinical signs, and CROSS-REFERENCE with the PATIENT'S PHYSICAL MCP CARD HISTORY.

CLINICAL REASONING MANDATE:
- Understand the real semantic meaning of what has been said (handling conversational descriptions, regional dialects, and negations like "sujan nahi hai" vs "severe swelling").
- Cross-reference current vitals against patient baseline history from the MCP card:
  * Baseline BP: Check if current BP represents an acute surge over baseline (e.g., systolic rise >= 30 mmHg or diastolic rise >= 15 mmHg over early pregnancy baseline is an acute pre-eclampsia alert).
  * Baseline Hb: Check for rapid drop in hemoglobin.
  * Past High Risk Status: Prior red-seal indicators warrant heightened vigilance.
- You are a non-diagnostic decision-support tool. Do not state definitive clinical diagnoses. Frame all findings as risk indicators for ANM / Medical Officer review.

TRIAGE SEVERITY CRITERIA:
1. "CRITICAL_RED_SEAL":
   - Systolic BP >= 140 mmHg OR Diastolic BP >= 90 mmHg (or acute hypertensive surge over baseline) combined with ANY pre-eclampsia symptom (pedal/facial edema, severe persistent headache, blurred vision, or proteinuria).
   - Active maternal vaginal bleeding / antepartum or postpartum hemorrhage.
   - Severe maternal anemia (Hemoglobin < 7.0 g/dL).
   - Convulsions or altered sensorium.
   Actions: Advise immediate clinical evaluation by Medical Officer at PHC/FRU, call 108 ambulance, stamp MCP Card Red Seal alert.

2. "URGENT":
   - Borderline hypertension (Systolic 130-139 mmHg or Diastolic 85-89 mmHg) without acute neurological danger signs.
   - Moderate anemia (Hemoglobin 7.0 to 10.9 g/dL).
   - Moderate symptoms or isolated concerns requiring priority Sub-Centre check.
   Actions: Same-day or priority re-check by ANM at Sub-Centre / VHSND, therapeutic dietary/iron counseling.

3. "NORMAL":
   - Vitals and symptoms consistent with baseline and within healthy parameters.
   Actions: Continue standard ANC counseling, IFA supplementation, and routine VHSND monitoring.

Output MUST be valid JSON with keys:
{
  "severity": "CRITICAL_RED_SEAL",
  "condition_name": "Severe Pre-Eclampsia Risk Alert",
  "action_hindi": "गीत जी, सुनिता देवी की रिपोर्ट ANMOL कतार में भेज दी गई है। सावधान: BP 142/92 के साथ पैरों में सूजन Pre-Eclampsia के गंभीर लक्षण हैं। सुनिता देवी को तुरंत PHC ले जाएं।",
  "action_english": "Critical: Elevated BP (142/92) with pedal edema and headache represents acute pre-eclampsia danger. Immediate PHC referral & Red Seal stamp.",
  "flag_red_seal": true,
  "referral_needed": true,
  "details": ["Current BP: 142/92 vs baseline 110/70 (+32/+22 mmHg surge)", "Reported pedal edema"],
  "patient_history_comparison": "Current BP 142/92 is an acute surge above baseline Sub-Centre BP 110/70."
}
"""

# ==============================================================================
# 4. EVON v3.3 ASYNC TRIAGE PIPELINE
# ==============================================================================

async def evaluate_maternal_triage_with_evon(
    bp_str: Optional[str] = None,
    hb_level: Optional[float] = None,
    danger_signs: Optional[List[str]] = None,
    urine_albumin: Optional[str] = None,
    asha_worker_name: str = "ASHA",
    beneficiary_name: str = "Beneficiary",
    anm_worker_name: str = "ANM",
    patient_history: Optional[Dict[str, Any]] = None,
    spoken_utterance: Optional[str] = None,
    language_code: str = "hi-IN",
    base_url: Optional[str] = None,
    model: Optional[str] = None,
) -> TriageResult:
    """
    Routes maternal triage through Gnani Evon v3.3 (30B Hybrid Mamba2-MoE),
    understanding conversational nuance, symptom meaning, and patient history.
    """
    endpoint = (base_url or GNANI_EVON_API_BASE or "").rstrip("/")
    target_model = model or GNANI_EVON_MODEL

    if not endpoint:
        raise ValueError("GNANI_EVON_API_BASE is not configured.")

    payload = {
        "current_vitals": {
            "bp": bp_str,
            "hb": hb_level,
            "urine_albumin": urine_albumin
        },
        "danger_signs": danger_signs or [],
        "spoken_utterance": spoken_utterance or "",
        "patient_history": patient_history or {},
        "worker_names": {
            "asha": asha_worker_name,
            "anm": anm_worker_name,
            "beneficiary": beneficiary_name
        },
        "language_code": language_code
    }

    messages = [
        {"role": "system", "content": EVON_CLINICAL_TRIAGE_PROMPT},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}
    ]

    headers = get_auth_headers()
    headers["Content-Type"] = "application/json"

    body = {
        "model": target_model,
        "messages": messages,
        "temperature": 0.5,
        "top_p": 0.95,
        "enable_thinking": False,
        "response_format": {"type": "json_object"}
    }

    url = f"{endpoint}/chat/completions"
    logger.info(f"Routing clinical triage to Evon v3.3 at {url}...")

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, headers=headers, json=body)
        if response.status_code != 200:
            raise RuntimeError(f"Evon Triage Inference Error [HTTP {response.status_code}]: {response.text}")
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(content)

        severity = parsed.get("severity", "NORMAL")
        cond = parsed.get("condition_name", "Maternal Health Review")
        act_hi = parsed.get("action_hindi", "Report save ho gayi hai.")
        act_en = parsed.get("action_english", "Visit recorded.")
        red_seal = bool(parsed.get("flag_red_seal", severity == "CRITICAL_RED_SEAL"))
        referral = bool(parsed.get("referral_needed", severity == "CRITICAL_RED_SEAL"))
        details = parsed.get("details", [])
        hist_comp = parsed.get("patient_history_comparison")

        return TriageResult(
            severity=severity,
            condition_name=cond,
            action_hindi=act_hi,
            action_english=act_en,
            flag_red_seal=red_seal,
            referral_needed=referral,
            details=details,
            patient_history_comparison=hist_comp
        )

# ==============================================================================
# 5. DYNAMIC CONTEXT-AWARE TRIAGE (WITH PATIENT HISTORY CROSS-REFERENCE)
# ==============================================================================

def evaluate_maternal_red_flags(
    bp_str: Optional[str] = None,
    hb_level: Optional[float] = None,
    danger_signs: Optional[List[str]] = None,
    urine_albumin: Optional[str] = None,
    asha_worker_name: str = "ASHA",
    beneficiary_name: str = "Beneficiary",
    anm_worker_name: str = "ANM",
    patient_history: Optional[Dict[str, Any]] = None,
    spoken_utterance: Optional[str] = None,
    language_code: str = "hi-IN"
) -> TriageResult:
    """
    Context-aware maternal triage engine.
    Understands symptom meaning, handles negations, and cross-references findings
    against the patient's physical MCP card history (baseline BP, baseline Hb, past red seals).
    Seamlessly integrates with Evon v3.3 when configured.
    """
    signs = [s.lower().strip() for s in (danger_signs or [])]
    systolic, diastolic = parse_bp(bp_str)
    history = patient_history or {}

    # Extract Baseline Readings from Patient MCP Card History
    base_bp_str = history.get("last_subcentre_bp")
    base_hb = history.get("last_subcentre_hb")
    prev_red_seal = bool(history.get("high_risk_red_seal", False))
    base_sys, base_dia = parse_bp(base_bp_str)

    # Calculate Clinically Meaningful History Differentials (NHM/FOGSI Guidelines)
    history_comparison_notes: List[str] = []
    has_acute_bp_surge = False
    has_acute_hb_drop = False

    if systolic is not None and base_sys is not None:
        delta_sys = systolic - base_sys
        delta_dia = (diastolic - base_dia) if (diastolic is not None and base_dia is not None) else 0
        if delta_sys >= 30 or delta_dia >= 15:
            has_acute_bp_surge = True
            history_comparison_notes.append(
                f"Acute BP surge over baseline ({base_bp_str} -> {bp_str}, +{delta_sys}/+{delta_dia} mmHg)"
            )
        elif delta_sys > 10 or delta_dia > 5:
            history_comparison_notes.append(
                f"Elevated compared to baseline Sub-Centre BP ({base_bp_str} -> {bp_str})"
            )

    if hb_level is not None and base_hb is not None:
        try:
            base_hb_f = float(base_hb)
            delta_hb = hb_level - base_hb_f
            if delta_hb <= -2.0:
                has_acute_hb_drop = True
                history_comparison_notes.append(
                    f"Rapid Hb drop from baseline ({base_hb_f} -> {hb_level} g/dL, {delta_hb:+.1f})"
                )
        except (ValueError, TypeError):
            pass

    if prev_red_seal:
        history_comparison_notes.append("Patient has existing High-Risk Red Seal on MCP card")

    # Semantic Symptom Understanding (Negation & Meaning Aware)
    # Checks both structured danger signs and raw spoken utterance
    spoken_text = (spoken_utterance or "").lower()

    def symptom_present(keywords: List[str], negation_targets: List[str]) -> bool:
        # Check structured danger signs first
        for s in signs:
            if any(k in s for k in keywords):
                return True
        # Check spoken utterance with negation protection (e.g. "sujan nahi hai")
        for kw in keywords:
            if kw in spoken_text:
                # Check if immediately preceded or followed by negation words
                neg_pattern = rf'(?:nahi|nhi|na|no|without|bina)\s+{kw}|{kw}\s+(?:nahi|nhi|na)'
                if not re.search(neg_pattern, spoken_text):
                    return True
        return False

    has_edema = symptom_present(["edema", "sujan", "swelling", "pairon mein sujan", "सूजन"], ["sujan"])
    has_headache = symptom_present(["headache", "sar dard", "tez sar dard", "डोकेदुखी", "ମୁଣ୍ଡବିନ୍ଦା"], ["sar dard"])
    has_vision = symptom_present(["vision", "dhundhla", "blurred", "आंखों में धुंधला"], ["dhundhla"])
    has_bleeding = symptom_present(["bleeding", "rakt srav", "khoon", "bleeding", "रक्तस्राव"], ["bleeding", "khoon"])
    has_fever = symptom_present(["fever", "bukhar", "tez bukhar", "ताप", "ଜ୍ୱର"], ["bukhar"])
    albumin_positive = (urine_albumin or "").lower() == "positive" or "albumin" in spoken_text

    # Absolute and Surge Hypertensive Classifications
    high_bp = (systolic is not None and systolic >= 140) or (diastolic is not None and diastolic >= 90) or has_acute_bp_surge
    borderline_bp = (systolic is not None and systolic >= 135) or (diastolic is not None and diastolic >= 85)

    has_preeclampsia_symptoms = has_edema or has_headache or has_vision or albumin_positive

    # Contextual Clinical Decision Engine
    # --------------------------------------------------------------------------
    # Rule 1: Severe Pre-Eclampsia / Hypertensive Crisis (CRITICAL_RED_SEAL)
    # Triggered by high BP or acute surge over baseline combined with pre-eclampsia indicators
    if high_bp and has_preeclampsia_symptoms:
        symptoms_str = []
        if has_edema: symptoms_str.append("pairon mein sujan")
        if has_headache: symptoms_str.append("tez sar dard")
        if has_vision: symptoms_str.append("dhundhla dikhna")
        if albumin_positive: symptoms_str.append("urine albumin positive")
        symp_desc = " aur ".join(symptoms_str) or "danger signs"

        hist_str = f" (Baseline: {base_bp_str})" if base_bp_str else ""
        details_list = [f"BP: {bp_str}{hist_str}", f"Symptoms: {', '.join(signs)}"]
        if history_comparison_notes:
            details_list.extend(history_comparison_notes)

        hindi_msg = (
            f"{asha_worker_name} ji, {beneficiary_name} ki report {anm_worker_name} Didi ke ANMOL queue mein bhej di gayi hai. "
            f"Savdhaan: BP {bp_str or '142/92'} ke saath {symp_desc} Pre-Eclampsia ke gambhir lakshan hain. "
            f"{beneficiary_name} ko turant PHC le jaayein."
        )
        return TriageResult(
            severity="CRITICAL_RED_SEAL",
            condition_name="Severe Pre-Eclampsia Risk Alert",
            action_hindi=hindi_msg,
            action_english=(
                f"Critical: Elevated BP ({bp_str}) with {symp_desc}. Pre-eclampsia danger signs. "
                f"{'; '.join(history_comparison_notes) if history_comparison_notes else ''} "
                f"Immediate PHC referral & Red Seal stamp."
            ).strip(),
            flag_red_seal=True,
            referral_needed=True,
            details=details_list,
            patient_history_comparison="; ".join(history_comparison_notes) if history_comparison_notes else None
        )

    # Rule 2: Active Maternal Bleeding / Obstetric Hemorrhage (CRITICAL_RED_SEAL)
    if has_bleeding:
        hindi_msg = (
            f"Aapatkaal: {beneficiary_name} ko rakt srav (bleeding) ho raha hai. "
            f"Yeh ek gambhir khatra hai. 108 ambulance bulakar turant FRU/District Hospital le jaayein."
        )
        return TriageResult(
            severity="CRITICAL_RED_SEAL",
            condition_name="Antepartum Hemorrhage Alert",
            action_hindi=hindi_msg,
            action_english="Critical: Active maternal hemorrhage. Immediate 108 ambulance transfer to FRU.",
            flag_red_seal=True,
            referral_needed=True,
            details=["Active Bleeding Observed"] + history_comparison_notes,
            patient_history_comparison="; ".join(history_comparison_notes) if history_comparison_notes else None
        )

    # Rule 3: Severe Maternal Anemia (Hb < 7.0 g/dL or acute drop) (CRITICAL_RED_SEAL)
    if (hb_level is not None and hb_level < 7.0) or (has_acute_hb_drop and hb_level is not None and hb_level < 8.0):
        hindi_msg = (
            f"Savdhaan: {beneficiary_name} ka Hemoglobin {hb_level} g/dL hai, jo gambhir Anemia (Severe Anemia) hai. "
            f"Turant PHC Medical Officer se iron sucrose ya blood transfusion ke liye sampark karein."
        )
        return TriageResult(
            severity="CRITICAL_RED_SEAL",
            condition_name="Severe Maternal Anemia",
            action_hindi=hindi_msg,
            action_english=(
                f"Critical Anemia: Hb {hb_level} g/dL (< 7.0). Requires emergency Medical Officer assessment. "
                f"{'; '.join(history_comparison_notes) if history_comparison_notes else ''}"
            ).strip(),
            flag_red_seal=True,
            referral_needed=True,
            details=[f"Hemoglobin: {hb_level} g/dL"] + history_comparison_notes,
            patient_history_comparison="; ".join(history_comparison_notes) if history_comparison_notes else None
        )

    # Rule 4: Borderline Hypertension Watch (URGENT)
    if borderline_bp and (has_edema or has_headache or prev_red_seal):
        hindi_msg = (
            f"Savdhaan: Borderline BP {bp_str} aur lakshan dekhe gaye hain. "
            f"ANM Sub-Centre par aaj hi {beneficiary_name} ki dubara BP jaanch karayein."
        )
        return TriageResult(
            severity="URGENT",
            condition_name="Borderline Hypertension Watch",
            action_hindi=hindi_msg,
            action_english=(
                f"Urgent: Borderline BP ({bp_str}) with swelling/headache. "
                f"{'; '.join(history_comparison_notes) if history_comparison_notes else ''} "
                f"Same-day ANM Sub-Centre BP re-check required."
            ).strip(),
            flag_red_seal=False,
            referral_needed=True,
            details=[f"BP: {bp_str}", f"Symptoms: {', '.join(signs)}"] + history_comparison_notes,
            patient_history_comparison="; ".join(history_comparison_notes) if history_comparison_notes else None
        )

    # Rule 5: Moderate Anemia (7.0 <= Hb < 9.0 g/dL) (URGENT)
    if hb_level is not None and hb_level < 9.0:
        hindi_msg = (
            f"{beneficiary_name} ka Hemoglobin {hb_level} g/dL madhyam anemia darshata hai. "
            f"IFA ki 2 goli pratidin lene ki salah dein aur aahar mein hare patte wali sabziyan shamil karein."
        )
        return TriageResult(
            severity="URGENT",
            condition_name="Moderate Maternal Anemia",
            action_hindi=hindi_msg,
            action_english=(
                f"Urgent: Moderate Anemia (Hb {hb_level} g/dL). Enforce therapeutic double IFA regimen. "
                f"{'; '.join(history_comparison_notes) if history_comparison_notes else ''}"
            ).strip(),
            flag_red_seal=False,
            referral_needed=False,
            details=[f"Hemoglobin: {hb_level} g/dL"] + history_comparison_notes,
            patient_history_comparison="; ".join(history_comparison_notes) if history_comparison_notes else None
        )

    # Rule 6: Normal Checkup (NORMAL)
    hist_str = f" Baseline BP {base_bp_str} sustained." if base_bp_str else ""
    hindi_msg = (
        f"{beneficiary_name} ki sabhi jaanch samanya hain. "
        f"Poshan, IFA goli aur agle VHSND camp ki niyamit jaanch sunishchit karein."
    )
    return TriageResult(
        severity="NORMAL",
        condition_name="Normal Pregnancy Progress",
        action_hindi=hindi_msg,
        action_english=(
            f"Vitals and symptoms are within normal parameters.{hist_str} "
            f"Continue standard ANC counseling and IFA supplementation."
        ).strip(),
        flag_red_seal=False,
        referral_needed=False,
        details=[f"BP: {bp_str or 'Normal'}", f"Hb: {hb_level or 'Normal'}"] + history_comparison_notes,
        patient_history_comparison="; ".join(history_comparison_notes) if history_comparison_notes else None
    )
