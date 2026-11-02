# Core Executable Skills (Tools)

## Overview

These are the core executable skills (tools) exposed to `gnani/gnani-evon-v3.3-30B-A3B` via the **LiveKit Agents / OpenAI-compatible tool-calling interface**.

Every skill executes deterministically and broadcasts state changes over WebSocket to the **Next.js Split-Screen Demo Dashboard**.

---

## Skill 1: `stage_asha_to_anmol_queue`

### When to Trigger
When an ASHA worker reports a home visit by reading historical Sub-Centre vitals from the mother's physical MCP Card alongside current home-visit observations.

### Why It Exists
ASHAs do not have data-entry logins for MoHFW's ANMOL tablet app.

This skill stages a pre-filled card organized by ASHA worker name so the ANM can approve and sync it to the RCH Portal in one tap.

### Input JSON Schema

| Field | Type | Required | Description |
|---|---|---|---|
| `asha_worker_name` | string | Yes | Name of the reporting ASHA worker. |
| `beneficiary_name` | string | Yes | Name of the pregnant woman or mother. |
| `rch_id` | string | Yes | 12-digit synthetic RCH ID from the MCP Card. |
| `gestational_month` | integer | No | Current month of pregnancy (1–9). |
| `mcp_card_last_bp` | string | No | Last BP recorded by the ANM at the Sub-Centre/VHSND (e.g., `"138/88"` or `"145/95"`). |
| `mcp_card_last_hb` | number | No | Last Hemoglobin (g/dL) recorded by the ANM on the MCP Card (e.g., `8.4`). |
| `home_danger_signs` | array of strings | Yes | Symptoms observed today (e.g., `["pedal_edema", "severe_headache", "blurred_vision", "bleeding", "high_fever", "none"]`). |
| `ifa_tablets_remaining` | integer | No | Number of Iron Folic Acid tablets remaining with the mother. |

---

## Skill 2: `commit_anm_vhsnd_record`

### When to Trigger
When an Auxiliary Nurse Midwife (ANM) directly dictates clinical measurements during a Village Health, Sanitation, and Nutrition Day (VHSND) or Sub-Centre ANC check-up.

### Why It Exists
ANMs have direct login permissions for ANMOL and perform clinical diagnostics, including:

- Blood Pressure (BP)
- Hemoglobin (Hb)
- Urine Albumin
- TT Injection
- Weight

### Input JSON Schema

| Field | Type | Required | Description |
|---|---|---|---|
| `anm_worker_name` | string | Yes | Name of the ANM worker. |
| `rch_id` | string | Yes | RCH ID of the beneficiary. |
| `beneficiary_name` | string | Yes | Name of the pregnant woman or mother. |
| `anc_visit_number` | integer | Yes | ANC visit number (1, 2, 3, or 4). |
| `measured_bp_systolic` | integer | Yes | Measured systolic BP. |
| `measured_bp_diastolic` | integer | Yes | Measured diastolic BP. |
| `measured_hb_g_dl` | number | Yes | Measured Hemoglobin in g/dL. |
| `weight_kg` | number | Yes | Beneficiary's weight in kilograms. |
| `urine_albumin` | string (enum) | Yes | One of: `negative`, `trace`, `positive`. |
| `ifa_tablets_issued` | integer | Yes | Number of IFA tablets issued. |
| `tt_booster_given` | boolean | Yes | Whether the TT booster was administered. |

---

## Skill 3: `evaluate_maternal_red_flags`

### When to Trigger
Automatically invoked inside the backend whenever Skill 1 or Skill 2 runs.

### Why It Exists
Combines deterministic NHM clinical rules with Evon v3.3 reasoning so high-risk pregnancies are never missed.

### Deterministic Triage Rules

#### 1. Severe Pre-Eclampsia / Eclampsia Risk

**Severity:** CRITICAL

**Condition:**

- Systolic BP ≥ 140 OR diastolic BP ≥ 90.
- AND at least one of the following:
  - `pedal_edema`
  - `severe_headache`
  - `blurred_vision`
  - `urine_albumin == "positive"`

**Action:**

- Flag for MCP Card Red Seal.
- Trigger immediate PHC Medical Officer referral.
- Trigger 108 ambulance referral alert.

#### 2. Borderline Hypertension Watch

**Severity:** URGENT

**Condition:**

- Systolic BP ≥ 135 OR diastolic BP ≥ 85, as recorded on the MCP Card.
- AND new `pedal_edema` or `severe_headache` observed by ASHA during the home visit.

**Action:**

- Urgent same-day ANM Sub-Centre BP re-check required.

#### 3. Severe Maternal Anemia

**Severity:** CRITICAL

**Condition:**

- Hemoglobin (Hb) < 7.0 g/dL: Severe anemia.
- Hemoglobin (Hb) < 9.0 g/dL with fatigue/pallor: Moderate-to-high anemia risk.

**Action:**

- Flag for PHC referral and clinician-directed iron sucrose assessment.
- Track the prescribed IFA dose and adherence.

---

## Skill 4: `sync_poshan_joint_visit`

### When to Trigger
When the voice update mentions a joint home visit with the Anganwadi Worker (AWW) or child nutrition/growth tracking.

### Why It Exists
MWCD's Poshan Tracker (v25.3.14) mandates joint ASHA + AWW execution for Home Visits 8, 9, 11, 14, and 15.

The application disables the "Next" button when offline.

This skill caches the joint visit payload using an offline-first approach and synchronizes it when connectivity returns.

### Input JSON Schema

| Field | Type | Required | Description |
|---|---|---|---|
| `visit_number` | integer (enum) | Yes | One of: `8`, `9`, `11`, `14`, `15`. |
| `child_or_mother_name` | string | Yes | Name of the child or mother. |
| `child_weight_kg` | number | No | Child's weight in kilograms. |
| `lbw_counseling_shown` | boolean | No | Whether Low Birth Weight (LBW) counseling was completed. |
| `thr_packets_verified` | integer | No | Number of Take-Home Ration (THR) packets verified. |

---

## Skill 5: `generate_paper_register_row`

### When to Trigger
At the conclusion of every voice entry.

### Why It Exists
Quality auditors still demand physical paper registers during inspections.

This skill formats the exact extracted fields into a clean row matching the physical register columns and sends it to the worker's WhatsApp screen.

---

# 4. `rules.md` — Engineering, API & Compliance Guardrails

Save the block below as `rules.md` (and copy it into `.cursorrules` if you use Cursor).

It enforces:

- Hackathon disqualification rules.
- Gnani API constraints.
- Evon v3.3 optimization rules.

(**Note**: Consult the `Gnani` MCP to verify things here if needed.)