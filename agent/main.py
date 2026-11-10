import io
import os
import time
import wave
import base64
import asyncio
import json
import logging
from typing import Dict, Any, Optional, List
import httpx
from agent.gnani_config import (
    get_auth_headers,
    get_universal_stt_keyterms,
    GNANI_STT_REST_URL,
    GNANI_TTS_REST_URL,
    TIMBRE_VOICES,
    DEFAULT_SAMPLE_RATE,
)
from agent.evon_client import EvonClient, extract_rch_id
from agent.tools import log_flexible_health_interaction
from backend.database import get_db_pool

logger = logging.getLogger("aaa_setu.agent")

# Protect against Gnani REST concurrency limits (HTTP 429) as mandated in rules.md
_stt_semaphore = asyncio.Semaphore(1)

def split_wav_bytes(wav_bytes: bytes, max_chunk_sec: float = 24.0) -> List[bytes]:
    """
    Splits audio into valid WAV chunks of <= max_chunk_sec (default 24s)
    to safely respect Gnani's 30-second server limit while supporting 1-minute
    or longer recordings without truncation or HTTP 400 errors.
    """
    try:
        with wave.open(io.BytesIO(wav_bytes), 'rb') as r:
            n_channels = r.getnchannels()
            sampwidth = r.getsampwidth()
            framerate = r.getframerate()
            n_frames = r.getnframes()
            total_sec = n_frames / framerate

            if total_sec <= max_chunk_sec:
                return [wav_bytes]

            logger.info(f"Audio duration is {total_sec:.1f}s (> {max_chunk_sec}s). Chunking into <= {max_chunk_sec}s segments...")
            frames_per_chunk = int(max_chunk_sec * framerate)
            chunks: List[bytes] = []

            while True:
                chunk_frames = r.readframes(frames_per_chunk)
                if not chunk_frames:
                    break
                out_buf = io.BytesIO()
                with wave.open(out_buf, 'wb') as w:
                    w.setnchannels(n_channels)
                    w.setsampwidth(sampwidth)
                    w.setframerate(framerate)
                    w.writeframes(chunk_frames)
                chunks.append(out_buf.getvalue())

            return chunks
    except Exception as e:
        logger.warning(f"Could not parse WAV for splitting ({e}), sending whole payload.")
        return [wav_bytes]

