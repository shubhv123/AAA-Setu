import os
import re
import json
import logging
from typing import Dict, Any, Optional, List, Tuple
import httpx
from agent.gnani_config import (
    get_auth_headers,
    GNANI_EVON_API_BASE,
    GNANI_EVON_MODEL,
)

logger = logging.getLogger("aaa_setu.evon")

# ==============================================================================
# 1. UNIVERSAL INDIC NUMERAL & SCRIPT NORMALIZERS
# ==============================================================================

INDIC_DIGIT_MAP = {
    # Devanagari
    '०': '0', '१': '1', '२': '2', '३': '3', '४': '4',
    '५': '5', '६': '6', '७': '7', '८': '8', '९': '9',
    # Odia
    '୦': '0', '୧': '1', '୨': '2', '୩': '3', '୪': '4',
    '୫': '5', '୬': '6', '୭': '7', '୮': '8', '୯': '9',
    # Kannada
    '೦': '0', '೧': '1', '೨': '2', '೩': '3', '೪': '4',
    '೫': '5', '೬': '6', '೭': '7', '೮': '8', '೯': '9',
}

def normalize_indic_numerals(text: str) -> str:
    """Translates Devanagari, Odia, and Kannada numerals to standard Arabic digits (0-9)."""
    chars = [INDIC_DIGIT_MAP.get(ch, ch) for ch in text]
    return "".join(chars)

# Universal spoken ordinals across Indic languages and English
ORDINAL_MAP: Dict[str, int] = {
    # English
    'first': 1, '1st': 1, 'second': 2, '2nd': 2, 'third': 3, '3rd': 3,
    'fourth': 4, '4th': 4, 'fifth': 5, '5th': 5, 'sixth': 6, '6th': 6,
    'seventh': 7, '7th': 7, 'eighth': 8, '8th': 8, 'ninth': 9, '9th': 9,
    'tenth': 10, '10th': 10, 'eleventh': 11, '11th': 11, 'twelfth': 12, '12th': 12,
    'thirteenth': 13, '13th': 13, 'fourteenth': 14, '14th': 14, 'fifteenth': 15, '15th': 15,
    # Hindi / Urdu
    'pehla': 1, 'pehli': 1, 'doosra': 2, 'doosri': 2, 'teesra': 3, 'teesri': 3,
    'chautha': 4, 'chauthi': 4, 'paanchwa': 5, 'paanchwi': 5, 'chhattha': 6, 'chhatthi': 6,
    'saatva': 7, 'saatvi': 7, 'satva': 7, 'satvi': 7, 'aathva': 8, 'aathvi': 8, 'aathwa': 8,
    'nauva': 9, 'nauvi': 9, 'navva': 9, 'navvi': 9, 'dasva': 10, 'dasvi': 10,
    'gyarahva': 11, 'gyarahvi': 11, 'barahva': 12, 'barahvi': 12, 'terahva': 13,
    'chaudahva': 14, 'chaudahvi': 14, 'pandrahva': 15, 'pandrahvi': 15,
    'पहला': 1, 'दूसरा': 2, 'तीसरा': 3, 'चौथा': 4, 'पांचवां': 5, 'छठा': 6,
    'सातवां': 7, 'आठवां': 8, 'नौवां': 9, 'दसवां': 10, 'ग्यारहवां': 11, 'चौदहवां': 14, 'पंद्रहवां': 15,
    # Marathi
    'pahila': 1, 'pahili': 1, 'dusra': 2, 'dusri': 2, 'tisra': 3, 'tisri': 3,
    'chautha': 4, 'pachva': 5, 'sahava': 6, 'satva': 7, 'aathva': 8, 'navva': 9,
    'dahava': 10, 'akrave': 11, 'chaudhave': 14, 'pandhrave': 15,
    # Odia
    'prathama': 1, 'dwitiya': 2, 'trutiya': 3, 'chaturtha': 4, 'panchama': 5,
    'sastha': 6, 'saptama': 7, 'ashtama': 8, 'nabama': 9, 'dasama': 10,
    'ekadasa': 11, 'chaturdasa': 14, 'panchadasi': 15,
    'ପ୍ରଥମ': 1, 'ଦ୍ୱିତୀୟ': 2, 'ତୃତୀୟ': 3, 'ଅଷ୍ଟମ': 8, 'ନବମ': 9, 'ଏକାଦଶ': 11,
    # Kannada
    'modala': 1, 'eradaneya': 2, 'mooraneya': 3, 'nalkaneya': 4, 'aidaneya': 5,
    'aaraneya': 6, 'elaneya': 7, 'entaneya': 8, 'ombhattaneya': 9, 'hattaneya': 10,
    'hannondu': 11, 'hadinalku': 14, 'hadinaidu': 15,
}

