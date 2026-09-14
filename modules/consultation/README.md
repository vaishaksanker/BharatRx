# AI Pre-Consultation Module (`modules/consultation/`)

## 👤 Module Owner
**Namita** (Branch: `feature/namita-consultation`)

---

## 1. What the Module Does

The `modules/consultation/` module powers the **BharatRx AI Pre-Consultation Engine**. It conducts an adaptive, empathetic, conversational intake with patients before their physician consultation.

The pre-consultation engine:
- Engages the patient in an intelligent, multi-turn clinical dialogue.
- Inquires about the chief complaint, onset duration, severity (1–10 scale), location, progression, and associated symptoms.
- Collects vital signs (temperature, blood pressure, heart rate) when provided.
- Records documented chronic conditions, active medications (with dosage and frequency), and known drug/substance allergies.
- Attaches optional prescription or clinical image references.
- Flags acute red-flag symptoms using rule-based triage (`routine` vs. `urgent`).
- Produces a doctor-ready, standardized clinical intake summary (SOAP-style) with targeted physician review questions.
- Constructs the unified `Patient` profile that Vaishak's backend provides to Sidharth's safety engine (`modules/safety_engine/`).

> [!IMPORTANT]
> **Clinical Decision-Support Boundaries**:  
> BharatRx is strictly an intake and decision-support system. It **does NOT** diagnose illnesses, prescribe medications, or recommend treatments. Final diagnostic and therapeutic authority rests exclusively with the examining physician.

---

## 2. Module Architecture

```
                                  [ Patient ]
                                       │
                                       ▼ (Patient Messages)
                         ┌───────────────────────────┐
                         │   ConsultationEngine      │
                         └──────┬─────────────┬──────┘
                                │             │
             ┌──────────────────┴───┐     ┌───┴─────────────────┐
             │ GeminiService (LLM)  │     │ MockEngine (Offline)│
             │ [if GEMINI_API_KEY]  │     │ [Auto-fallback]     │
             └──────────────────────┘     └─────────────────────┘
                                │             │
                                └──────┬──────┘
                                       ▼
                         ┌───────────────────────────┐
                         │    UrgencyDetector        │ (Triage: routine vs urgent)
                         └─────────────┬─────────────┘
                                       ▼
                         ┌───────────────────────────┐
                         │    ReportGenerator        │
                         └──────┬─────────────┬──────┘
                                │             │
                                ▼             ▼
                     [ ConsultationReport ] [ Unified PatientProfile ]
                                │                     │
                                ▼                     ▼
                       (Doctor Dashboard)    (Sidharth Safety Engine)
```

---

## 3. File Structure

```text
modules/consultation/
├── __init__.py                 # Public module exports and package initialization
├── schemas.py                  # Pydantic data contracts (docs/integration.md compliant)
├── engine.py                   # Main ConsultationEngine coordinator class
├── conversation_manager.py     # In-memory session tracking, slots, and dialogue history
├── gemini_service.py           # Gemini Generative AI client with graceful fallback
├── mock_engine.py              # Deterministic adaptive intake engine for 4 key conditions
├── urgency_detector.py         # Red-flag clinical safety screening and triage
├── report_generator.py         # Clinical report and unified patient profile generator
├── api.py                      # FastAPI REST API (POST /message & POST /report)
├── mock_data.py                # Synthetic demo patients and test scenarios
├── requirements.txt            # Module-specific dependencies
├── README.md                   # Complete module documentation & integration guide
└── tests/
    ├── __init__.py
    └── test_consultation.py    # Comprehensive test suite (14 unit & integration tests)
```

---

## 4. Installation

Clone the repository, ensure Python 3.10+ is available, and install module dependencies:

```bash
# From workspace root
pip install -r modules/consultation/requirements.txt
```

---

## 5. Dependencies

