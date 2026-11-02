# 1. Non-Negotiable Hackathon Compliance Rules (Zero Tolerance)

- **STRICT SYNTHETIC DATA MANDATE:** Never hardcode, log, display, or speak real phone numbers, real Aadhaar numbers, real PAN numbers, real bank account numbers, or real recorded patient calls. Any violation results in immediate disqualification.

### Synthetic Formats Only

- **Phone Numbers:** Must follow the format `+91-90000-XXXXX`.
- **RCH IDs:** Must use synthetic 12-digit strings prefixed with `999` (e.g., `999000104829`).
- **Aadhaar References:** Must only be stored as boolean flags (`e_kyc_verified: true/false`). Never store or expose 12-digit Aadhaar numbers.

### Mandatory AI Disclosure

Any outbound or interactive voice session must clearly state in both the UI and initial greeting that it is an AI-powered assistant:

`AAA-Setu AI Sahayak`

---

# 2. Public Health Domain & Role Accuracy Rules

### ANMOL Access Restrictions

- **Never give an ASHA worker direct write-access to ANMOL in the UI.**
- ANMOL (ANM Online) is the MoHFW tablet application for Auxiliary Nurse Midwives (ANMs).
- When an ASHA speaks into the application, her output must populate the **ASHA-Wise Pre-Filled Verification Queue** inside the ANM's ANMOL view.

### Clinical Diagnostics Attribution

Clinical measurements must be clearly attributed according to the user's role.

| Mode | Data | Required Label |
|---|---|---|
| ASHA Mode | BP and Hemoglobin (Hb) | `Last Sub-Centre / VHSND Reading from MCP Card` |
| ASHA Mode | Swelling/edema, headache, fever, IFA adherence | `Today's ASHA Home Observation` |
| ANM Mode | BP, Hb, weight, urine albumin | `Live VHSND / Sub-Centre Clinical Measurement` |

### WCD vs. MoHFW Separation

Keep the following schemas and workflows strictly separate:

- **MoHFW:** ANMOL / RCH Portal.
- **MWCD:** Poshan Tracker v25.3.14 Joint Home Visits 8, 9, 11, 14, and 15.

---

# 3. Gnani Speech API Rules (`Prisma` & `Timbre`)

### Authentication Header

Every direct REST or WebSocket handshake to Gnani Speech APIs must pass the following authentication header:

```python
X-API-Key-ID: os.environ["GNANI_API_KEY"]
```

**Security requirements:**
- Never hardcode API keys.
- Never commit API keys to Git.
- Load credentials through environment variables.

### Concurrency Limit Protection

Gnani's REST STT endpoint allows only **1 active request at a time** and returns HTTP `429 RATE_LIMITED` without a `Retry-After` header.

Therefore:

1. Always prefer WebSocket Streaming:

   `wss://api.vachana.ai/stt/v3/stream`

   Use `livekit-plugins-gnani` or `pipecat-gnani` for live voice turns.

2. If calling REST `POST /stt/v3`:
   - Wrap calls in an `asyncio.Semaphore(1)`.
   - Implement exponential backoff.
   - Keep audio clips under 30 seconds.

### WebSocket Audio Framing

Streaming STT requires:

- **Audio format:** Signed 16-bit little-endian mono PCM (`linear_pcm`).
- **Frame size:** 1,024 bytes.
- **Samples per frame:** 512 samples.
- **Frame duration:**
  - 32 ms at 16 kHz.
  - 64 ms at 8 kHz.

Calculation:

```text
512 samples × 2 bytes = 1,024 bytes
```

### Always Enable Inverse Text Normalization (ITN)

Set:

```python
format="transcribe"
```

on Prisma STT so spoken numbers (BP, Hb, weight, tablets) are returned as digits rather than spelled-out words.

### Prisma v3.0 Context Rules

- `keyterms`, `topic`, and `codemix` are ONLY valid when:

  ```python
  model="prisma-v3.0"
  ```

- Sending these parameters to `prisma-v2.5` raises HTTP `400 INVALID_CONFIG`.

#### Indic Auto Language Detection

When using:

```python
language_code="indic-auto"
```

with `prisma-v3.0`:

- Pass at most **4 candidate languages**.

Example:

```python
["hi-IN", "mr-IN", "or-IN", "en-IN"]
```

- Passing 5 or more languages raises HTTP `400`.
- Never leave `indic-auto` unconstrained on REST clips ending in silence.

### Timbre TTS Version Rule

Never use:

```python
model="timbre-v2.0"
```

This version is retired/deprecated and raises a `ValueError` in `pipecat-gnani`.

Always use one of the following:

| Model | Available Voices | Example Voices |
|---|---:|---|
| `timbre-v2.5` | 42 | `Nalini`, `Pranav`, `Kaveri` |
| `timbre-v3.0` | 13 | `Avinash`, `Chetana` |

**Important:** Ensure that the selected `voice` belongs to the chosen model.

---

# 4. Gnani Evon v3.3 (`30B-A3B`) Inference Rules

### Native Indic Script Requirement

- **Pass native Indic script, NEVER Romanized text.**
- Evon v3.3's expanded 163,072-token BPE vocabulary reduces Indic token fertility by 38.6% on native scripts.
- Romanized Indic text is heavily penalized.

**Implementation requirement:**

Feed Prisma's native-script transcript directly into Evon v3.3 without converting it into Romanized text.

### Latency Control (`enable_thinking`)

On the live conversational voice path, ALWAYS set:

```python
enable_thinking=False
```

inside `apply_chat_template`.

This allows Evon v3.3 to respond immediately without generating a long internal reasoning trace before speaking.

### Recommended Inference Parameters

Use the following settings for tool calling and instruction following:

```python
temperature=0.6
top_p=0.95
```

---

# 5. `context.md` — Project & Architecture Context

Save the block below as `context.md` in your repository.

It provides your team and AI code editor with complete project context, including:

- Problem statement and project objectives.
- Database schema.
- Repository directory structure.
- System architecture.
- 8-day sprint schedule.

(**Note**: Consult the `Gnani` MCP to verify things here if needed.)