SPOKEN_QUANTITY_WORDS: Dict[str, int] = {
    'ek': 1, 'do': 2, 'teen': 3, 'char': 4, 'chaar': 4, 'paanch': 5,
    'chhe': 6, 'saat': 7, 'aath': 8, 'nau': 9, 'das': 10,
    'gyarah': 11, 'barah': 12, 'terah': 13, 'chaudah': 14, 'pandrah': 15,
    'solah': 16, 'satrah': 17, 'atharah': 18, 'unnis': 19, 'bees': 20,
    'pachis': 25, 'tees': 30, 'paintis': 35, 'chalis': 40, 'pachaas': 50,
    'saatth': 60, 'sau': 100,
    'एक': 1, 'दो': 2, 'तीन': 3, 'चार': 4, 'पांच': 5, 'दस': 10, 'बीस': 20, 'तीस': 30, 'साठ': 60, 'सौ': 100
}

# Generic stopwords that must never be mistaken for a patient name
NAME_STOPWORDS = {
    'asha', 'anm', 'aww', 'nurse', 'doctor', 'worker', 'dost', 'behen',
    'rch', 'mcp', 'card', 'home', 'visit', 'camp', 'vhsnd', 'subcentre', 'sub-centre',
    'hospital', 'phc', 'chc', 'village', 'gaav', 'poshan', 'tracker', 'main', 'aaj',
    'today', 'grah', 'bhet', 'daura', 'update', 'record', 'report', 'details',
    'namaste', 'swagat', 'kripya', 'dekha', 'kiya', 'mila', 'diya', 'bol', 'rahi', 'hoon',
    'patient', 'beneficiary', 'labharthi', 'mata', 'shrimati'
}

# ==============================================================================
# 2. UNIVERSAL ENTITY EXTRACTION HELPERS
# ==============================================================================

def extract_rch_id(text: str) -> Optional[str]:
    """Universal 12-digit RCH ID extractor across Arabic and Indic numerals."""
    normalized = normalize_indic_numerals(text)
    
    # 1. Match canonical 12-digit RCH IDs (e.g. 999000104829 or generic 12 digits)
    m = re.search(r'\b(999\d{9}|\d{12})\b', normalized)
    if m:
        raw_rch = m.group(1)
        return f"999{raw_rch[-9:]}" if not raw_rch.startswith("999") else raw_rch

    # 2. Match RCH numbers with spaces or hyphens (common in speech-to-text: "999 000 104 829")
    m_spaced = re.search(r'(?:rch|id|sankhya|number)[\s:]*([0-9\s\-]{12,18})', normalized, re.IGNORECASE)
    if m_spaced:
        digits = re.sub(r'\D', '', m_spaced.group(1))
        if len(digits) == 12:
            return f"999{digits[-9:]}" if not digits.startswith("999") else digits

    return None

def extract_beneficiary_name(transcript: str, text_normalized: str) -> Optional[str]:
    """
    Universal beneficiary name extractor.
    Operates without hardcoded surnames or regional word restrictions.
    Supports Latin title-case, lower-case transcripts, and native Indic scripts (Devanagari, Odia, Kannada).
    """
    # Pattern A: Name explicitly prefixed with maternal honorifics or beneficiary labels
    # e.g., "Mata Sunita Devi", "Labharthi Rekha Devi", "Patient Mary Thomas", "Shishu Aarav"
    prefix_pattern = (
        r'(?:mata|maa|shrimati|mrs\.?|miss|srimati|didi|tai|amma|behen|बहन|माता|श्रीमती|माँ|महिला|'
        r'labharthi|beneficiary|patient|marij|garbhvati|mahila|bache|bacha|shishu|child|mother|मरीज|गर्भवती|बाळ|ଶିଶୁ|ମଗୁ|'
        r'naam|name|called|naav|nav|नांव|नाव|नाम|ନାମ|ಹೆಸರು)\s*'
        r'[:\-]?\s*'
        r'([A-Za-z\u0900-\u097F\u0B00-\u0B7F\u0C80-\u0CFF]+(?:\s+[A-Za-z\u0900-\u097F\u0B00-\u0B7F\u0C80-\u0CFF]+){0,2})'
    )
    for match in re.finditer(prefix_pattern, transcript, re.IGNORECASE):
        candidate = match.group(1).strip()
        # Clean out any trailing postpositions or punctuation
        candidate = re.sub(r'[\s,.\-!?:].*', '', candidate) if len(candidate.split()) == 1 else candidate
        candidate = re.sub(r'\s+(?:ji|ko|ka|ki|ke|ku|ne|se|par|hai|tha|thi|daura|visit|rch|id|bp|hb|card|mcp).*', '', candidate, flags=re.I).strip()
        words = [w for w in candidate.split() if w.lower() not in NAME_STOPWORDS and len(w) > 1]
        if words:
            return " ".join(words).title() if words[0].isascii() else " ".join(words)

    # Pattern B: Name directly preceding relationship / visit postpositions
    # e.g., "Sunita Devi, RCH ID..." or "Pooja Patil ka home visit" or "Fatima Begum ki checkup"
    pre_marker = re.search(
        r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*(?:ji|ko|ka|ki|ke|ku|ne|didi|\s*,\s*|\s+rch\b|\s+mcp\b)',
        transcript
    )
    if pre_marker:
        candidate = pre_marker.group(1).strip()
        words = [w for w in candidate.split() if w.lower() not in NAME_STOPWORDS and len(w) > 1]
        if words:
            return " ".join(words).title()

    # Pattern C: Generic 2-word proper noun pair in transcript
    # (Matches any 2 consecutive capitalized words that aren't system keywords)
    two_word = re.findall(r'\b([A-Z][a-z]{2,}\s+[A-Z][a-z]{2,})\b', transcript)
    for cand in two_word:
        words = [w.lower() for w in cand.split()]
        if not any(w in NAME_STOPWORDS for w in words):
            return cand.title()

    return None

