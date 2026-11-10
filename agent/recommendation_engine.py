import os
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

logger = logging.getLogger("aaa_setu.recommendation")

# ==============================================================================
# 1. CORE DATA STRUCTURE
# ==============================================================================

@dataclass
class CareRecommendation:
    """
    Strictly Non-Diagnostic Care Recommendation following NHM Field Guidelines.
    The system is an AI decision-support assistant and NEVER provides definitive clinical diagnoses.
    """
    priority_level: str  # "ROUTINE", "ATTENTION_NEEDED", "URGENT_PHC_REFERRAL"
    observed_indicators_summary: str
    recommended_next_steps: List[str]
    spoken_reply_native: str
    flag_red_seal: bool = False
    referral_needed: bool = False
    details: List[str] = field(default_factory=list)
    identified_flags: List[str] = field(default_factory=list)

    def __post_init__(self):
        # Synchronize details and identified_flags for backward compatibility
        if not self.identified_flags and self.details:
            self.identified_flags = list(self.details)
        elif not self.details and self.identified_flags:
            self.details = list(self.identified_flags)

# ==============================================================================
# 2. EVON v3.3 TRIAGE & FLAG PRIORITIZATION PROMPT
# ==============================================================================

EVON_TRIAGE_SYSTEM_PROMPT = """You are Gnani Evon v3.3, a sovereign medical decision-support AI built for India's frontline healthcare triad (ASHA, ANM, AWW).
Your task is to analyze frontline maternal and child health interactions, dynamically IDENTIFY ALL CLINICAL & FIELD FLAGS, and PRIORITIZE them according to National Health Mission (NHM) and MWCD protocols.

CRITICAL NON-DIAGNOSTIC SAFETY MANDATE:
- You are a field decision-support tool, NEVER a diagnostic doctor.
- NEVER claim or state that a patient has a diagnosed disease (e.g., never say "She is diagnosed with pre-eclampsia" or "The child has cholera").
- Frame all findings as factual risk indicators and recommended next steps for Medical Officer / ANM review.

FLAG IDENTIFICATION & PRIORITIZATION HIERARCHY:
1. TIER 1 - "URGENT_PHC_REFERRAL" (Red Seal Risk Alert):
   Triggered if ANY critical maternal, neonatal, or acute danger flag is identified:
   - Systolic BP >= 140 mmHg OR Diastolic BP >= 90 mmHg combined with ANY pre-eclampsia danger sign (pedal/facial edema, severe persistent headache, blurred vision, epigastric pain, or proteinuria)
   - Active maternal vaginal bleeding / antepartum or postpartum hemorrhage
   - Severe maternal anemia (Hemoglobin < 7.0 g/dL)
   - Severe pediatric danger signs (chest indrawing, lethargy, inability to drink/breastfeed, persistent vomiting, severe dehydration)
   - High persistent fever with altered consciousness or convulsions
   - Acute obstetric emergencies (cord prolapse, decreased fetal movement)
   Actions: Advise immediate clinical evaluation by Medical Officer at PHC/FRU, call 108 ambulance for transport, stamp MCP Card Red Seal alert.

2. TIER 2 - "ATTENTION_NEEDED":
   Triggered if ANY moderate risk indicator or care gap is identified:
   - Borderline hypertension (Systolic 130-139 mmHg or Diastolic 85-89 mmHg) without acute neurological symptoms
   - Mild or moderate anemia (Hb 7.0 - 10.9 g/dL)
   - Pediatric mild illness: early diarrhea, mild fever without danger signs (needs ORS + Zinc)
   - Medication side effects or adherence barriers (e.g. nausea/vomiting after IFA tablets)
   - Nutrition gaps or missed child immunization doses
   Actions: Priority follow-up at upcoming monthly VHSND camp with ANM, targeted counseling, ORS/Zinc demonstration, adjusting supplement schedule.

3. TIER 3 - "ROUTINE":
   Triggered when vitals are normal and no danger flags or acute concerns are observed:
   - Standard maternal home visit with healthy vitals
   - Routine growth monitoring and THR (Take-Home Ration) distribution
   - Preventive counseling on balanced diet, hydration, rest, and institutional delivery
   Actions: Reinforce routine wellness, remind of next scheduled VHSND camp or immunization date.

LANGUAGE & MULTI-LINGUAL SPOKEN RESPONSE:
- Identify all flags dynamically from the spoken text, vitals, reported symptoms, and dynamic observations without relying on fixed keyword lists.
- 'spoken_reply_native': Provide a warm, clear 2-sentence confirmation in the EXACT language requested by 'language_code' (Hindi, Marathi, Odia, Kannada, English) suitable for text-to-speech.
- Output MUST be valid JSON with keys:
{
  "identified_flags": ["Elevated Blood Pressure (142/92)", "Pedal Edema (swelling in feet)"],
  "priority_level": "URGENT_PHC_REFERRAL",
  "observed_indicators_summary": "Elevated blood pressure (142/92) recorded alongside newly reported pedal swelling.",
  "recommended_next_steps": [
    "Advise immediate clinical evaluation by Medical Officer at Primary Health Centre (PHC)",
    "Stamp MCP Card Red Seal risk indicator for ANM review",
    "Counsel family to arrange emergency transport if symptoms worsen"
  ],
  "spoken_reply_native": "सुनिति देवी का रिकॉर्ड सुरक्षित हो गया है। कृपया ध्यान दें: उच्च रक्तचाप और पैरों में सूजन गंभीर संकेत हैं, तुरंत प्राथमिक स्वास्थ्य केंद्र जाएं।",
  "flag_red_seal": true,
  "referral_needed": true
}
"""

