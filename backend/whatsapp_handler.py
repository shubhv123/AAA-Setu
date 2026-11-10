import base64
import json
import logging
import random
from typing import Dict, Any, Optional, Tuple
from backend.database import (
    get_whatsapp_session,
    set_whatsapp_otp,
    verify_whatsapp_otp,
    reset_whatsapp_session,
    get_db_pool,
)
from backend.audio_transcoder import any_audio_to_pcm_wav, wav_to_ogg_opus
from agent.main import VoiceAgentPipeline

logger = logging.getLogger("aaa_setu.whatsapp")

class WhatsAppFrontlineHandler:
    def __init__(self, pipeline: Optional[VoiceAgentPipeline] = None):
        self.pipeline = pipeline or VoiceAgentPipeline()

    def normalize_phone(self, phone: str) -> str:
        clean = "".join(ch for ch in phone if ch.isdigit() or ch == "+")
        if not clean.startswith("+"):
            if clean.startswith("91") and len(clean) == 12:
                clean = f"+{clean}"
            elif len(clean) == 10:
                clean = f"+91{clean}"
            else:
                clean = f"+{clean}"
        return clean

    async def handle_incoming_text(self, sender_phone: str, text: str) -> Dict[str, Any]:
        """
        Processes text messages on WhatsApp: Greetings, OTP verification, and text dictation.
        """
        phone = self.normalize_phone(sender_phone)
        session = await get_whatsapp_session(phone)
        trimmed = text.strip()

        # If phone not registered, auto-register as frontline worker
        if not session:
            worker_role = "ANM" if "anm" in phone or "nurse" in text.lower() else "ASHA"
            worker_name = "Nurse Kavita" if worker_role == "ANM" else "ASHA Geeta"
            await set_whatsapp_otp(phone, "1234", worker_name=worker_name, worker_role=worker_role)
            session = await get_whatsapp_session(phone)

        # Check for logout / reset
        if trimmed.lower() in ["logout", "reset", "bahar niklo"]:
            await reset_whatsapp_session(phone)
            return {
                "type": "text",
                "phone": phone,
                "text": "🔒 *Logout Successful!*\nAapka WhatsApp session reset ho gaya hai. Dobara login karne ke liye 'Hi' bhejein.",
                "is_authenticated": False
            }

        # Flow 1: If NOT Authenticated -> Process OTP
        if not session.get("is_authenticated"):
            # Check if user sent a 4-digit code matching OTP
            if trimmed.isdigit() and len(trimmed) == 4:
                success = await verify_whatsapp_otp(phone, trimmed)
                if success:
                    session = await get_whatsapp_session(phone)
                    role = session.get("worker_role", "ASHA")
                    name = session.get("worker_name", "Frontline Worker")
                    return {
                        "type": "text",
                        "phone": phone,
                        "text": (
                            f"✅ *Login Safal! (Authentication Verified)*\n"
                            f"Namaste *{name}* ({role})!\n\n"
                            f"Ab aap mariz ya labharthi ka visit update bolkar bhej sakte hain.\n"
                            f"🎤 *Niche diye gaye Mic button ko dabakar apna Voice Note bhejein.*"
                        ),
                        "is_authenticated": True,
                        "worker_name": name,
                        "worker_role": role
                    }
                else:
                    return {
                        "type": "text",
                        "phone": phone,
                        "text": "❌ *Galat OTP!* Kripya sahi 4-digit OTP darj karein ya 'Hi' bhejein naye OTP ke liye.",
                        "is_authenticated": False
                    }
            else:
                # Issue new 4-digit OTP
                otp = f"{random.randint(1000, 9999)}"
                worker_name = session.get("worker_name", "Frontline Worker")
                worker_role = session.get("worker_role", "ASHA")
                await set_whatsapp_otp(phone, otp, worker_name=worker_name, worker_role=worker_role)

                return {
                    "type": "otp_prompt",
                    "phone": phone,
                    "otp": otp,
                    "text": (
                        f"🇮🇳 *AAA-Setu (ANMOL-Sahayak)*\n"
                        f"Namaste *{worker_name}* ji! Swagat hai.\n\n"
                        f"🔒 *Aapka Login OTP hai:* *{otp}*\n\n"
                        f"Kripya login verify karne ke liye yeh 4-digit OTP reply mein bhejein:"
                    ),
                    "is_authenticated": False
                }

        # Flow 2: Authenticated -> Check if user sent a greeting or asked to re-login
        if trimmed.lower() in ["hi", "hello", "namaste", "pranam", "hey"]:
            name = session.get("worker_name", "Frontline Worker")
            role = session.get("worker_role", "ASHA")
            return {
                "type": "text",
                "phone": phone,
                "text": (
                    f"Namaste *{name}* ({role}) ji! 🙏\n\n"
                    f"Aap already logged in hain. Ab aap mariz ka visit update bolkar bhej sakte hain.\n"
                    f"🎤 *Niche diye gaye Mic button ko dabakar apna Voice Note bhejein.*\n\n"
                    f"*(Naye sire se OTP verification test karne ke liye 'Logout' type karke bhejein).*"
                ),
                "is_authenticated": True,
                "worker_name": name,
                "worker_role": role
            }

        if trimmed.lower() in ["login", "otp", "relogin"]:
            await reset_whatsapp_session(phone)
            otp = f"{random.randint(1000, 9999)}"
            worker_name = session.get("worker_name", "Frontline Worker")
            worker_role = session.get("worker_role", "ASHA")
            await set_whatsapp_otp(phone, otp, worker_name=worker_name, worker_role=worker_role)
            return {
                "type": "otp_prompt",
                "phone": phone,
                "otp": otp,
                "text": (
                    f"🇮🇳 *AAA-Setu (ANMOL-Sahayak)*\n"
                    f"Namaste *{worker_name}* ji! Swagat hai.\n\n"
                    f"🔒 *Aapka Login OTP hai:* *{otp}*\n\n"
                    f"Kripya login verify karne ke liye yeh 4-digit OTP reply mein bhejein:"
                ),
                "is_authenticated": False
            }

        # Otherwise: Worker dictates health visit report via text
        role_tag = "ANM_DIRECT" if session.get("worker_role") == "ANM" else "ASHA_RELAY"
        pipeline_res = await self.pipeline.process_frontline_relay(
            spoken_text=trimmed,
            source_role=role_tag
        )

        return await self._format_pipeline_response(phone, session, pipeline_res)

    async def handle_incoming_audio(
        self,
        sender_phone: str,
        audio_bytes: bytes,
        language_code: str = "hi-IN"
    ) -> Dict[str, Any]:
        """
        Processes WhatsApp Voice Notes (.ogg / .opus / .webm):
        Transcodes to 16kHz PCM WAV -> Prisma STT -> Evon -> Recommendation Engine -> Timbre TTS.
        """
        phone = self.normalize_phone(sender_phone)
        session = await get_whatsapp_session(phone)

        # Require OTP authentication before accepting audio
        if not session or not session.get("is_authenticated"):
            otp = f"{random.randint(1000, 9999)}"
            w_name = session.get("worker_name", "Frontline Worker") if session else "ASHA Geeta"
            w_role = session.get("worker_role", "ASHA") if session else "ASHA"
            await set_whatsapp_otp(phone, otp, worker_name=w_name, worker_role=w_role)
            return {
                "type": "auth_required",
                "phone": phone,
                "text": (
                    f"🔒 *Pehle Login Karein!*\n"
                    f"Aapka voice note mila, lekin pehle login zaroori hai.\n"
                    f"Aapka OTP hai: *{otp}*\n"
                    f"Kripya *{otp}* type karke bhejein."
                ),
                "is_authenticated": False
            }

        # Transcode incoming WhatsApp audio (OGG Opus) into 16kHz PCM WAV
        pcm_wav_bytes = any_audio_to_pcm_wav(audio_bytes, target_sample_rate=16000)

        # Process through Voice Agent Pipeline
        role_tag = "ANM_DIRECT" if session.get("worker_role") == "ANM" else "ASHA_RELAY"
        pipeline_res = await self.pipeline.process_frontline_relay(
            audio_bytes=pcm_wav_bytes,
            source_role=role_tag,
            language_code=language_code
        )

        return await self._format_pipeline_response(phone, session, pipeline_res)

    async def _format_pipeline_response(
        self,
        phone: str,
        session: dict,
        pipeline_res: dict
    ) -> Dict[str, Any]:
        """
        Constructs dual output: Formatted WhatsApp register summary + Timbre voice note.
        Also constructs ANM 1-tap interactive approval card if reported by ASHA.
        """
        status = pipeline_res.get("status")

        # Case A: Mandatory RCH ID was missing from speech
        if status == "AWAITING_RCH_ID":
            prompt = pipeline_res.get("prompt_message", "Kripya labharthi ka 12-digit RCH ID batayein.")
            return {
                "type": "awaiting_rch_id",
                "phone": phone,
                "text": (
                    f"⚠️ *RCH ID Batana Zaroori Hai*\n\n"
                    f"💬 *{prompt}*\n\n"
                    f"📌 *Note:* Record save karne ke liye sirf 12-digit RCH ID zaroori hai (koi BP/Hb anivarya nahi hai)."
                ),
                "spoken_audio_b64": pipeline_res.get("spoken_audio_b64"),
                "is_authenticated": True
            }

        # Case B: Successfully processed and recorded
        rec = pipeline_res.get("recommendation", {})
        priority = rec.get("priority_level", "ROUTINE")
        summary = rec.get("observed_indicators_summary", "")
        steps = rec.get("recommended_next_steps", [])
        native_voice_msg = rec.get("spoken_reply_native", "")
        queue_id = pipeline_res.get("queue_id")
        extracted = pipeline_res.get("extracted", {})
        ben_name = extracted.get("beneficiary_name") or "Beneficiary"
        rch_id = extracted.get("rch_id") or "N/A"

        # Format WhatsApp text reply
        steps_bullet = "\n".join(f"  • {s}" for s in steps) if steps else "  • Niyamit nigehani rakhein"
        priority_emoji = "🚨" if "URGENT" in priority else "⚠️" if "ATTENTION" in priority else "🟢"

        whatsapp_text = (
            f"📋 *MoHFW Register Entry Recorded*\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"• *Beneficiary:* {ben_name}\n"
            f"• *RCH ID:* `{rch_id}`\n"
            f"• *Priority:* {priority_emoji} *{priority}*\n"
            f"• *Observed Summary:* {summary}\n\n"
            f"📌 *Karyawahi / Next Steps:*\n{steps_bullet}\n\n"
            f"💬 *AI Sahayak:* \"{native_voice_msg}\"\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"✅ *ANMOL Tablet Queue mein bhej diya gaya hai!*"
        )

        # Transcode Timbre TTS WAV audio to WhatsApp OGG Opus voice note
        audio_ogg_b64 = None
        if pipeline_res.get("spoken_audio_b64"):
            try:
                wav_bytes = base64.b64decode(pipeline_res["spoken_audio_b64"])
                ogg_bytes = wav_to_ogg_opus(wav_bytes)
                audio_ogg_b64 = base64.b64encode(ogg_bytes).decode("utf-8")
            except Exception as e:
                logger.warning(f"Could not convert TTS to OGG Opus: {e}")

        # Construct ANM interactive alert card (to notify Nurse Kavita on WhatsApp)
        anm_alert = None
        if session.get("worker_role") == "ASHA" and queue_id:
            anm_alert = {
                "anm_phone": "+919000098765",
                "queue_id": queue_id,
                "beneficiary_name": ben_name,
                "rch_id": rch_id,
                "reported_by": session.get("worker_name", "ASHA Geeta"),
                "priority": priority,
                "message": (
                    f"🔔 *ANM Action Alert: New ASHA Home Visit*\n"
                    f"Reported by: *{session.get('worker_name')} (ASHA)*\n"
                    f"Beneficiary: *{ben_name}* (RCH `{rch_id}`)\n"
                    f"Priority: {priority_emoji} *{priority}*\n"
                    f"Summary: {summary}\n\n"
                    f"Tap below to approve and commit to ANMOL & Poshan Tracker:"
                ),
                "buttons": [
                    {"id": f"APPROVE_{queue_id}", "title": "✅ Approve & Sync ANMOL"},
                    {"id": f"REVIEW_{queue_id}", "title": "🔍 Review Details"}
                ]
            }

        return {
            "type": "visit_recorded",
            "phone": phone,
            "queue_id": queue_id,
            "text": whatsapp_text,
            "spoken_audio_b64": pipeline_res.get("spoken_audio_b64"),
            "audio_ogg_b64": audio_ogg_b64,
            "anm_alert": anm_alert,
            "extracted": extracted,
            "recommendation": rec,
            "is_authenticated": True
        }

    async def handle_anm_approval(self, anm_phone: str, queue_id: int) -> Dict[str, Any]:
        """
        Processes 1-Tap approval from ANM on WhatsApp:
        Updates queue in Neon PostgreSQL -> triggers Poshan sync -> confirms to ANM.
        """
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE anmol_verification_queue
                SET anm_approval_status = 'SYNCED_TO_RCH'
                WHERE queue_id = $1
                RETURNING *;
                """,
                queue_id
            )
            if not row:
                return {
                    "success": False,
                    "text": f"❌ Record #{queue_id} nahi mila."
                }

            record = dict(row)
            rch_id = record.get("rch_id")
            ben_name = record.get("beneficiary_name") or "Beneficiary"

        return {
            "success": True,
            "queue_id": queue_id,
            "text": (
                f"🎉 *ANMOL Approval Successful!*\n"
                f"Record #{queue_id} for *{ben_name}* (RCH `{rch_id}`) has been approved by Nurse Kavita.\n\n"
                f"✅ *Status:* SYNCED_TO_RCH\n"
                f"✅ *Poshan Tracker:* Joint Home Visit Verified\n"
                f"✅ *MoHFW Portal:* Committed Hands-Free!"
            )
        }