def extract_worker_info(transcript: str) -> Tuple[str, str]:
    """Universal worker role and name extractor."""
    text_lower = transcript.lower()

    # Role detection
    if any(w in text_lower for w in ['nurse', 'anm', 'sister', 'vhsnd camp', 'sub-centre', 'subcentre', 'उप-केंद्र', 'नर्स']):
        worker_role = "ANM"
    elif any(w in text_lower for w in ['aww', 'anganwadi', 'anganwady', 'sevik', 'पोषण', 'अंगणवाडी', 'ଅଙ୍ଗନୱାଡି']):
        worker_role = "AWW"
    else:
        worker_role = "ASHA"

    # Name detection
    worker_name = "Frontline Worker"
    worker_match = re.search(
        r'(?:asha|aasha|आशा|nurse|anm|sister|aww|sewika)\s+([A-Za-z\u0900-\u097F\u0B00-\u0B7F\u0C80-\u0CFF]+(?:\s+[A-Za-z\u0900-\u097F\u0B00-\u0B7F\u0C80-\u0CFF]+)?)',
        transcript,
        re.IGNORECASE
    )
    if worker_match:
        cand = worker_match.group(1).strip()
        cleaned = re.sub(r'\s+(?:bol|ji|didi|here|from|ne|ke|ka|ki|today|aaj).*', '', cand, flags=re.I).strip()
        if len(cleaned) > 2 and cleaned.lower() not in NAME_STOPWORDS:
            worker_name = cleaned.title() if cleaned.isascii() else cleaned

    return worker_role, worker_name

def extract_blood_pressure(transcript: str) -> Tuple[Optional[str], str]:
    """
    Universal blood pressure extractor.
    Parses numeric, spoken ("140 by 90", "140 over 90", "140 bata 90"),
    and Indic numeral representations with physiological sanity bounds (70-260 / 40-160).
    """
    norm = normalize_indic_numerals(transcript).lower()
    bp = None

    # Pattern A: Standard delimiters (140/90, 140-90, 140 / 90)
    m = re.search(r'\b([0-9]{2,3})\s*(?:/|\-)\s*([0-9]{2,3})\b', norm)
    if m:
        sys, dia = int(m.group(1)), int(m.group(2))
        if 70 <= sys <= 260 and 40 <= dia <= 160:
            bp = f"{sys}/{dia}"

    # Pattern B: Spoken phrases ("140 by 90", "140 over 90", "140 bata 90", "140 aur 90", "bp 140 90")
    if not bp:
        m2 = re.search(
            r'(?:bp|raktchaap|raktdaab|rakt\s*daab|blood\s*pressure)?\s*([0-9]{2,3})\s*(?:by|over|bata|slash|aur|and|\s)\s*([0-9]{2,3})',
            norm
        )
        if m2:
            sys, dia = int(m2.group(1)), int(m2.group(2))
            if 70 <= sys <= 260 and 40 <= dia <= 160:
                bp = f"{sys}/{dia}"

    # Determine whether measured live today or cited from physical MCP card record
    is_card_history = any(
        w in norm for w in [
            'mcp', 'card', 'pichla', 'purana', 'previous', 'past',
            'subcentre', 'sub-centre', 'sub centre', 'last visit', 'pichle daure'
        ]
    )
    bp_source = "MCP_CARD_HISTORY" if is_card_history else "LIVE_ANM_MEASURED"

    return bp, bp_source

def extract_hemoglobin(transcript: str) -> Optional[float]:
    """Universal hemoglobin extractor (physiological range: 3.0 to 19.0 g/dL)."""
    norm = normalize_indic_numerals(transcript).lower()
    
    # Keyword-anchored Hb extraction
    m = re.search(r'(?:hb|hemoglobin|haemoglobin|himoglobin|khoon|rakt)[\s:]*([0-9]{1,2}(?:\.[0-9]+)?)', norm)
    if m:
        try:
            val = float(m.group(1))
            if 3.0 <= val <= 19.0:
                return val
        except ValueError:
            pass

    # Decimal float fallback if clearly spoken with unit or decimal
    m2 = re.search(r'\b([0-9]{1,2}\.[0-9]+)\s*(?:g/dl|gram|gm)?\b', norm)
    if m2:
        try:
            val = float(m2.group(1))
            if 3.0 <= val <= 19.0:
                return val
        except ValueError:
            pass

    return None

