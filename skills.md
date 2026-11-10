# Core Executable Skills (Tools)

## Overview

These are the core executable skills (tools) exposed to `gnani/gnani-evon-v3.3-30B-A3B` via the **LiveKit Agents / OpenAI-compatible tool-calling interface**.

Every skill executes deterministically, persists records to Neon PostgreSQL, and broadcasts real-time updates over WebSocket (<50ms) to the **Split-Screen Frontline Dashboard**.

---

## Unified Primary Skill: `log_flexible_health_interaction`

### When to Trigger
Whenever a frontline worker (ASHA, ANM, or AWW) speaks a visit update, counseling record, clinic measurement, child illness report, or ration delivery.

### Why It Exists
Frontline healthcare visits are multifaceted. Workers do not always measure or report BP and Hb. They discuss nutrition, diarrhea, immunization, counseling, side effects, and social barriers. 

This unified skill:
1. **Requires ONLY `rch_id`** (synthetic 12-digit ID starting with 999).
2. **Accepts all clinical vitals as optional/nullable** (BP, Hb, Weight, Temp, Symptoms, Supplies).
3. **Preserves zero information loss** via open-ended `dynamic_observations` for any other topics discussed.
4. **Tracks unmentioned routine checks** as gentle reminders for the next clinic camp.
5. **Generates non-diagnostic field recommendations** adhering strictly to NHM guidelines without making definitive medical diagnoses.
6. **Stages for ANM verification** if reported by ASHA, or directly syncs to RCH if recorded by ANM.

### Input JSON Schema

| Field | Type | Required | Description |
|---|---|---|---|
| `rch_id` | string | **Yes** | 12-digit synthetic RCH ID (e.g., `"999000104829"`). ONLY mandatory identifier. |
| `worker_role` | string (enum) | **Yes** | One of: `"ASHA"`, `"ANM"`, `"AWW"`. |
| `worker_name` | string | Yes | Spoken name of the frontline worker (e.g., `"Geeta Devi"`). |
| `beneficiary_name` | string | No | Spoken name of the mother or child (e.g., `"Sunita Devi"`). |
| `bp_reading` | string | No | Spoken Blood Pressure (e.g., `"142/92"`). |
| `bp_source` | string (enum) | No | `"MCP_CARD_HISTORY"` (if read from card by ASHA) or `"LIVE_ANM_MEASURED"`. |
| `hb_g_dl` | number | No | Hemoglobin in g/dL (e.g., `8.4` or `11.2`). |
| `weight_kg` | number | No | Beneficiary or child weight in kg (e.g., `52.5`). |
| `temperature_f` | number | No | Measured body temperature in °F (e.g., `101.4`). |
| `reported_symptoms` | array of strings | No | Specific symptoms mentioned (e.g., `["pedal_edema", "severe_headache"]`). |
| `supplies_or_meds` | array of strings | No | Medications or supplies discussed (e.g., `["10 IFA tablets left", "ORS packet given"]`). |
| `poshan_joint_visit_num` | integer | No | Mandated Poshan joint visit number (`8`, `9`, `11`, `14`, `15`). |
| `dynamic_observations` | array of objects | No | Catch-all for any other details spoken (zero information loss). |
| `unmentioned_routine_checks` | array of strings | No | Standard checks not mentioned (e.g., `["Blood Pressure (BP)", "Hemoglobin (Hb)"]`). |

### Dynamic Observations Schema (`dynamic_observations`)
Each item in `dynamic_observations` captures rich contextual data:
```json
{
  "category": "Maternal | Child_Health | Nutrition_THR | Immunization | Counseling_Social | General",
  "field_label": "Short descriptive label in English (e.g., IFA Nausea Adherence)",
  "spoken_value": "Exact detail spoken by the worker in native script and English",
  "status": "Normal | Note | Attention"
}
```

---

## Non-Diagnostic Recommendation Engine (`CareRecommendation`)

### Medical Safety Architecture
The system functions as an AI field decision-support assistant under the banner:
**`"AI-Generated Field Recommendations & Risk Indicators for ANM / Medical Officer Review"`**

It **NEVER** issues medical diagnoses. Instead, it evaluates indicators against NHM field guidelines to produce:

```json
{
  "priority_level": "ROUTINE | ATTENTION_NEEDED | URGENT_PHC_REFERRAL",
  "observed_indicators_summary": "Factual non-diagnostic summary (e.g., 'Last Sub-Centre BP was 142/92 combined with newly reported pedal swelling today.')",
  "recommended_next_steps": [
    "Advise immediate clinical evaluation by Medical Officer at Primary Health Centre",
    "Advise taking IFA tablet after night meal with lemon water to relieve nausea",
    "Note: BP and Hb were not recorded today; schedule check at upcoming VHSND camp"
  ],
  "spoken_reply_native": "Warm, natural 2-sentence spoken Indic response for Gnani Timbre v2.5 TTS readout."
}
```

---

## Supporting Sub-Operations

### 1. `sync_poshan_joint_visit`
Automatically triggered when `poshan_joint_visit_num` is in `[8, 9, 11, 14, 15]`.
Caches in offline queue if connectivity drops and syncs to MWCD upon reconnection.

### 2. `generate_paper_register_row`
Automatically triggered for every interaction. Formats a WhatsApp-ready row matching the physical paper audit register columns (Date, RCH ID, Name, Village, Worker, Vitals, Dynamic Observations, Recommendations).