class VoiceAgentPipeline:
    def __init__(self):
        self.evon_client = EvonClient()

    async def _transcribe_single_chunk(
        self,
        chunk_bytes: bytes,
        language_code: str,
        filename: str
    ) -> str:
        headers = get_auth_headers()
        headers.pop("Content-Type", None)

        keyterms = get_universal_stt_keyterms(language_code)
        data = {
            "model": "prisma-v3.0",
            "language_code": language_code,
            "format": "transcribe",  # Inverse Text Normalization for numeric vitals (142/92, 8.4)
            "itn_native_numerals": "false",  # Return Arabic numerals for BP/Hb indicators
            "keyterms": json.dumps(keyterms, ensure_ascii=False),
        }
        files = {
            "audio_file": (filename, chunk_bytes, "audio/wav")
        }

        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(GNANI_STT_REST_URL, headers=headers, data=data, files=files)
            if resp.status_code != 200:
                err_text = resp.text
                logger.error(f"Prisma STT error HTTP {resp.status_code}: {err_text}")
                raise RuntimeError(f"Gnani Prisma STT Error [HTTP {resp.status_code}]: {err_text}")

            result = resp.json()
            transcript = result.get("transcript") or result.get("text") or ""
            return transcript.strip()

    async def transcribe_audio(
        self,
        audio_bytes: bytes,
        language_code: str = "hi-IN",
        filename: str = "input.wav"
    ) -> str:
        """
        Transcribes audio using Gnani Prisma v3.0 STT via REST with ITN format='transcribe'.
        Automatically chunks audio exceeding 24 seconds to support 1-minute or longer speech.
        Surfaces raw API errors directly if request fails.
        """
        if len(audio_bytes) < 4:
            raise ValueError(f"Audio file is too short ({len(audio_bytes)} bytes)")

        header = audio_bytes[:4]
        logger.info(f"Received audio file for STT ({len(audio_bytes)} bytes). Header magic: {header}")

        # Check if client accidentally sent WebM (EBML: 0x1A 0x45 0xDF 0xA3)
        if header == b"\x1a\x45\xdf\xa3":
            logger.error("Received WebM audio instead of WAV. WebM cannot be parsed by Prisma's WAV demuxer.")
            raise ValueError(
                "Client sent WebM audio instead of PCM WAV. The browser must record using 16kHz PCM WAV with standard RIFF header."
            )

        chunks = split_wav_bytes(audio_bytes, max_chunk_sec=24.0)
        logger.info(f"Transcribing {len(chunks)} chunk(s) via Gnani Prisma v3.0...")

        transcripts = []
        async with _stt_semaphore:
            for idx, chunk_bytes in enumerate(chunks):
                chunk_name = f"chunk_{idx}_{filename}"
                transcript_part = await self._transcribe_single_chunk(chunk_bytes, language_code, chunk_name)
                if transcript_part:
                    transcripts.append(transcript_part)
                # Brief pacing between consecutive chunks to avoid 429 rate limit
                if len(chunks) > 1 and idx < len(chunks) - 1:
                    await asyncio.sleep(0.15)

        full_transcript = " ".join(transcripts).strip()
        logger.info(f"Full transcript combined ({len(chunks)} chunks): '{full_transcript}'")
        return full_transcript

    async def synthesize_speech(
        self,
        text: str,
        language_code: str = "hi-IN",
        voice: Optional[str] = None
    ) -> bytes:
        """
        Synthesizes spoken audio alert using Gnani Timbre v2.5.
        Surfaces raw API errors directly if request fails.
        """
        headers = get_auth_headers()
        headers["Content-Type"] = "application/json"

        selected_voice = voice or TIMBRE_VOICES.get(language_code, "Nalini")
        payload = {
            "text": text,
            "voice": selected_voice,
            "model": "timbre-v2.5",
            "language": language_code,
            "audio_config": {
                "sample_rate": DEFAULT_SAMPLE_RATE,
                "encoding": "linear_pcm",
                "container": "wav"
            }
        }

        logger.info(f"Calling Gnani Timbre TTS at {GNANI_TTS_REST_URL} (voice: {selected_voice})...")
        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(GNANI_TTS_REST_URL, headers=headers, json=payload)
            if resp.status_code != 200:
                err_text = resp.text
                logger.error(f"Timbre TTS error HTTP {resp.status_code}: {err_text}")
                raise RuntimeError(f"Gnani Timbre TTS Error [HTTP {resp.status_code}]: {err_text}")

            return resp.content

    async def process_frontline_relay(
        self,
        audio_bytes: Optional[bytes] = None,
        spoken_text: Optional[str] = None,
        source_role: str = "ASHA_RELAY",
        language_code: str = "hi-IN",
        offline_poshan: bool = False
    ) -> Dict[str, Any]:
        """
        End-to-End Frontline Relay Pipeline:
        1. Transcribe audio using Prisma v3.0 (if audio provided).
        2. Extract clinical indicators using Evon v3.3.
        3. Dispatch to deterministic tools (ANMOL queue, Poshan sync, Paper register).
        4. Synthesize spoken regional alert using Timbre v2.5.
        """
        # Step 1: STT
        if audio_bytes and not spoken_text:
            transcript = await self.transcribe_audio(audio_bytes, language_code=language_code)
        elif spoken_text:
            transcript = spoken_text
        else:
            raise ValueError("Either audio_bytes or spoken_text must be provided.")

        logger.info(f"Transcript received: '{transcript}'")

        # Step 2: Clinical Data Extraction & Triage via Evon v3.3
        # Pre-fetch patient baseline history if an RCH ID is mentioned in speech
        candidate_rch = extract_rch_id(transcript)
        baseline_mcp_card = None
        if candidate_rch:
            try:
                pool = await get_db_pool()
                async with pool.acquire() as conn:
                    row = await conn.fetchrow(
                        "SELECT * FROM synthetic_mcp_cards WHERE rch_id = $1;",
                        candidate_rch
                    )
                    if row:
                        baseline_mcp_card = dict(row)
            except Exception as e:
                logger.warning(f"Could not pre-fetch baseline MCP card for RCH {candidate_rch}: {e}")

        evon_res = await self.evon_client.extract_and_recommend(
            transcript,
            language_code=language_code,
            baseline_mcp_card=baseline_mcp_card
        )
        logger.info(f"Evon v3.3 result: {evon_res}")

        # Check if mandatory RCH ID is missing
        if evon_res.get("missing_mandatory_id"):
            prompt_text = evon_res.get("prompt_message") or "Kripya labharthi ka 12-digit RCH ID batayein."
            logger.info(f"Mandatory RCH ID missing. Prompting worker: {prompt_text}")

            audio_b64 = None
            try:
                tts_audio_bytes = await self.synthesize_speech(
                    text=prompt_text,
                    language_code=language_code
                )
                audio_b64 = base64.b64encode(tts_audio_bytes).decode("utf-8")
            except Exception as e:
                logger.warning(f"Could not generate TTS prompt: {e}")

            return {
                "transcript": transcript,
                "status": "AWAITING_RCH_ID",
                "prompt_message": prompt_text,
                "spoken_audio_b64": audio_b64,
                "extracted": evon_res.get("extracted", evon_res)
            }

        extracted = evon_res["extracted"]
        rec = evon_res.get("recommendation")

        # Step 3: Tool Execution (Unified Flexible Tool)
        worker_role = "ANM" if source_role == "ANM_DIRECT" else "ASHA"
        tool_res = await log_flexible_health_interaction(
            rch_id=extracted["rch_id"],
            worker_role=worker_role,
            worker_name=extracted.get("worker_name") or ("Nurse" if worker_role == "ANM" else "ASHA"),
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
            language_code=language_code,
            offline_poshan=offline_poshan,
            recommendation=rec
        )

        # Step 4: Spoken Audio Response with Timbre v2.5
        rec_info = tool_res["recommendation"]
        spoken_action = rec_info["spoken_reply_native"]

        audio_b64 = None
        try:
            tts_audio_bytes = await self.synthesize_speech(
                text=spoken_action,
                language_code=language_code
            )
            audio_b64 = base64.b64encode(tts_audio_bytes).decode("utf-8")
        except Exception as e:
            logger.warning(f"Could not generate TTS audio: {e}")

        return {
            "transcript": transcript,
            "extracted": extracted,
            "recommendation": rec_info,
            "triage": {
                "severity": rec_info["priority_level"],
                "action_hindi": rec_info["spoken_reply_native"],
                "flag_red_seal": rec_info["flag_red_seal"]
            },
            "poshan": tool_res.get("poshan"),
            "paper_register": tool_res.get("paper_register"),
            "queue_id": tool_res.get("queue_id"),
            "spoken_audio_b64": audio_b64,
            "status": tool_res.get("status")
        }