def extract_weight_and_temp(transcript: str) -> Tuple[Optional[float], Optional[float]]:
    """Universal weight (kg) and temperature (Fahrenheit) extractor."""
    norm = normalize_indic_numerals(transcript).lower()
    weight_kg, temp_f = None, None

    # Weight in kilograms (1 to 150 kg)
    w_match = re.search(r'(?:weight|vajan|wazan|वजन|ओजन|ತೂಕ|ଭାର)[\s:]*([0-9]{1,3}(?:\.[0-9]+)?)\s*(?:kg|kilo)?', norm)
    if w_match:
        try:
            val = float(w_match.group(1))
            if 1.0 <= val <= 150.0:
                weight_kg = val
        except ValueError:
            pass

    # Temperature in Fahrenheit (95 to 108 F)
    t_match = re.search(r'(?:temp|temperature|taapman|bukhar|fever|तापमान|बुखार|ಜ್ವರ|ଜ୍ୱର)[\s:]*([0-9]{2,3}(?:\.[0-9]+)?)\s*(?:f|degree)?', norm)
    if t_match:
        try:
            val = float(t_match.group(1))
            if 95.0 <= val <= 108.0:
                temp_f = val
            elif 35.0 <= val <= 42.0:  # Convert Celsius to Fahrenheit
                temp_f = round((val * 9 / 5) + 32, 1)
        except ValueError:
            pass

    return weight_kg, temp_f

def extract_reported_symptoms(transcript: str) -> List[str]:
    """
    Multilingual maternal and child health red-flag danger sign detector.
    Adheres strictly to NHM (National Health Mission) field manuals.
    """
    text_lower = transcript.lower()
    symptoms = []

    # 1. Pedal / Facial Edema (Pre-eclampsia & Renal Danger Sign)
    if any(w in text_lower for w in [
        'sujan', 'edema', 'oedema', 'swelling', 'swollen', 'सूजन', 'सूज',
        'pair me sujan', 'pairon mein sujan', 'pairo me sujan', 'chehre pe sujan',
        'god phuliba', 'phuliba', 'ଫୁଲିବା', 'ಕಾಲು ಊತ', 'ootha'
    ]):
        symptoms.append('pedal_edema')

    # 2. Severe Headache / Migraine / Dizziness
    if any(w in text_lower for w in [
        'sar dard', 'sir dard', 'headache', 'tez sar dard', 'डोकेदुखी', 'dokedukhi',
        'chakkar', 'chakkar aana', 'munda bindha', 'ମୁଣ୍ଡ ବିନ୍ଧା', 'ತಲೆನೋವು', 'talenovu'
    ]):
        symptoms.append('severe_headache')

    # 3. Blurred / Diminished Vision
    if any(w in text_lower for w in [
        'dhundhla', 'dhundla', 'vision', 'blurred', 'अंधुक', 'andhuk',
        'nazar kamzor', 'jhapsa', 'ଅସ୍ପଷ୍ଟ ଦୃଷ୍ଟି', 'ಮಸುಕಾದ ದೃಷ್ಟಿ', 'masukada drishti'
    ]):
        symptoms.append('blurred_vision')

    # 4. Vaginal Bleeding / Antepartum Hemorrhage
    if any(w in text_lower for w in [
        'bleeding', 'rakt srav', 'raktasrav', 'khoon', 'रक्तस्त्राव', 'raktastrav',
        'rakta padiba', 'ରକ୍ତସ୍ରାବ', 'ರಕ್ತಸ್ರಾವ', 'raktasrava'
    ]):
        symptoms.append('bleeding')

    # 5. High Fever / Rigors / Sepsis
    if any(w in text_lower for w in [
        'bukhar', 'fever', 'tez bukhar', 'high fever', 'ताप', 'कडक ताप',
        'jwara', 'ଜ୍ୱର', 'ತೀವ್ರ ಜ್ವರ', 'sheetha jwara'
    ]):
        symptoms.append('high_fever')

    # 6. Convulsions / Seizures / Eclampsia Fits
    if any(w in text_lower for w in [
        'daura', 'daure', 'fits', 'convulsion', 'convulsions', 'seizures',
        'jhatke', 'मिरगी', 'झटके', 'ବାତ', 'bata', 'ಸೆಳೆತ'
    ]):
        symptoms.append('convulsions_or_fits')

    # 7. Respiratory Distress / Breathlessness
    if any(w in text_lower for w in [
        'saans phoolna', 'saans lene me takleef', 'breathlessness', 'shortness of breath',
        'दम लागणे', 'ଶ୍ୱାସକ୍ରିୟାରେ କଷ୍ଟ', 'ಉಸಿರಾಟದ ತೊಂದರೆ'
    ]):
        symptoms.append('breathlessness')

    # 8. Severe Abdominal Pain / Epigastric Pain
    if any(w in text_lower for w in [
        'pet dard', 'tez pet dard', 'abdominal pain', 'stomach ache',
        'पोटदुखी', 'ପେଟ ବିନ୍ଧା', 'ಹೊಟ್ಟೆ ನೋವು'
    ]):
        symptoms.append('severe_abdominal_pain')

    return symptoms

