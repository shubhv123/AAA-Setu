import os
from typing import Dict, List
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
GNANI_EVON_API_BASE = os.environ.get("GNANI_EVON_API_BASE", "https://api.inya.ai/v1")
GNANI_EVON_MODEL = "gnani/gnani-evon-v3.3-30B-A3B"

# Speech Configs
DEFAULT_SAMPLE_RATE = 16000  # 16 kHz mono PCM
AUDIO_FRAME_SIZE_BYTES = 1024  # 512 samples * 2 bytes
AUDIO_FRAME_DURATION_16KHZ_MS = 32
AUDIO_FRAME_DURATION_8KHZ_MS = 64

# Prisma v3.0 Keyterms for maternal & child health
MATERNAL_KEYTERMS: List[str] = [
    "RCH ID", "ANMOL", "Poshan Tracker", "MCP Card", "VHSND",
    "Hemoglobin", "Blood Pressure", "IFA goli", "TT booster",
    "pedal edema", "sujan", "sar dard", "urine albumin", "Sunita Devi"
]

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