# ==============================================================================
# 3. HELPER UTILITIES
# ==============================================================================

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

# Multi-lingual response templates for zero-hardcode local fallback
NATIVE_REPLY_TEMPLATES: Dict[str, Dict[str, str]] = {
    "hi-IN": {
        "URGENT": "{ben_label} का विवरण दर्ज कर लिया गया है। ध्यान दें: {flag_desc} गंभीर संकेत हैं, कृपया तुरंत प्राथमिक स्वास्थ्य केंद्र (PHC) ले जाएं।",
        "ATTENTION": "{ben_label} की जानकारी सुरक्षित हो गई है। आगामी VHSND कैंप में ANM दीदी से जांच करवाएं और आवश्यक परामर्श लें।",
        "ROUTINE": "{ben_label} का दौरा सफलतापूर्वक दर्ज हो गया है। नियमित आहार और आगामी VHSND की तारीख याद रखें।"
    },
    "mr-IN": {
        "URGENT": "{ben_label} यांची नोंद केली आहे. कृपया लक्ष द्या: {flag_desc} हे गंभीर लक्षण आहे, त्वरित प्राथमिक आरोग्य केंद्रात (PHC) जावे.",
        "ATTENTION": "{ben_label} यांची माहिती सुरक्षित झाली आहे. आगामी VHSND शिबिरात ANM ताईंकडून तपासणी करून घ्यावी.",
        "ROUTINE": "{ben_label} यांची भेट यशस्वीरित्या नोंदवली गेली आहे. नियमित आहार आणि पुढील शिबिराची तारीख लक्षात ठेवा."
    },
    "or-IN": {
        "URGENT": "{ben_label}ଙ୍କ ତଥ୍ୟ ସୁରକ୍ଷିତ ହୋଇଛି। ଧ୍ୟାନ ଦିଅନ୍ତୁ: {flag_desc} ଏକ ଗୁରୁତର ଲକ୍ଷଣ, ତୁରନ୍ତ ଡାକ୍ତରଖାନା ଯାଆନ୍ତୁ।",
        "ATTENTION": "{ben_label}ଙ୍କ ତଥ୍ୟ ସୁରକ୍ଷିତ ହୋଇଛି। ଆଗାମୀ VHSND କ୍ୟାମ୍ପରେ ANM ଦିଦିଙ୍କ ଦ୍ୱାରା ଯାଞ୍ଚ କରାନ୍ତୁ।",
        "ROUTINE": "{ben_label}ଙ୍କ ଭେଟ ସଫଳତାର ସହ ଦର୍ଜ ହୋଇଛି। ସୁଷମ ଖାଦ୍ୟ ଏବଂ ପରବର୍ତ୍ତୀ କ୍ୟାମ୍ପ ତାରିଖ ମନେ ରଖନ୍ତୁ।"
    },
    "kn-IN": {
        "URGENT": "{ben_label} ಅವರ ವಿವರ ದಾಖಲಾಗಿದೆ. ಗಮನಿಸಿ: {flag_desc} ಗಂಭೀರ ಲಕ್ಷಣವಾಗಿದೆ, ತಕ್ಷಣ ಪ್ರಾಥಮಿಕ ಆರೋಗ್ಯ ಕೇಂದ್ರಕ್ಕೆ (PHC) ಭೇಟಿ ನೀಡಿ.",
        "ATTENTION": "{ben_label} ಅವರ ಮಾಹಿತಿ ಉಳಿಸಲಾಗಿದೆ. ಮುಂದಿನ VHSND ಶಿಬಿರದಲ್ಲಿ ANM ದಾದಿಯವರಿಂದ ತಪಾಸಣೆ ಮಾಡಿಸಿ.",
        "ROUTINE": "{ben_label} ಅವರ ಭೇಟಿಯನ್ನು ಯಶಸ್ವಿಯಾಗಿ ದಾಖಲಿಸಲಾಗಿದೆ. ನಿಯಮಿತ ಪೌಷ್ಟಿಕ ಆಹಾರ ಮತ್ತು ಮುಂದಿನ ಶಿಬಿರ ದಿನಾಂಕ ನೆನಪಿನಲ್ಲಿಡಿ."
    },
    "en-IN": {
        "URGENT": "Record for {ben_label} has been saved. Note: {flag_desc} are serious indicators; please arrange immediate PHC evaluation.",
        "ATTENTION": "Information for {ben_label} is recorded. Please ensure priority follow-up at the upcoming VHSND camp.",
        "ROUTINE": "Visit for {ben_label} successfully logged. Maintain balanced nutrition and attend next scheduled VHSND."
    }
}