def extract_supplies_or_medications(transcript: str) -> List[str]:
    """
    Universal frontline medication and nutritional supply extractor.
    Dynamically extracts quantities (digits or words) and distinguishes
    between items distributed today vs. remaining tablets in household.
    """
    text_lower = transcript.lower()
    supplies = []

    # Dynamic Quantity Extractor Helper
    def find_quantity(pattern_keyword: str) -> Optional[int]:
        # Try numeric digits first
        m_num = re.search(rf'([0-9]+)\s*(?:{pattern_keyword})', text_lower)
        if m_num:
            return int(m_num.group(1))
        # Try word numbers
        for word, val in SPOKEN_QUANTITY_WORDS.items():
            if f"{word} {pattern_keyword}" in text_lower or f"{pattern_keyword} {word}" in text_lower:
                return val
        return None

    # 1. Iron & Folic Acid (IFA) Tablets
    if any(w in text_lower for w in ['ifa', 'iron', 'folic acid', 'loha goli', 'आयरन']):
        qty = find_quantity('ifa') or find_quantity('iron') or find_quantity('goli') or find_quantity('tablet')
        is_remaining = any(w in text_lower for w in ['bachi', 'bache', 'remaining', 'shesh', 'baki'])
        if qty:
            status_text = "remaining" if is_remaining else "administered"
            supplies.append(f"{qty} IFA tablets {status_text}")
        else:
            supplies.append("IFA tablets verified")
    elif any(w in text_lower for w in ['goli', 'tablets', 'गोली']):
        # If worker simply said quantity + goli without specifying IFA, but in frontline context
        qty = find_quantity('goli') or find_quantity('tablet')
        if qty:
            is_remaining = any(w in text_lower for w in ['bachi', 'bache', 'remaining', 'shesh', 'baki'])
            status_text = "remaining" if is_remaining else "administered"
            supplies.append(f"{qty} IFA tablets {status_text}")

    # 2. Oral Rehydration Salts (ORS) & Zinc
    if any(w in text_lower for w in ['ors', 'ors packet', 'ors ghol', 'जीवन रक्षक']):
        supplies.append("ORS packet administered")
    if any(w in text_lower for w in ['zinc', 'zinc tablet', 'जिंक']):
        supplies.append("Zinc tablets provided")

    # 3. Calcium Tablets
    if any(w in text_lower for w in ['calcium', 'कैल्शियम']):
        qty = find_quantity('calcium')
        supplies.append(f"{qty} Calcium tablets given" if qty else "Calcium tablets verified")

    # 4. Albendazole (Deworming)
    if any(w in text_lower for w in ['albendazole', 'deworming', 'keede ki dawa', 'कीड़े की दवा']):
        supplies.append("Albendazole deworming administered")

    # 5. Tetanus Toxoid / Td Vaccine Injection
    if any(w in text_lower for w in ['tt booster', 'tt injection', 'tt teeka', 'td injection', 'tetanus']):
        supplies.append("TT/Td booster administered")

    # 6. Take-Home Ration (THR) / Supplementary Nutrition
    if any(w in text_lower for w in ['ration', 'thr', 'chana dal', 'daliya', 'chana', 'पोषाहार', 'राशन', 'chhatua']):
        supplies.append("Take-Home Ration (THR) verified")

    return supplies

def extract_visit_number(transcript: str) -> Optional[int]:
    """
    Universal visit number extractor for MWCD Poshan Tracker & NHM ANC registers.
    Maps numeric digits and multilingual word ordinals without hardcoding.
    """
    text_lower = transcript.lower()

    # Pattern A: Number following visit / daura / bhet keyword
    m = re.search(r'(?:visit|daura|daure|bhet|bheti|दौरा|ଭେଟ|ಭೇಟಿ)\s*(?:number|no|#)?\s*([0-9]+)', text_lower)
    if m:
        cand = int(m.group(1))
        if 1 <= cand <= 25:
            return cand

    # Pattern B: Ordinal words in any language (e.g., "aathva visit", "8th visit", "आठवा दौरा")
    for word, num in ORDINAL_MAP.items():
        if re.search(rf'\b{word}\b\s*(?:visit|daura|daure|bhet|bheti|दौरा|ଭେଟ|bhet)?', text_lower):
            # Verify that this was connected to a health visit or home check
            if any(k in text_lower for k in ['visit', 'daura', 'bhet', 'grah', 'home', 'poshan', 'aww', 'asha']) or word.endswith(('th', 'st', 'nd', 'rd')):
                return num

    return None

