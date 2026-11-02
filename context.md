# AAA-Setu (ANMOL-Sahayak): Architecture & Domain Context

## 1. Executive Summary

**AAA-Setu (ANMOL-Sahayak)** is a real-time, noise-resilient voice AI bridge built on the **Gnani Artha Sovereign Stack** (`Prisma v2.5/v3.0`, `Evon v3.3`, and `Timbre v2.5`) with **Neon PostgreSQL** as the persistent backend for the **Gnani.ai Great Indian AI Internship Challenge**.

It solves the **Double Documentation & Broken Handoff Crisis** across India's rural maternal and child healthcare triad (**AAA**):

### 1. ASHA — Accredited Social Health Activist
- Conducts village home visits.
- Inspects the mother's physical **MCP (Mother and Child Protection) Card** for previous Sub-Centre BP/Hb readings.
- Checks physical danger signs.
- Verbally relays updates because she lacks login access to ANMOL.

### 2. ANM — Auxiliary Nurse Midwife
- Performs clinical diagnostics (BP, Hb, urine albumin, vaccinations) at noisy monthly **VHSND** camps and Sub-Centres.
- Burdened with entering approximately 200 indicators into the **MoHFW ANMOL tablet app**.
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

## 3. Frontline 3-Phase Workflow

### Phase 1: The ASHA Worker’s Home Visit (At the Mother's House)
- ASHA worker Geeta visits Sunita Devi (7 months pregnant) during Joint Home Visit #8.
- Switches on 75dB Background Noise (crying babies, crowd chatter).
- Speaks naturally: *"Main ASHA Geeta bol rahi hoon. RCH ID 999000104829, Sunita Devi, satva mahina, Joint Visit number 8. MCP card mein pichle camp ka BP 142 by 92 aur Hb 8.4 likha hai. Aaj Sunita ke pairon mein sujan hai aur tez sar dard hai. Uske paas 10 IFA goli bachi hain."*
- Prisma STT filters noise, converts spoken numbers to clean digits (142/92, 8.4, 10).
- Evon v3.3 extracts JSON fields and triage engine flags High-Risk Pre-Eclampsia & Severe Anemia.
- Timbre v2.5 immediately speaks back the emergency referral instruction.
- WhatsApp paper register row is formatted and saved for audit inspections.

### Phase 2: The ANM Nurse’s Workflow (At Sub-Centre / VHSND Camp)
- Nurse Kavita views the "ASHA-Wise Verification Queue" on her ANMOL tablet view.
- Sees the pre-filled verification card staged under "Reported by: ASHA Geeta" with 🔴 CRITICAL: Pre-Eclampsia & Severe Anemia badge.
- Taps single button: "Approve & Sync to RCH Portal" (zero typing).
- ANM can also switch to "ANM Camp Mode" for hands-free dictation during noisy clinics.

### Phase 3: The Anganwadi Worker’s (AWW) Workflow (Poshan Tracker Sync)
- Captures mandated Joint Home Visits (8, 9, 11, 14, 15).
- Automatically caches visit payloads in an offline-resilient queue when rural connection drops, and syncs upon reconnection.

