# Project Context: AAA-Setu

## 1. Executive Summary

**AAA-Setu (ANMOL-Sahayak)** is a real-time, noise-resilient voice AI bridge built on the **Gnani Artha Sovereign Stack** (`Prisma v2.5/v3.0`, `Evon v3.3`, and `Timbre v2.5`) for the **Gnani.ai Great Indian AI Internship Challenge**.

It solves the **Double Documentation & Broken Handoff Crisis** across India's rural maternal and child healthcare triad (**AAA**):

### 1. ASHA — Accredited Social Health Activist

- Conducts village home visits.
- Inspects the mother's physical **MCP (Mother and Child Protection) Card** for previous Sub-Centre BP/Hb readings.
- Checks physical danger signs.
- Verbally relays updates because she lacks login access to ANMOL.

### 2. ANM — Auxiliary Nurse Midwife

- Performs clinical diagnostics (BP, Hb, urine albumin, vaccinations) at noisy monthly **VHSND** camps and Sub-Centres.
- Is burdened with entering approximately 200 indicators into the **MoHFW ANMOL tablet app**.
- Must also maintain mandatory physical paper registers for quality audits.

### 3. AWW — Anganwadi Worker

- Tracks nutrition and growth in the **MWCD Poshan Tracker app (v25.3.14)**.
- Must conduct joint home visits with the ASHA for Visits 8, 9, 11, 14, and 15.
- Faces workflow interruptions when rural connectivity drops.

---

## 2. Target Challenge Awards (₹50,000 Each)

| Award | Category | Project Alignment |
|---|---|---|
| **03 Real Deal Award** | Grassroots Impact | Solves an authentic, verified grassroots workflow problem for rural health workers. |
| **04 Noise Canceller Award** | Audio Technology | Operates over 8kHz/16kHz audio amidst simulated 75dB VHSND clinic noise (crying babies, crowd chatter, ceiling fans). |
| **01 Main Character Award** | Regional Language AI | Supports low-resource/regional Indian languages (`or-IN` Odia, `mr-IN` Marathi, `kn-IN` Kannada, `hi-IN` Hindi) natively in script. |
| **09 Demo Day Drop Award** | Presentation | Engineered around a visual 60-second split-screen live demo. |

---

## 3. Repository Directory Structure

```text
aaa-setu/
│
├── agent/
│   ├── main.py                 # LiveKit / Pipecat voice agent entrypoint
│   ├── gnani_config.py         # Prisma v2.5/v3.0 & Timbre v2.5 settings + keyterms
│   ├── evon_client.py          # OpenAI-compatible client for Evon v3.3 (enable_thinking=False)
│   ├── triage_engine.py        # Deterministic NHM maternal red-flag rules (BP, Hb, Edema)
│   └── tools.py                # Function-calling tools (ANMOL queue, Poshan sync, Register row)
│
├── backend/
│   ├── app.py                  # FastAPI server + WebSocket broadcaster for live UI
│   ├── database.py             # SQLite tables (synthetic beneficiaries, ANMOL queue, Poshan logs)
│   └── seed_synthetic_data.py  # Generates 100% synthetic MCP cards & worker profiles
│
├── frontend/
│   └── src/
│       └── components/
│           ├── VoiceSimulator.tsx  # Audio input + 8kHz VHSND noise mixer + live waveform
│           ├── AnmolQueuePanel.tsx # ANM Tablet View: ASHA-wise pre-filled verification cards
│           ├── PoshanSyncPanel.tsx # AWW View: Offline-resilient Joint Home Visits (8,9,11,14,15)
│           └── PaperRegister.tsx   # WhatsApp/Printable table matching physical audit register
│
├── context.md
├── rules.md
└── skills.md
```

---

## 4. Core Synthetic Database Schema (SQLite)

### Table 1: `synthetic_mcp_cards`

**Purpose:** Pre-seeded baseline data.

| Column | Data Type | Description / Example |
|---|---|---|
| `rch_id` | TEXT PRIMARY KEY | Synthetic RCH ID, e.g., `"999000104829"` |
| `mother_name` | TEXT | `"Sunita Devi (Synthetic)"` |
| `village` | TEXT | `"Kishanpur"` |
| `assigned_asha` | TEXT | `"Geeta Devi"` |
| `assigned_anm` | TEXT | `"Nurse Kavita"` |
| `last_vhsnd_date` | TEXT | `"2026-10-15"` |
| `last_subcentre_bp` | TEXT | `"138/88"` |
| `last_subcentre_hb` | REAL | `8.6` |
| `high_risk_red_seal` | BOOLEAN | `false` |