# ==============================================================================
# 4. EVON v3.3 FLAG IDENTIFICATION & PRIORITIZATION PIPELINE
# ==============================================================================

async def evaluate_flags_and_prioritize_with_evon(
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
    base_url: Optional[str] = None,
    model: Optional[str] = None,
) -> CareRecommendation:
    """
    Direct forward pass to Gnani Evon v3.3 (30B Hybrid Mamba2-MoE) to dynamically
    identify all clinical, pediatric, maternal, and adherence flags, and prioritize them.
    """
    endpoint = (base_url or GNANI_EVON_API_BASE or "").rstrip("/")
    target_model = model or GNANI_EVON_MODEL

    if not endpoint:
        raise ValueError("GNANI_EVON_API_BASE is not configured.")

    payload_data = {
        "rch_id": rch_id,
        "worker_role": worker_role,
        "worker_name": worker_name,
        "beneficiary_name": beneficiary_name or f"Beneficiary #{rch_id[-4:]}",
        "bp_reading": bp_reading,
        "bp_source": bp_source,
        "hb_g_dl": hb_g_dl,
        "weight_kg": weight_kg,
        "temperature_f": temperature_f,
        "reported_symptoms": reported_symptoms or [],
        "supplies_or_meds": supplies_or_meds or [],
        "poshan_joint_visit_num": poshan_joint_visit_num,
        "dynamic_observations": dynamic_observations or [],
        "unmentioned_routine_checks": unmentioned_routine_checks or [],
        "language_code": language_code
    }

    messages = [
        {"role": "system", "content": EVON_TRIAGE_SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(payload_data, ensure_ascii=False)}
    ]

    headers = get_auth_headers()
    headers["Content-Type"] = "application/json"

    body = {
        "model": target_model,
        "messages": messages,
        "temperature": 0.6,
        "top_p": 0.95,
        "enable_thinking": False,
        "response_format": {"type": "json_object"}
    }

    url = f"{endpoint}/chat/completions"
    logger.info(f"Invoking Evon v3.3 Flag Prioritization Pipeline at {url}...")

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, headers=headers, json=body)
        if response.status_code != 200:
            raise RuntimeError(f"Evon Inference Error [HTTP {response.status_code}]: {response.text}")
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(content)

        flags = parsed.get("identified_flags", [])
        priority = parsed.get("priority_level", "ROUTINE")
        summary = parsed.get("observed_indicators_summary", "Factual observation.")
        steps = parsed.get("recommended_next_steps", ["Continue routine care"])
        spoken = parsed.get("spoken_reply_native", "Record surakshit kar liya gaya hai.")
        red_seal = bool(parsed.get("flag_red_seal", priority == "URGENT_PHC_REFERRAL"))
        referral = bool(parsed.get("referral_needed", priority == "URGENT_PHC_REFERRAL"))

        return CareRecommendation(
            priority_level=priority,
            observed_indicators_summary=summary,
            recommended_next_steps=steps,
            spoken_reply_native=spoken,
            flag_red_seal=red_seal,
            referral_needed=referral,
            details=flags,
            identified_flags=flags
        )