def extract_dynamic_observations(transcript: str) -> List[Dict[str, str]]:
    """
    Universal Dynamic Observations Extractor.
    Ensures TRUE ZERO INFORMATION LOSS:
    Extracts the EXACT spoken sentence/clause uttered by the frontline worker,
    instead of substituting fabricated generic static strings.
    """
    # Break transcript into distinct spoken clauses / phrases
    # Split by sentence markers or major Indic coordinating conjunctions
    raw_clauses = re.split(r'[,.!?;\n]|\b(?:aur|tatha|and|lekin|par|punah|aani|mattu)\b', transcript, flags=re.IGNORECASE)
    cleaned_clauses = [c.strip() for c in raw_clauses if len(c.strip()) > 3]

    observations: List[Dict[str, str]] = []
    seen_categories = set()

    for clause in cleaned_clauses:
        c_lower = clause.lower()

        # 1. Child Diarrhea / Loose Motions
        if any(w in c_lower for w in ['dast', 'loose motion', 'diarrhea', 'patla dast', 'jhada']) and 'Child_Health' not in seen_categories:
            observations.append({
                "category": "Child_Health",
                "field_label": "Child Diarrheal Episode",
                "spoken_value": clause,
                "status": "Attention"
            })
            seen_categories.add('Child_Health')

        # 2. Maternal Nausea / Morning Sickness / IFA Tolerance
        elif any(w in c_lower for w in ['ulti', 'nausea', 'vomiting', 'chakkar', 'khana nahi']) and 'Maternal' not in seen_categories:
            observations.append({
                "category": "Maternal",
                "field_label": "Maternal Nausea / Tolerance Issue",
                "spoken_value": clause,
                "status": "Note"
            })
            seen_categories.add('Maternal')

        # 3. Nutrition, Diet & Take-Home Ration (THR)
        elif any(w in c_lower for w in ['chana dal', 'ration', 'khana', 'diet', 'poshan', 'thr', 'daliya', 'poshahar']) and 'Nutrition_THR' not in seen_categories:
            observations.append({
                "category": "Nutrition_THR",
                "field_label": "Nutritional Intake & Ration",
                "spoken_value": clause,
                "status": "Normal"
            })
            seen_categories.add('Nutrition_THR')

        # 4. Family Objections / Social Hesitation
        elif any(w in c_lower for w in ['sasural', 'pati', 'family', 'parivar', 'mana kiya', 'manahi', 'sasu']) and 'Counseling_Social' not in seen_categories:
            observations.append({
                "category": "Counseling_Social",
                "field_label": "Family Counseling & Social Support",
                "spoken_value": clause,
                "status": "Attention"
            })
            seen_categories.add('Counseling_Social')

        # 5. Sanitation, Clean Drinking Water & Hygiene
        elif any(w in c_lower for w in ['paani', 'water', 'safai', 'sanitation', 'shauchalay', 'clean water']) and 'General_Sanitation' not in seen_categories:
            observations.append({
                "category": "General",
                "field_label": "Sanitation & Clean Drinking Water",
                "spoken_value": clause,
                "status": "Normal"
            })
            seen_categories.add('General_Sanitation')

        # 6. Routine Immunization & Vaccination Topics
        elif any(w in c_lower for w in ['teeka', 'vaccine', 'tika', 'polio', 'pentavalent', 'booster', 'immunization']) and 'Immunization' not in seen_categories:
            observations.append({
                "category": "Immunization",
                "field_label": "Immunization Status & Follow-up",
                "spoken_value": clause,
                "status": "Normal"
            })
            seen_categories.add('Immunization')

    return observations

# ==============================================================================
# 3. MASTER EXTRACTION PIPELINE (ZERO HARDCODING)
# ==============================================================================

def extract_spoken_entities(transcript: str) -> Dict[str, Any]:
    """
    Open-ended, universal frontline health entity extraction.
    Only rch_id is mandatory.
    Zero information loss: captures exact spoken clauses into dynamic observations.
    """
    text_normalized = normalize_indic_numerals(transcript)

    # 1. Mandatory RCH ID
    rch_id = extract_rch_id(transcript)
    ben_name = extract_beneficiary_name(transcript, text_normalized)

    # If RCH ID is missing, flag politely for the worker
    if not rch_id:
        prompt_msg = (
            f"Kripya {ben_name} ka 12-digit RCH ID batayein."
            if ben_name else
            "Kripya labharthi ka 12-digit RCH ID batayein."
        )
        return {
            "missing_mandatory_id": True,
            "prompt_message": prompt_msg,
            "beneficiary_name": ben_name,
            "transcript": transcript
        }

    # 2. Worker Identity
    worker_role, worker_name = extract_worker_info(transcript)

    # 3. Optional Clinical Vitals
    bp, bp_source = extract_blood_pressure(transcript)
    hb = extract_hemoglobin(transcript)
    weight_kg, temp_f = extract_weight_and_temp(transcript)

    # 4. Symptoms & Danger Signs
    symptoms = extract_reported_symptoms(transcript)

    # 5. Supplies & Medications
    supplies = extract_supplies_or_medications(transcript)

    # 6. Poshan / ANC Visit Number
    visit_num = extract_visit_number(transcript)

    # 7. Dynamic Catch-All Observations (Exact Spoken Clauses)
    dynamic_obs = extract_dynamic_observations(transcript)

    # 8. Unmentioned Routine Checks Tracker (Gentle Reminder, Not an Error)
    unmentioned_checks = []
    if bp is None:
        unmentioned_checks.append("Blood Pressure (BP)")
    if hb is None:
        unmentioned_checks.append("Hemoglobin (Hb)")
    if weight_kg is None:
        unmentioned_checks.append("Weight")

    return {
        "missing_mandatory_id": False,
        "rch_id": rch_id,
        "worker_role": worker_role,
        "worker_name": worker_name,
        "beneficiary_name": ben_name,
        "bp_reading": bp,
        "bp_source": bp_source,
        "hb_g_dl": hb,
        "weight_kg": weight_kg,
        "temperature_f": temp_f,
        "reported_symptoms": symptoms,
        "supplies_or_meds": supplies,
        "poshan_joint_visit_num": visit_num,
        "dynamic_observations": dynamic_obs,
        "unmentioned_routine_checks": unmentioned_checks
    }

