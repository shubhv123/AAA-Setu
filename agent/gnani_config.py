import os
import json
from typing import Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()

def get_gnani_api_key() -> str:
    key = os.environ.get("GNANI_API_KEY", "").strip()
    if not key:
        raise ValueError("GNANI_API_KEY is not set in environment or .env file.")
    return key

# Speech API Endpoints
GNANI_STT_WS_URL = "wss://api.vachana.ai/stt/v3/stream"
GNANI_STT_REST_URL = "https://api.vachana.ai/stt/v3"
GNANI_TTS_REST_URL = "https://api.vachana.ai/api/v1/tts/inference"

# Platform / Evon API Endpoints
GNANI_PLATFORM_API_BASE = "https://api.inya.ai/platform"
GNANI_EVON_API_BASE = os.environ.get("GNANI_EVON_API_BASE", "").strip()
GNANI_EVON_MODEL = os.environ.get("GNANI_EVON_MODEL", "gnani/gnani-evon-v3.3-30B-A3B")

# Speech Configs
DEFAULT_SAMPLE_RATE = 16000  # 16 kHz mono PCM
AUDIO_FRAME_SIZE_BYTES = 1024  # 512 samples * 2 bytes
AUDIO_FRAME_DURATION_16KHZ_MS = 32
AUDIO_FRAME_DURATION_8KHZ_MS = 64

# ==============================================================================
# UNIVERSAL DOMAIN KEYTERMS FOR GNANI PRISMA v3.0 STT
# ==============================================================================
# In Gnani Prisma v3.0, "keyterms" is an acoustic biasing feature (up to 200 terms)
# that helps the speech recognizer correctly transcribe technical government acronyms,
# clinical terms, and medications that might otherwise be misrecognized.
#
# IMPORTANT:
# 1. Prisma v3.0 is an unconstrained acoustic foundation model:
#    It can transcribe ANY spoken word, sentence, name, or topic, even if NOT in keyterms!
# 2. Keyterms must NEVER contain hardcoded patient names (e.g. no "Sunita Devi").
# 3. Domain vocabulary below covers national MoHFW & MWCD programs across all topics universally.

PORTAL_AND_GOVERNMENT_TERMS: List[str] = [
    "RCH ID", "ANMOL", "Poshan Tracker", "MCP Card", "VHSND",
    "NHM", "MWCD", "ASHA", "ANM", "AWW", "Anganwadi", "Sub-Centre",
    "PHC", "CHC", "JSY", "PMMVY"
]

CLINICAL_VITALS_AND_DIAGNOSTICS: List[str] = [
    "Blood Pressure", "Systolic", "Diastolic", "Hemoglobin", "Urine Albumin",
    "Weight", "Temperature", "Pulse Rate", "Blood Sugar"
]

MEDICATIONS_AND_SUPPLIES: List[str] = [
    "IFA tablets", "Iron Folic Acid", "Calcium", "Albendazole",
    "ORS packet", "Zinc tablets", "Paracetamol", "TT booster", "Td vaccine"
]

NUTRITION_AND_CHILD_CARE: List[str] = [
    "Take-Home Ration", "THR", "Poshahar", "Chana Dal", "Daliya",
    "Malnutrition", "Stunting", "Wasting", "Joint Home Visit", "Diarrhea"
]

IMMUNIZATION_TERMS: List[str] = [
    "Immunization", "Polio drops", "Pentavalent", "Rotavirus", "BCG",
    "Measles-Rubella", "MR vaccine", "Vitamin A dose"
]

# Language-specific technical terms for Indic scripts
REGIONAL_KEYTERMS: Dict[str, List[str]] = {
    "hi-IN": [
        "रक्तचाप", "हीमोग्लोबिन", "वजन", "तापमान", "सूजन", "सर दर्द",
        "उल्टी", "दस्त", "दौरा", "आयरन गोली", "टीका", "पोषाहार", "राशन"
    ],
    "mr-IN": [
        "रक्तदाब", "हिमोग्लोबिन", "वजन", "ताप", "सूज", "डोकेदुखी",
        "उलटी", "जुलाब", "गोळ्या", "लसीकरण", "अंगणवाडी", "दौरा"
    ],
    "or-IN": [
        "ରକ୍ତଚାପ", "ହିମୋଗ୍ଲୋବିନ", "ଓଜନ", "ଜ୍ୱର", "ଫୁଲିବା", "ମୁଣ୍ଡ ବିନ୍ଧା",
        "ଝାଡ଼ା", "ଔଷଧ", "ଟିକାକରଣ", "ଅଙ୍ଗନୱାଡ଼ି"
    ],
    "kn-IN": [
        "ರಕ್ತದೊತ್ತಡ", "ಹಿಮೋಗ್ಲೋಬಿನ್", "ತೂಕ", "ಜ್ವರ", "ಊತ", "ತಲೆನೋವು",
        "ಬೇಧಿ", "ಮಾತ್ರೆ", "ಲಸಿಕೆ", "ಅಂಗನವಾಡಿ"
    ]
}

def get_universal_stt_keyterms(
    language_code: str = "hi-IN",
    custom_terms: Optional[List[str]] = None
) -> List[str]:
    """
    Dynamically generates a universal list of up to 150 domain terms for Prisma v3.0 STT.
    - Zero hardcoded patient names (works for any person or spoken topic).
    - Covers all maternal, newborn, child, nutritional, and administrative vocabulary universally.
    - Seamlessly merges caller-provided custom terms if needed.
    """
    terms_set = set(
        PORTAL_AND_GOVERNMENT_TERMS +
        CLINICAL_VITALS_AND_DIAGNOSTICS +
        MEDICATIONS_AND_SUPPLIES +
        NUTRITION_AND_CHILD_CARE +
        IMMUNIZATION_TERMS +
        REGIONAL_KEYTERMS.get(language_code, [])
    )

    if custom_terms:
        for t in custom_terms:
            clean = t.strip()
            if clean and "<|" not in clean and "|>" not in clean:
                terms_set.add(clean)

    # Return clean list within Gnani's 200 keyterm limit
    return sorted(list(terms_set))[:150]

# Backward-compatibility alias (without hardcoded names)
MATERNAL_KEYTERMS: List[str] = get_universal_stt_keyterms("hi-IN")

# Supported Indian Regional Languages
SUPPORTED_LANGUAGES: Dict[str, str] = {
    "hi-IN": "Hindi (हिंदी)",
    "mr-IN": "Marathi (मराठी)",
    "or-IN": "Odia (ଓଡ଼ିଆ)",
    "kn-IN": "Kannada (ಕನ್ನಡ)",
}

# Timbre v2.5 Voices (Nalini, Pranav, Kaveri)
TIMBRE_VOICES: Dict[str, str] = {
    "hi-IN": "Nalini",
    "mr-IN": "Kaveri",
    "or-IN": "Nalini",
    "kn-IN": "Kaveri",
}

def get_auth_headers() -> Dict[str, str]:
    api_key = get_gnani_api_key()
    return {
        "X-API-Key-ID": api_key,
        "x-api-key": api_key,
        "Authorization": f"Bearer {api_key}",
    }