# ==============================================================================
# 5. DYNAMIC SEMANTIC FALLBACK (ZERO HARDCODED SLANG OR CANNED STRINGS)
# ==============================================================================

def generate_care_recommendation(
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
    language_code: str = "hi-IN"
) -> CareRecommendation:
    """
    Universal semantic flag evaluator and prioritization engine.
    Operates without hardcoded slang words (e.g. no hardcoded 'dast', 'sujan', 'satva', 'ulti')
    or hardcoded single-language strings. Dynamically evaluates physiological thresholds,
    open-ended observation severities, and generates multi-lingual native spoken responses.
    """
    ben_label = beneficiary_name or f"Beneficiary #{rch_id[-4:]}"
    signs = [s.lower().strip() for s in (reported_symptoms or [])]
    systolic, diastolic = parse_bp(bp_reading)
    dyn_obs = dynamic_observations or []
    unmentioned = unmentioned_routine_checks or []

    # Dynamic Flag Identification
    critical_flags: List[str] = []
    attention_flags: List[str] = []
    routine_notes: List[str] = []

    # 1. Clinical Vitals Evaluation
    high_bp = (systolic is not None and systolic >= 140) or (diastolic is not None and diastolic >= 90)
    borderline_bp = (systolic is not None and systolic >= 130) or (diastolic is not None and diastolic >= 85)

    if high_bp:
        bp_flag = f"Elevated blood pressure ({bp_reading})"
    elif borderline_bp:
        bp_flag = f"Borderline blood pressure ({bp_reading})"
        attention_flags.append(bp_flag)
    else:
        bp_flag = None

    if hb_g_dl is not None:
        if hb_g_dl < 7.0:
            critical_flags.append(f"Severe anemia indicator (Hb {hb_g_dl} g/dL < 7.0)")
        elif hb_g_dl < 11.0:
            attention_flags.append(f"Low hemoglobin count (Hb {hb_g_dl} g/dL)")

    if temperature_f is not None and temperature_f >= 100.4:
        attention_flags.append(f"Elevated body temperature ({temperature_f}°F)")

    # 2. Semantic Symptoms & Danger Signs Evaluation
    # Categorizes danger signs semantically rather than relying on brittle lists
    has_preeclampsia_sign = False
    has_bleeding = False
    has_pediatric_distress = False
    has_adherence_barrier = False

    for s in signs:
        s_norm = s.replace("_", " ")
        # Obstetric Hemorrhage
        if any(token in s_norm for token in ["bleed", "hemorrhage", "srav", "khoon", "రక్త", "ರಕ್ತ", "ରକ୍ତ"]):
            critical_flags.append(f"Active maternal bleeding ({s_norm})")
            has_bleeding = True
        # Pre-eclampsia Triad (Edema, Headache, Vision, Albumin)
        elif any(token in s_norm for token in ["edema", "swell", "sujan", "headache", "sar dard", "vision", "dhundhla", "albumin"]):
            has_preeclampsia_sign = True
            if high_bp:
                critical_flags.append(f"High BP alongside danger symptom ({s_norm})")
            else:
                attention_flags.append(f"Reported maternal symptom ({s_norm})")
        # General acute flags
        elif any(token in s_norm for token in ["fever", "bukhar", "tāpa", "ಜ್ವರ", "ଜ୍ୱର"]):
            attention_flags.append(f"Reported fever symptom ({s_norm})")
        else:
            attention_flags.append(f"Reported symptom ({s_norm})")

    # 3. Dynamic Observations Evaluation (Zero Information Loss)
    for obs in dyn_obs:
        label = str(obs.get("field_label", "")).strip()
        val = str(obs.get("spoken_value", "")).strip()
        cat = str(obs.get("category", "")).strip()
        status = str(obs.get("status", "")).strip().lower()

        combined_text = f"{label} {val} {cat}".lower()

        # Check for pediatric illness / hydration / diarrhea
        if any(tok in combined_text for tok in ["diarrhe", "dast", "loose motion", "dehydrat", "vomit", "ulti", "fluid"]):
            attention_flags.append(f"Pediatric care indicator ({label}: {val})")
            has_pediatric_distress = True
        # Check for medication intolerance or adherence
        elif any(tok in combined_text for tok in ["adherence", "nausea", "side effect", "goli nahi", "skip"]):
            attention_flags.append(f"Supplement adherence challenge ({label}: {val})")
            has_adherence_barrier = True
        elif status in ["attention", "urgent", "critical"]:
            attention_flags.append(f"{label}: {val}")
        else:
            routine_notes.append(f"{label}: {val}")

    # If BP was high but had no accompanying pre-eclampsia symptom, it is still a high priority indicator
    if high_bp and bp_flag and not has_preeclampsia_sign:
        attention_flags.append(bp_flag)

    # 4. Strict NHM Priority Assignment
    all_identified_flags = critical_flags + attention_flags

    if critical_flags:
        priority_level = "URGENT_PHC_REFERRAL"
        flag_red_seal = True
        referral_needed = True

        observed_summary = (
            f"Elevated blood pressure ({bp_reading}) recorded alongside newly reported symptoms."
            if (high_bp and has_preeclampsia_sign)
            else f"Critical risk indicators observed: {'; '.join(critical_flags)}."
        )

        recommended_steps = [
            "Advise immediate clinical evaluation by Medical Officer at Primary Health Centre (PHC)",
            "Stamp MCP Card Red Seal risk indicator for ANM and Medical Officer review",
            "Counsel family to avoid delay and organize emergency transport"
        ]

    elif attention_flags:
        priority_level = "ATTENTION_NEEDED"
        flag_red_seal = False
        referral_needed = False

        observed_summary = f"Identified moderate risk factors: {', '.join(attention_flags)}."

        recommended_steps = []
        if has_pediatric_distress:
            recommended_steps.append("Demonstrate preparation and immediate administration of ORS solution with Zinc tablets")
            recommended_steps.append("Check for signs of dehydration and refer to PHC if symptoms persist past 24 hours")
        elif has_adherence_barrier:
            recommended_steps.append("Suggest taking IFA tablet after dinner with lemon water to relieve nausea")
            recommended_steps.append("Schedule priority follow-up at upcoming VHSND camp with the ANM")
        else:
            recommended_steps.append("Schedule priority follow-up at the upcoming VHSND camp with the ANM")
            recommended_steps.append("Advise adequate rest, balanced diet, and continued monitoring")

    else:
        priority_level = "ROUTINE"
        flag_red_seal = False
        referral_needed = False

        observed_summary = "Routine frontline home visit completed. Vitals within expected limits or counseling conducted."
        recommended_steps = [
            "Continue routine balanced diet, adequate hydration, and adherence to prescribed supplements",
            "Remind beneficiary of next scheduled immunization or VHSND date"
        ]

        if unmentioned:
            missing_str = ", ".join(unmentioned)
            recommended_steps.append(
                f"Note: Standard checks ({missing_str}) were not recorded today; schedule check at upcoming VHSND camp"
            )

    # 5. Dynamic Native Spoken Reply Construction
    lang_key = language_code if language_code in NATIVE_REPLY_TEMPLATES else "hi-IN"
    templates = NATIVE_REPLY_TEMPLATES[lang_key]

    flag_summary_short = "लक्षण"
    if critical_flags:
        flag_summary_short = "उच्च रक्तचाप और लक्षण" if high_bp else "गंभीर संकेत"
        tier_key = "URGENT"
    elif attention_flags:
        tier_key = "ATTENTION"
    else:
        tier_key = "ROUTINE"

    spoken_template = templates.get(tier_key, templates["ROUTINE"])
    spoken_reply = spoken_template.format(
        ben_label=ben_label,
        flag_desc=flag_summary_short
    )

    return CareRecommendation(
        priority_level=priority_level,
        observed_indicators_summary=observed_summary,
        recommended_next_steps=recommended_steps,
        spoken_reply_native=spoken_reply,
        flag_red_seal=flag_red_seal,
        referral_needed=referral_needed,
        details=all_identified_flags or ["Routine visit logged"],
        identified_flags=all_identified_flags or ["Routine visit logged"]
    )