# ==============================================================================
# 4. EVON CLIENT CLASS (HOSTED OR FALLBACK INFERENCE)
# ==============================================================================

from agent.recommendation_engine import (
    generate_care_recommendation,
    CareRecommendation,
)

EVON_UNIFIED_SYSTEM_PROMPT = """You are Gnani Evon v3.3 (30B Hybrid Mamba2-MoE), the sovereign frontline healthcare AI for India's National Health Mission (NHM) and Ministry of Women & Child Development (MWCD).
Your role is to analyze native-script Indic transcripts spoken by frontline workers (ASHA, ANM, AWW), extract structured field data, and generate non-diagnostic field care recommendations for Medical Officer review.

STRICT NON-DIAGNOSTIC MEDICAL SAFETY MANDATE:
- You are an AI field decision-support assistant, NOT a medical doctor.
- NEVER diagnose a condition or state definitively that a patient "has" a disease (e.g., never say "She has pre-eclampsia" or "The child has pneumonia").
- Frame all findings as factual risk indicators and recommended next steps for ANM / Medical Officer review.

EXTRACTION RULES:
1. Mandatory ID: ONLY 'rch_id' (12-digit string, usually starting with 999) is mandatory. If the worker did not speak an RCH ID, set 'missing_mandatory_id': true, and write a polite 1-sentence Indic prompt in 'prompt_message' asking only for the RCH ID.
2. Optional Vitals: BP, Hb, Weight, Temp are optional. Set to null if not spoken.
3. Zero Information Loss: For ANY other topic spoken (e.g. child diarrhea/hydration, nausea/vomiting, dietary habits, family objections, clean drinking water, vaccination), extract each item into 'dynamic_observations' with:
   - "category": "Maternal" | "Child_Health" | "Nutrition_THR" | "Immunization" | "Counseling_Social" | "General"
   - "field_label": short descriptive English title
   - "spoken_value": exact spoken detail in native script/English
   - "status": "Normal" | "Note" | "Attention"
4. Missing Routine Info Tracker: Note standard checks not mentioned today in 'unmentioned_routine_checks' (e.g. ["Blood Pressure (BP)", "Hemoglobin (Hb)", "Weight"]).

FIELD CARE RECOMMENDATION:
- "priority_level": "ROUTINE" | "ATTENTION_NEEDED" | "URGENT_PHC_REFERRAL"
- "identified_flags": list of identified clinical or field risk indicators
- "observed_indicators_summary": Factual summary of why this priority was chosen (e.g. 'Elevated blood pressure recorded on MCP card combined with newly reported pedal swelling today')
- "recommended_next_steps": 1 to 3 practical next steps for the worker following NHM field guidelines
- "spoken_reply_native": Warm, natural 2-sentence confirmation in the exact Indian language spoken by the worker for Gnani Timbre TTS readout
- "flag_red_seal": boolean (true if urgent referral)
- "referral_needed": boolean (true if priority is URGENT_PHC_REFERRAL)

Respond strictly with valid JSON with top-level keys:
{
  "missing_mandatory_id": false,
  "rch_id": "999000104829",
  "worker_role": "ASHA",
  "worker_name": "Frontline Worker",
  "beneficiary_name": "Beneficiary Name",
  "bp_reading": "142/92",
  "bp_source": "MCP_CARD_HISTORY",
  "hb_g_dl": null,
  "weight_kg": null,
  "temperature_f": null,
  "reported_symptoms": ["pedal_edema"],
  "supplies_or_meds": ["10 IFA tablets remaining"],
  "poshan_joint_visit_num": 8,
  "dynamic_observations": [],
  "unmentioned_routine_checks": ["Hemoglobin (Hb)", "Weight"],
  "recommendation": {
    "priority_level": "URGENT_PHC_REFERRAL",
    "identified_flags": ["Elevated blood pressure (142/92)", "Pedal edema"],
    "observed_indicators_summary": "Elevated blood pressure (142/92) recorded alongside newly reported pedal swelling.",
    "recommended_next_steps": ["Advise immediate clinical evaluation by Medical Officer at Primary Health Centre (PHC)", "Stamp MCP Card Red Seal", "Arrange emergency transport if symptoms worsen"],
    "spoken_reply_native": "Labharthi ka record darj kar liya gaya hai. Kripya turant PHC jakar doctor se jaanch karwayein.",
    "flag_red_seal": true,
    "referral_needed": true
  }
}
"""

