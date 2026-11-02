from dataclasses import dataclass, field
from typing import List, Optional, Tuple

@dataclass
class TriageResult:
    severity: str  # "NORMAL", "URGENT", "CRITICAL_RED_SEAL"
    condition_name: str
    action_hindi: str
    action_english: str
    flag_red_seal: bool = False
    referral_needed: bool = False
    details: List[str] = field(default_factory=list)

def parse_bp(bp_str: Optional[str]) -> Tuple[Optional[int], Optional[int]]:
    if not bp_str:
        return None, None
    clean = bp_str.replace("by", "/").replace(" ", "").strip()
    if "/" in clean:
        parts = clean.split("/")
        try:
            return int(parts[0]), int(parts[1])
        except ValueError:
            return None, None
    return None, None

def evaluate_maternal_red_flags(
    bp_str: Optional[str] = None,
    hb_level: Optional[float] = None,
    danger_signs: Optional[List[str]] = None,
    urine_albumin: Optional[str] = None,
    asha_worker_name: str = "Geeta",
    beneficiary_name: str = "Sunita Devi",
    anm_worker_name: str = "Nurse Kavita"
) -> TriageResult:
    """
    Deterministic NHM maternal triage engine combining clinical vitals
    with reported danger signs according to National Health Mission guidelines.
    """
    signs = [s.lower().strip() for s in (danger_signs or [])]
    systolic, diastolic = parse_bp(bp_str)
    details = []

    has_edema = any(s in signs for s in ["pedal_edema", "edema", "sujan", "swelling", "pairon mein sujan"])
    has_headache = any(s in signs for s in ["severe_headache", "headache", "sar dard", "tez sar dard"])
    has_vision = any(s in signs for s in ["blurred_vision", "vision", "dhundhla dikhna"])
    has_bleeding = any(s in signs for s in ["bleeding", "rakt srav", "khoon aana"])
    has_fever = any(s in signs for s in ["high_fever", "fever", "tez bukhar"])
    albumin_positive = (urine_albumin or "").lower() == "positive"

    # Rule 1: Severe Pre-Eclampsia / Eclampsia Risk (CRITICAL)
    # Systolic >= 140 OR Diastolic >= 90 AND at least one pre-eclampsia symptom
    high_bp = (systolic is not None and systolic >= 140) or (diastolic is not None and diastolic >= 90)
    has_preeclampsia_symptoms = has_edema or has_headache or has_vision or albumin_positive

    if high_bp and has_preeclampsia_symptoms:
        symptoms_str = []
        if has_edema: symptoms_str.append("pairon mein sujan")
        if has_headache: symptoms_str.append("tez sar dard")
        if has_vision: symptoms_str.append("dhundhla dikhna")
        if albumin_positive: symptoms_str.append("urine albumin positive")
        symp_desc = " aur ".join(symptoms_str)

        hindi_msg = (
            f"{asha_worker_name} ji, {beneficiary_name} ki report {anm_worker_name} Didi ke ANMOL queue mein bhej di gayi hai. "
            f"Savdhaan: BP {bp_str or '142/92'} ke saath {symp_desc} Pre-Eclampsia ke gambhir lakshan hain. "
            f"{beneficiary_name} ko turant PHC le jaayein."
        )
        return TriageResult(
            severity="CRITICAL_RED_SEAL",
            condition_name="Severe Pre-Eclampsia Risk",
            action_hindi=hindi_msg,
            action_english=f"Critical: Elevated BP ({bp_str}) with {symp_desc}. Pre-eclampsia danger signs. Immediate PHC referral & Red Seal stamp.",
            flag_red_seal=True,
            referral_needed=True,
            details=[f"BP: {bp_str}", f"Symptoms: {', '.join(signs)}"]
        )

    # Rule 2: Severe Antepartum Bleeding
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
            details=["Active Bleeding Observed"]
        )

    # Rule 3: Severe Maternal Anemia (Hb < 7.0 g/dL)
    if hb_level is not None and hb_level < 7.0:
        hindi_msg = (
            f"Savdhaan: {beneficiary_name} ka Hemoglobin {hb_level} g/dL hai, jo gambhir Anemia (Severe Anemia) hai. "
            f"Turant PHC Medical Officer se iron sucrose ya blood transfusion ke liye sampark karein."
        )
        return TriageResult(
            severity="CRITICAL_RED_SEAL",
            condition_name="Severe Maternal Anemia",
            action_hindi=hindi_msg,
            action_english=f"Critical Anemia: Hb {hb_level} g/dL (< 7.0). Requires emergency Medical Officer assessment for IV iron sucrose.",
            flag_red_seal=True,
            referral_needed=True,
            details=[f"Hemoglobin: {hb_level} g/dL"]
        )

    # Rule 4: Borderline Hypertension Watch (URGENT)
    # Systolic >= 135 OR Diastolic >= 85 AND edema or headache
    borderline_bp = (systolic is not None and systolic >= 135) or (diastolic is not None and diastolic >= 85)
    if borderline_bp and (has_edema or has_headache):
        hindi_msg = (
            f"Savdhaan: Borderline BP {bp_str} aur lakshan dekhe gaye hain. "
            f"ANM Sub-Centre par aaj hi {beneficiary_name} ki dubara BP jaanch karayein."
        )
        return TriageResult(
            severity="URGENT",
            condition_name="Borderline Hypertension Watch",
            action_hindi=hindi_msg,
            action_english=f"Urgent: Borderline BP ({bp_str}) with swelling/headache. Same-day ANM Sub-Centre BP re-check required.",
            flag_red_seal=False,
            referral_needed=True,
            details=[f"BP: {bp_str}", f"Symptoms: {', '.join(signs)}"]
        )

    # Rule 5: Moderate Anemia (7.0 <= Hb < 9.0 g/dL)
    if hb_level is not None and hb_level < 9.0:
        hindi_msg = (
            f"{beneficiary_name} ka Hemoglobin {hb_level} g/dL madhyam anemia darshata hai. "
            f"IFA ki 2 goli pratidin lene ki salah dein aur aahar mein hare patte wali sabziyan shamil karein."
        )
        return TriageResult(
            severity="URGENT",
            condition_name="Moderate Maternal Anemia",
            action_hindi=hindi_msg,
            action_english=f"Urgent: Moderate Anemia (Hb {hb_level} g/dL). Enforce therapeutic double IFA regimen and dietary counseling.",
            flag_red_seal=False,
            referral_needed=False,
            details=[f"Hemoglobin: {hb_level} g/dL"]
        )

    # Rule 6: Normal Checkup
    hindi_msg = (
        f"{beneficiary_name} ki sabhi jaanch samanya hain. "
        f"Poshan, IFA goli aur agle VHSND camp ki niyamit jaanch sunishchit karein."
    )
    return TriageResult(
        severity="NORMAL",
        condition_name="Normal Pregnancy Progress",
        action_hindi=hindi_msg,
        action_english="Vitals and symptoms are within normal parameters. Continue standard ANC counseling and IFA supplementation.",
        flag_red_seal=False,
        referral_needed=False,
        details=[f"BP: {bp_str or 'Normal'}", f"Hb: {hb_level or 'Normal'}"]
    )