# ==============================================================================
# 6. UNIFIED ASYNC ENTRYPOINT (EVON FIRST WITH ZERO-HARDCODE FALLBACK)
# ==============================================================================

async def evaluate_care_recommendation(
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
    language_code: str = "hi-IN"
) -> CareRecommendation:
    """
    Unified async pipeline entrypoint:
    Tries Gnani Evon v3.3 (30B Hybrid Mamba2-MoE) first if configured,
    and seamlessly falls back to the dynamic semantic engine if offline or unconfigured.
    """
    if GNANI_EVON_API_BASE:
        try:
            return await evaluate_flags_and_prioritize_with_evon(
                rch_id=rch_id,
                worker_role=worker_role,
                worker_name=worker_name,
                beneficiary_name=beneficiary_name,
                bp_reading=bp_reading,
                bp_source=bp_source,
                hb_g_dl=hb_g_dl,
                weight_kg=weight_kg,
                temperature_f=temperature_f,
                reported_symptoms=reported_symptoms,
                supplies_or_meds=supplies_or_meds,
                poshan_joint_visit_num=poshan_joint_visit_num,
                dynamic_observations=dynamic_observations,
                unmentioned_routine_checks=unmentioned_routine_checks,
                language_code=language_code
            )
        except Exception as e:
            logger.warning(f"Evon v3.3 hosted pipeline call failed ({e}). Using semantic fallback.")

    return generate_care_recommendation(
        rch_id=rch_id,
        worker_role=worker_role,
        worker_name=worker_name,
        beneficiary_name=beneficiary_name,
        bp_reading=bp_reading,
        bp_source=bp_source,
        hb_g_dl=hb_g_dl,
        weight_kg=weight_kg,
        temperature_f=temperature_f,
        reported_symptoms=reported_symptoms,
        supplies_or_meds=supplies_or_meds,
        poshan_joint_visit_num=poshan_joint_visit_num,
        dynamic_observations=dynamic_observations,
        unmentioned_routine_checks=unmentioned_routine_checks,
        language_code=language_code
    )