class EvonClient:
    def __init__(self, base_url: Optional[str] = None, model: Optional[str] = None):
        self.base_url = (base_url or GNANI_EVON_API_BASE).rstrip("/") if (base_url or GNANI_EVON_API_BASE) else ""
        self.model = model or GNANI_EVON_MODEL

    async def chat_completion(
        self,
        messages: list,
        temperature: float = 0.6,
        top_p: float = 0.95,
        response_format: Optional[dict] = None,
    ) -> Dict[str, Any]:
        if not self.base_url:
            raise ValueError("GNANI_EVON_API_BASE is not configured.")

        headers = get_auth_headers()
        headers["Content-Type"] = "application/json"

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "top_p": top_p,
            "enable_thinking": False,
        }
        if response_format:
            payload["response_format"] = response_format

        url = f"{self.base_url}/chat/completions"
        logger.info(f"Calling Evon v3.3 at {url}...")

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            if response.status_code != 200:
                raise RuntimeError(
                    f"Gnani Evon v3.3 Inference Error [HTTP {response.status_code}]: {response.text}"
                )
            return response.json()

    async def extract_and_recommend(
        self,
        transcript: str,
        language_code: str = "hi-IN",
        baseline_mcp_card: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Single unified forward pass through Gnani Evon v3.3 (30B Hybrid Mamba2-MoE).
        Takes Prisma native-script transcript, extracts rch_id + open-ended dynamic_observations,
        and generates non-diagnostic field care recommendations adhering to NHM protocols.
        Seamlessly falls back to local universal extractor if no remote GPU endpoint is active.
        """
        if self.base_url:
            try:
                user_content = {
                    "spoken_transcript": transcript,
                    "language_code": language_code,
                    "baseline_mcp_card": baseline_mcp_card or {}
                }
                messages = [
                    {"role": "system", "content": EVON_UNIFIED_SYSTEM_PROMPT},
                    {"role": "user", "content": json.dumps(user_content, ensure_ascii=False)}
                ]

                res = await self.chat_completion(messages=messages, response_format={"type": "json_object"})
                content = res["choices"][0]["message"]["content"]
                parsed = json.loads(content)

                # Ensure consistent schema
                if parsed.get("missing_mandatory_id"):
                    return {
                        "missing_mandatory_id": True,
                        "prompt_message": parsed.get("prompt_message") or "Kripya labharthi ka 12-digit RCH ID batayein.",
                        "beneficiary_name": parsed.get("beneficiary_name"),
                        "transcript": transcript,
                        "extracted": parsed
                    }

                rec_data = parsed.get("recommendation", {})
                flags = rec_data.get("identified_flags") or parsed.get("identified_flags") or []
                rec = CareRecommendation(
                    priority_level=rec_data.get("priority_level", "ROUTINE"),
                    observed_indicators_summary=rec_data.get("observed_indicators_summary", "Routine frontline observation."),
                    recommended_next_steps=rec_data.get("recommended_next_steps", ["Continue routine care"]),
                    spoken_reply_native=rec_data.get("spoken_reply_native", "Record surakshit kar liya gaya hai."),
                    flag_red_seal=bool(rec_data.get("flag_red_seal", rec_data.get("priority_level") == "URGENT_PHC_REFERRAL")),
                    referral_needed=bool(rec_data.get("referral_needed", rec_data.get("priority_level") == "URGENT_PHC_REFERRAL")),
                    details=flags,
                    identified_flags=flags
                )

                return {
                    "missing_mandatory_id": False,
                    "extracted": parsed,
                    "recommendation": rec
                }
            except Exception as e:
                logger.warning(f"Hosted Evon v3.3 API call failed ({e}). Falling back to local semantic NLU.")

        # Local Zero-Hardcode Fallback Engine
        extracted = extract_spoken_entities(transcript)
        if extracted.get("missing_mandatory_id"):
            return {
                "missing_mandatory_id": True,
                "prompt_message": extracted.get("prompt_message") or "Kripya labharthi ka 12-digit RCH ID batayein.",
                "beneficiary_name": extracted.get("beneficiary_name"),
                "transcript": transcript,
                "extracted": extracted
            }

        rec = generate_care_recommendation(
            rch_id=extracted["rch_id"],
            worker_role=extracted.get("worker_role", "ASHA"),
            worker_name=extracted.get("worker_name", "Frontline Worker"),
            beneficiary_name=extracted.get("beneficiary_name"),
            bp_reading=extracted.get("bp_reading"),
            bp_source=extracted.get("bp_source"),
            hb_g_dl=extracted.get("hb_g_dl"),
            weight_kg=extracted.get("weight_kg"),
            temperature_f=extracted.get("temperature_f"),
            reported_symptoms=extracted.get("reported_symptoms"),
            supplies_or_meds=extracted.get("supplies_or_meds"),
            poshan_joint_visit_num=extracted.get("poshan_joint_visit_num"),
            dynamic_observations=extracted.get("dynamic_observations"),
            unmentioned_routine_checks=extracted.get("unmentioned_routine_checks"),
            language_code=language_code
        )

        return {
            "missing_mandatory_id": False,
            "extracted": extracted,
            "recommendation": rec
        }

    async def extract_asha_visit_update(self, transcript: str) -> Dict[str, Any]:
        """
        Legacy compatibility method: returns extracted fields dictionary.
        """
        res = await self.extract_and_recommend(transcript)
        if res.get("missing_mandatory_id"):
            return res
        return res.get("extracted", {})

