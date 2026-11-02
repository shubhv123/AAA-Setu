import os
import json
import logging
from typing import Dict, Any, Optional
import httpx
from agent.gnani_config import (
    get_auth_headers,
    GNANI_EVON_API_BASE,
    GNANI_EVON_MODEL,
)

logger = logging.getLogger("aaa_setu.evon")

class EvonClient:
    def __init__(self, base_url: Optional[str] = None, model: Optional[str] = None):
        self.base_url = (base_url or GNANI_EVON_API_BASE).rstrip("/")
        self.model = model or GNANI_EVON_MODEL

    async def chat_completion(
        self,
        messages: list,
        temperature: float = 0.6,
        top_p: float = 0.95,
        tools: Optional[list] = None,
        tool_choice: Optional[str] = None,
        response_format: Optional[dict] = None,
    ) -> Dict[str, Any]:
        """
        Calls Evon v3.3 (OpenAI-compatible) endpoint with enable_thinking=False
        to ensure low conversational latency and native Indic script fidelity.
        """
        headers = get_auth_headers()
        headers["Content-Type"] = "application/json"

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "top_p": top_p,
            # Mandatory latency control parameter for Evon v3.3 live voice turns
            "enable_thinking": False,
        }

        if tools:
            payload["tools"] = tools
        if tool_choice:
            payload["tool_choice"] = tool_choice
        if response_format:
            payload["response_format"] = response_format

        url = f"{self.base_url}/chat/completions"
        logger.info(f"Dispatching inference request to Evon v3.3 at {url}...")

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            if response.status_code != 200:
                error_body = response.text
                logger.error(f"Evon v3.3 API returned HTTP {response.status_code}: {error_body}")
                raise RuntimeError(
                    f"Gnani Evon v3.3 Inference Error [HTTP {response.status_code}]: {error_body}"
                )
            return response.json()

    async def extract_asha_visit_update(self, transcript: str) -> Dict[str, Any]:
        """
        Extracts structured fields from an ASHA worker's spoken relay.
        Adheres strictly to Skill 1 schema in skills.md.
        """
        system_prompt = (
            "You are AAA-Setu AI Sahayak, a clinical data extraction assistant for India's rural health triad "
            "(ASHA, ANM, AWW). Your task is to extract structured indicators from an ASHA worker's spoken Hindi/Indic visit update.\n"
            "Rules:\n"
            "1. Extract the RCH ID (12-digit string prefixed with 999).\n"
            "2. Extract Beneficiary Name, Gestational Month, Last BP (systolic/diastolic from MCP card), "
            "Last Hb (g/dL from MCP card), danger signs observed today (e.g. pedal_edema, severe_headache, blurred_vision, bleeding, high_fever), "
            "IFA tablets remaining, and Joint Visit number (if mentioned, e.g. 8, 9, 11, 14, 15).\n"
            "3. If any field is not mentioned, set it to null.\n"
            "4. Return ONLY valid JSON with keys: 'asha_worker_name', 'beneficiary_name', 'rch_id', "
            "'gestational_month', 'mcp_card_last_bp', 'mcp_card_last_hb', 'home_danger_signs', "
            "'ifa_tablets_remaining', 'joint_visit_number', 'missing_fields'."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"ASHA Spoken Input:\n{transcript}"}
        ]

        # Use response_format json_object if supported or structured prompt
        try:
            res = await self.chat_completion(
                messages=messages,
                response_format={"type": "json_object"}
            )
            content = res["choices"][0]["message"]["content"]
            data = json.loads(content)
            return data
        except Exception as e:
            logger.error(f"Failed to extract structured fields via Evon v3.3: {e}")
            raise