Listed in [`requirements.txt`](file:///c:/Users/Namita%20Krishnan%20U/OneDrive/Desktop/BharatRX/BharatRX/modules/consultation/requirements.txt):
- `pydantic>=2.0.0` — Data validation and schema enforcement
- `fastapi>=0.100.0` — REST API framework
- `uvicorn>=0.20.0` — ASGI web server
- `httpx>=0.24.0` — HTTP client for external LLM calls and API testing
- `pytest>=7.0.0` — Automated unit testing framework
- `python-dotenv>=1.0.0` — Safe environment variable management from `.env` files

---

## 6. How to Configure Gemini API

The engine supports Google Gemini models (`gemini-1.5-flash` by default).

### Method A: Using a `.env` File (Recommended)
1. In the root directory of the repository (`BharatRx/`), create a file named `.env`:
   ```bash
   # BharatRx/.env
   GEMINI_API_KEY=your_actual_gemini_api_key_here
   GEMINI_MODEL=gemini-1.5-flash
   ```
2. The module automatically loads this file at startup via `python-dotenv`.
3. **Security**: The `.env` file is already listed in `.gitignore` so your secrets will never be committed to Git.

### Method B: Using Shell Environment Variables
Alternatively, you can export the key directly in your terminal session:
```powershell
# Windows PowerShell
$env:GEMINI_API_KEY = "your_actual_gemini_api_key_here"

# Linux / macOS Bash
export GEMINI_API_KEY="your_actual_gemini_api_key_here"
```

---

## 7. Environment Variables

| Variable | Required | Default | Description |
| :--- | :--- | :--- | :--- |
| `GEMINI_API_KEY` | Optional | `""` | Google Gemini API key. If absent or invalid, the engine automatically falls back to `MockConsultationEngine`. Loaded automatically from `.env` or system environment. |
| `GEMINI_MODEL` | Optional | `"gemini-1.5-flash"` | Gemini model identifier to utilize. |

---

## 8. Mock Fallback Engine

If no `GEMINI_API_KEY` is provided, or if an API call fails (network interruption, quota exceeded, or timeout), the system seamlessly and deterministically falls back to [`MockConsultationEngine`](file:///c:/Users/Namita%20Krishnan%20U/OneDrive/Desktop/BharatRX/BharatRX/modules/consultation/mock_engine.py).

The mock engine supports adaptive 4-to-5 turn clinical consultation flows for:
1. **Headache**: Location & character -> Duration & onset -> Severity (1–10) -> Associated symptoms (nausea, photophobia) -> Medications & chronic history.
2. **Fever**: Duration & temperature reading -> Severity & pattern (chills) -> Associated symptoms (cough, ENT) -> Antipyretic medications & allergies.
3. **Stomach Pain**: Location & character -> Duration & severity -> Relation to food & bowel movements -> History of ulcers & NSAIDs.
4. **Skin Rash**: Location & appearance -> Duration & itching -> New exposures/detergents/medications -> Allergic history.
5. **General Complaints**: Structured adaptive questions covering duration, severity, associated symptoms, and medical background.

---

## 9. How to Run the API

### Option A: Standalone Uvicorn Server
```bash
uvicorn modules.consultation.api:app --host 0.0.0.0 --port 8000 --reload
```

### Option B: Interactive Swagger Documentation
Open your browser at:
```
http://localhost:8000/docs
```

---

## 10. Available Endpoints

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/consultation/message` | Processes a patient message and returns the next adaptive question. |
| `POST` | `/api/consultation/report` | Compiles and retrieves the structured consultation report for doctor review. |

---

## 11. Sample Requests

### 11.1 Message Endpoint (`POST /api/consultation/message`)
```json
{
  "session_id": "S001",
  "patient_id": "P001",
  "message": "I have had a throbbing headache since yesterday."
}
```

### 11.2 Report Endpoint (`POST /api/consultation/report`)
```json
{
  "session_id": "S001",
  "patient_id": "P001"
}
```

---

## 12. Sample Responses

### 12.1 Message Response (`200 OK`)
```json
{
  "session_id": "S001",
  "next_question": "Where exactly is the headache located (e.g., forehead, temples, one side), and how does it feel (throbbing, dull, or sharp)?",
  "conversation_complete": false,
  "urgency": "routine"
}
```

### 12.2 Report Response (`200 OK`)
```json
{
  "report_id": "R_P001_1726214500",
  "patient_id": "P001",
  "chief_complaint": "I have had a throbbing headache since yesterday.",
  "duration": "1 day",
  "severity": 6,
  "temperature": null,
  "associated_symptoms": ["nausea", "photophobia"],
  "medical_history": ["Hypertension"],
  "current_medications": [
    {
      "name": "Telmisartan",
      "dose": "40 mg",
      "frequency": "OD"
    }
  ],
  "allergies": [],
  "uploaded_image": "Not provided",
  "patient_description": "Patient presents with I have had a throbbing headache since yesterday. Onset duration: 1 day. Reported discomfort severity is 6 out of 10.",
  "ai_summary": "Pre-Consultation Clinical Intake:\n- Chief Complaint: I have had a throbbing headache since yesterday. (Duration: 1 day, Severity: 6/10, Temp: Not recorded)\n- Associated Symptoms: nausea, photophobia\n- Chronic Conditions: Hypertension\n- Active Medications: Telmisartan\n- Allergies: No known drug allergies reported\n- Triage Urgency: ROUTINE",
  "doctor_review_questions": [
    "Check for focal neurological deficits, pupillary reflexes, and cranial nerve signs.",
    "Verify current blood pressure reading.",
    "Inquire about visual aura, stress triggers, and family history of migraine."
  ],
  "urgency": "routine",
  "created_at": "2026-09-13T08:15:00.000000Z"
}
```

### 12.3 Error Response (`400 Bad Request` or `404 Not Found`)
```json
{
  "success": false,
  "error": {
    "code": "INVALID_REQUEST",
    "message": "Required field 'patient_id' is missing from the payload"
  }
}
```

---

## 13. How Vaishak Can Integrate ConsultationEngine

Vaishak can integrate this module in either of two straightforward ways:

### Method 1: Direct Python In-Memory Service (Recommended for Monolith)

```python
from modules.consultation.engine import ConsultationEngine

# 1. Initialize engine
engine = ConsultationEngine()

# 2. Start consultation when patient enters chat
response = engine.start_consultation(
    patient_id="P001",
    initial_message="I have a headache since yesterday"
)
print("Assistant asks:", response["next_question"])

# 3. Process subsequent turns
next_turn = engine.process_message(
    session_id=response["session_id"],
    patient_message="7 out of 10 in temples"
)

# 4. Attach image if patient uploads prescription or rash photo
engine.attach_image_reference(
    session_id=response["session_id"],
    image_reference="https://storage.bharatrx.in/uploads/rx_101.jpg"
)

# 5. Retrieve final report for doctor review
report = engine.get_consultation_report(session_id=response["session_id"])

# 6. Retrieve unified patient profile to pass to Sidharth's safety engine
patient_profile = engine.get_patient_profile(session_id=response["session_id"])
```

### Method 2: FastAPI Router Inclusion (Microservice or API Gateway)

```python
# In backend/main.py
from fastapi import FastAPI
from modules.consultation.api import router as consultation_router

app = FastAPI()
app.include_router(consultation_router)
```

---

## 14. Missing Data Rules Compliance

Per `docs/integration.md`:
- **Missing numeric values** (e.g. unmeasured temperature): `null`
- **Missing lists/arrays** (e.g. no associated symptoms): `[]`
- **Missing text** (e.g. unuploaded image): `"Not provided"`
- **Severity validation**: Integer between 1 and 10, or `null`.
- **Urgency validation**: Must be either `"routine"` or `"urgent"`.

---

## 15. Limitations & Future Scope

- **In-Memory Storage**: Current session state is stored in-memory for the 5-hour hackathon MVP. Persistent DB storage (PostgreSQL/Redis) can be wired by Vaishak in `backend/`.
- **Decision Support Only**: Does not provide medical diagnoses or drug recommendations.
- **Image Processing Boundary**: Attaches image URLs/references to sessions, but does not perform computer vision diagnosis (handled downstream by Keshav's RAG/OCR and the reviewing physician).