### Table 2: `anmol_verification_queue`

**Purpose:** Populated by the Voice Agent.

| Column | Data Type | Description / Example |
|---|---|---|
| `queue_id` | INTEGER PRIMARY KEY | Unique queue entry ID. |
| `source_role` | TEXT | `"ASHA_RELAY"` or `"ANM_DIRECT"` |
| `asha_worker_name` | TEXT | Enables ASHA-wise filtering for the ANM. |
| `rch_id` | TEXT | Synthetic RCH ID. |
| `recorded_bp` | TEXT | Recorded blood pressure. |
| `recorded_hb` | REAL | Recorded hemoglobin level. |
| `danger_signs_json` | TEXT | `'["pedal_edema", "severe_headache"]'` |
| `triage_severity` | TEXT | `"NORMAL"`, `"URGENT"`, or `"CRITICAL_RED_SEAL"` |
| `triage_action_hindi` | TEXT | Triage action displayed in Hindi. |
| `anm_approval_status` | TEXT | `"PENDING_VERIFICATION"` or `"SYNCED_TO_RCH"` |

### Table 3: `poshan_joint_visits`

**Purpose:** MWCD Poshan Tracker Sync.

| Column | Data Type | Description / Example |
|---|---|---|
| `visit_id` | INTEGER PRIMARY KEY | Unique visit entry ID. |
| `rch_id` | TEXT | Synthetic RCH ID. |
| `visit_number` | INTEGER | `8`, `9`, `11`, `14`, or `15`. |
| `joint_asha_aww_verified` | BOOLEAN | Whether joint ASHA + AWW execution was verified. |
| `sync_status` | TEXT | `"CACHED_OFFLINE"` or `"SYNCED_MWCD"` |

---

## 5. Remaining 8-Day Execution Schedule (November 2–10, 2026)

### Day 1 — Monday, November 2

**Focus: Repository Initialization & API Verification**

- Initialize the repository.
- Seed `synthetic_mcp_cards`.
- Verify `GNANI_API_KEY` on `app.gnani.ai/voice`.
- Test a 5-second WAV file with:
  - Prisma STT.
  - Timbre v2.5 TTS.

### Day 2 — Tuesday, November 3

**Focus: Voice Agent & LLM Integration**

- Stand up the Evon v3.3 endpoint using:
  - GGUF on a 24GB GPU, or
  - SGLang.
- Integrate `livekit-plugins-gnani` into `main.py`.
- Connect:
  - `tools.py`
  - `triage_engine.py`

### Day 3 — Wednesday, November 4

**Focus: Backend & Real-Time Communication**

- Build the FastAPI backend.
- Implement the WebSocket state broadcaster.
- Ensure voice tool calls:
  - Mutate SQLite.
  - Push JSON events to the frontend.
  - Target a latency of under 50ms.

### Day 4 — Thursday, November 5

**Focus: Split-Screen Dashboard**

Build the Next.js Split-Screen Dashboard with:

- `AnmolQueuePanel`
- `PoshanSyncPanel`
- `PaperRegister`
- Red-Seal Triage Alert banner.

### Day 5 — Friday, November 6

**Focus: Noise Cancellation Demonstration**

- Add the **VHSND 75dB Clinic Noise Toggle** to the frontend.
- Mix background crowd and baby-crying audio into the 8kHz stream.
- Visually demonstrate Noise Canceller Award performance.

### Day 6 — Saturday, November 7

**Focus: 60-Second Demo Video**

Record and edit the 60-second demo video with burned-in English subtitles.

The demo must show:

1. ASHA speaking a home-visit relay with noisy background audio.
2. Evon v3.3 identifying pre-eclampsia risk using historical MCP Card BP and newly observed swelling.
3. ANM's ANMOL verification queue and paper register updating live.

### Day 7 — Sunday, November 8

**Focus: Social Media Launch & Organic Engagement**

- Publish the demo video on LinkedIn and X.
- Tag Gnani AI.
- Include the following hashtags:

  - `#GreatIndianAIInternshipChallenge`
  - `#GnaniAI`

- Start gathering verified organic engagement:
  - Reactions.
  - Comments.
  - Reshares.

### Day 8–9 — Monday–Tuesday, November 9–10

**Focus: Final Outreach & Submission**

- Share the project across developer and college networks.
- Prepare the final nomination submission.
- Include:
  - Demo video URL.
  - Written architecture documentation.
  - LinkedIn post URL.
  - X post URL.

**Final Submission Deadline:**

<escape>11:59 PM IST, November 10, 2026.</escape>

Submit well before the deadline to avoid last-minute technical issues.

---