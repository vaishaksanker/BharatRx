# BharatRx Integration Contract

> **Document Status**: Active Shared Contract  
> **Target Scope**: 5-Hour Hackathon MVP  
> **Core Objective**: Provide a practical, standardized, and language-agnostic interface specification enabling independent module development and seamless backend integration.

---

## 1. System Architecture & Information Flow

The BharatRx system processes clinical information sequentially, transitioning from patient symptom intake to clinical risk evaluation on the doctor's dashboard:

```
                  ┌──────────────────────────────┐
                  │           Patient            │
                  └──────────────┬───────────────┘
                                 │
                                 ▼
                  ┌──────────────────────────────┐
                  │    AI Pre-Consultation       │  (Namita)
                  └──────────────┬───────────────┘
                                 │
                                 ▼
                  ┌──────────────────────────────┐
                  │Structured Consultation Report│
                  └──────────────┬───────────────┘
                                 │
                                 ▼
                  ┌──────────────────────────────┐
                  │        Doctor Review         │
                  └──────────────┬───────────────┘
                                 │
                                 ▼
                  ┌──────────────────────────────┐
                  │         Prescription         │
                  └──────────────┬───────────────┘
                                 │
                                 ▼
                  ┌──────────────────────────────┐
                  │Prescription Processing / RAG │  (Keshav)
                  └──────────────┬───────────────┘
                                 │
                                 ▼
                  ┌──────────────────────────────┐
                  │   Medication Safety Engine   │  (Sidharth)
                  └──────────────┬───────────────┘
                                 │
                                 ▼
                  ┌──────────────────────────────┐
                  │        Risk Analysis         │
                  └──────────────┬───────────────┘
                                 │
                                 ▼
                  ┌──────────────────────────────┐
                  │       Doctor Dashboard       │  (Vaishak)
                  └──────────────────────────────┘
```

---

## 2. Integration Principles

1. **JSON Data Standard**: All external and internal API interactions must use valid JSON payloads over HTTP REST endpoints or direct in-memory function calls.
2. **Decoupled Architecture**: Teammate modules (`consultation`, `prescription_rag`, `safety_engine`) must never directly import or rely on the internal execution logic or private functions of other modules.
3. **Backend API Gateway**: The main `backend` module (owned by Vaishak) acts as the central integration layer and API gateway.
4. **Interface Stability**: Module owners may modify internal algorithms, prompts, or model parameters freely as long as the external JSON payload schema defined in this contract remains intact.
5. **Zero Secrets in Payloads**: Never transmit API keys, secrets, database tokens, or private credentials within request or response bodies.
6. **Synthetic Demo Data**: Use synthetic, mock patient data for hackathon demonstrations.
7. **Decision Support Boundaries**: BharatRx is explicitly an AI clinical decision-support tool. It **does not** autonomously diagnose conditions or prescribe medications.
8. **Physician Ownership**: The qualified doctor retains full final clinical authority over all diagnoses, treatment plans, and safety alert dismissals.

---

## 3. Common Patient Schema

The `Patient` object is the unified data representation passed between the backend, consultation report, and safety engine.

```json
{
  "patient_id": "P001",
  "name": "Demo Patient",
  "age": 65,
  "sex": "M",
  "conditions": ["CKD"],
  "allergies": ["Penicillin"],
  "current_medications": [
    {
      "name": "Warfarin",
      "dose": "5 mg",
      "frequency": "OD"
    }
  ]
}
```

### Schema Field Specification

| Field Name | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `patient_id` | String | **Yes** | Unique identifier for the patient session or profile (e.g., `"P001"`). |
| `name` | String | Optional | Patient's display name or alias. |
| `age` | Integer | **Yes** | Patient's age in years (used for age-dependent safety checks). |
| `sex` | String | **Yes** | Patient's biological sex (`"M"`, `"F"`, `"Other"`). |
| `conditions` | Array of Strings | **Yes** | Documented clinical diagnoses or chronic conditions (e.g., `["CKD", "Hypertension"]`). Empty array if none. |
| `allergies` | Array of Strings | **Yes** | Known drug or substance allergies (e.g., `["Penicillin", "Sulfa"]`). Empty array if none. |
| `current_medications` | Array of Objects | **Yes** | Active ongoing prescriptions. Each item requires `name` (String), `dose` (String), and `frequency` (String). Empty array if none. |

*Note: Real-world sensitive identifiers (Aadhaar, exact address, phone numbers) are intentionally omitted for the MVP to protect patient privacy.*

---

## 4. Consultation API (Namita)

### 4.1 Interactive Message Endpoint

**Endpoint**: `POST /api/consultation/message`

#### Request Payload
```json
{
  "session_id": "S001",
  "patient_id": "P001",
  "message": "I have had a headache since yesterday."
}
```

#### Response Payload
```json
{
  "session_id": "S001",
  "next_question": "Where exactly is the headache located?",
  "conversation_complete": false,
  "urgency": "routine"
}
```

### 4.2 Structured Report Endpoint

**Endpoint**: `POST /api/consultation/report`

#### Request Payload
```json
{
  "session_id": "S001",
  "patient_id": "P001"
}
```

#### Response Payload
```json
{
  "report_id": "R001",
  "patient_id": "P001",
  "chief_complaint": "Headache",
  "duration": "1 day",
  "severity": 6,
  "temperature": null,
  "associated_symptoms": [],
  "medical_history": [],
  "current_medications": [],
  "allergies": [],
  "patient_description": "Patient reports a moderate headache originating 1 day ago.",
  "ai_summary": "65yo male presenting with 1-day onset headache, severity 6/10.",
  "doctor_review_questions": [
    "Check for neurological signs",
    "Verify blood pressure reading"
  ],
  "urgency": "routine"
}
```

#### Data Formatting Rules for Missing Data:
- Missing numeric values (e.g., unmeasured temperature): `null`
- Missing lists (e.g., no associated symptoms reported): `[]`
- Missing text descriptions: `"Not provided"`

---

## 5. Prescription Processing / RAG API (Keshav)

### 5.1 Prescription Text Extraction Endpoint

**Endpoint**: `POST /api/prescription/analyze`

#### Request Payload
```json
{
  "prescription_text": "Warfarin 5mg OD\nIbuprofen 400mg BD"
}
```

#### Response Payload
```json
{
  "prescription_id": "RX001",
  "medications": [
    {
      "name": "Warfarin",
      "normalized_name": "warfarin",
      "dose": "5 mg",
      "frequency": "OD"
    },
    {
      "name": "Ibuprofen",
      "normalized_name": "ibuprofen",
      "dose": "400 mg",
      "frequency": "BD"
    }
  ]
}
```

### 5.2 RAG Knowledge Retrieval Payload (Internal / Sub-Module Contract)

Format provided by the RAG knowledge module to feed the Safety Engine:

```json
{
  "medicine": "ibuprofen",
  "knowledge": {
    "interactions": [
      {
        "interacting_drug": "warfarin",
        "effect": "Increased risk of severe gastrointestinal bleeding",
        "severity": "HIGH"
      }
    ],
    "contraindications": [
      {
        "condition": "CKD",
        "reason": "NSAIDs reduce renal blood flow and worsen renal impairment",
        "severity": "HIGH"
      }
    ],
    "allergy_information": [
      "Cross-sensitivity with aspirin and other NSAIDs"
    ],
    "adverse_effects": [
      "Gastric ulceration",
      "Renal toxicity"
    ],
    "special_population_risks": [
      "Elderly (>65 years): Elevated bleeding and renal risk"
    ]
  },
  "sources": [
    "CDSCO Approved Drug Data",
    "OpenFDA Reference Knowledge Base"
  ]
}
```

*Rule: The RAG system must return citation sources (`sources`) for all retrieved clinical insights.*

---

## 6. Safety Engine API (Sidharth)

### 6.1 Patient Safety Analysis Endpoint

**Endpoint**: `POST /api/safety/analyze`

#### Request Payload
```json
{
  "patient": {
    "patient_id": "P001",
    "age": 65,
    "conditions": ["CKD"],
    "allergies": ["Penicillin"],
    "current_medications": [
      {
        "name": "Warfarin",
        "dose": "5 mg",
        "frequency": "OD"
      }
    ]
  },
  "prescription": [
    {
      "name": "Ibuprofen",
      "dose": "400 mg",
      "frequency": "BD"
    },
    {
      "name": "Amoxicillin",
      "dose": "500 mg",
      "frequency": "TDS"
    }
  ]
}
```

#### Response Payload
```json
{
  "analysis_id": "A001",
  "overall_risk": "HIGH",
  "alerts": [
    {
      "type": "DRUG_DRUG",
      "severity": "HIGH",
      "medicine": "Ibuprofen",
      "related_drug": "Warfarin",
      "reason": "Potential increased bleeding risk due to concomitant NSAID and anticoagulant therapy"
    },
    {
      "type": "DRUG_DISEASE",
      "severity": "HIGH",
      "medicine": "Ibuprofen",
      "condition": "CKD",
      "reason": "Potential renal safety concern; NSAIDs impair renal blood flow in pre-existing CKD"
    },
    {
      "type": "ALLERGY",
      "severity": "HIGH",
      "medicine": "Amoxicillin",
      "related_to": "Penicillin",
      "reason": "Potential allergy concern; Amoxicillin is a penicillin-class antibiotic"
    }
  ]
}
```

### 6.2 Permitted Values & Enum Constraints

#### Allowed Risk Levels (`overall_risk` and `severity`)
- `LOW`
- `MEDIUM`
- `HIGH`
- `CRITICAL`

#### Allowed Alert Types (`type`)
- `DRUG_DRUG`
- `DRUG_DISEASE`
- `ALLERGY`
- `DUPLICATE_THERAPY`
- `PATIENT_FACTOR`
- `DOSE_CONCERN`
- `OTHER`

---

## 7. End-to-End Integration Scenario Example

### Scenario Overview
- **Patient**: 65-year-old male with Chronic Kidney Disease (CKD).
- **Active Medication**: Warfarin (5 mg OD).
- **Known Allergy**: Penicillin.
- **New Prescription Submitted**: Ibuprofen (400 mg BD) and Amoxicillin (500 mg TDS).

### Step-by-Step Flow Execution

1. **Pre-Consultation Intake**: Patient completes intake via `modules/consultation/`. Namita's module generates the patient profile JSON (`P001`) with age 65, condition `"CKD"`, allergy `"Penicillin"`, and medication `"Warfarin"`.
2. **Prescription Submission**: The new prescription document containing Ibuprofen and Amoxicillin is uploaded through Vaishak's `frontend` and passed to the `backend`.
3. **OCR & Extraction**: The `backend` calls Keshav's `modules/prescription_rag/` via `POST /api/prescription/analyze`. Keshav's extraction normalizes the list to `["ibuprofen", "amoxicillin"]`.
4. **RAG Knowledge Lookup**: Keshav's RAG component fetches medical knowledge for Ibuprofen (DDI with Warfarin, Contraindication in CKD) and Amoxicillin (Beta-lactam penicillin class).
5. **Safety Evaluation**: Vaishak's `backend` invokes Sidharth's `modules/safety_engine/` via `POST /api/safety/analyze`, supplying the combined `patient` object and `prescription` list.
6. **Alert Generation**: The `safety_engine` identifies three high-severity risks (`DRUG_DRUG` for Ibuprofen+Warfarin, `DRUG_DISEASE` for Ibuprofen+CKD, and `ALLERGY` for Amoxicillin+Penicillin) and assigns an `overall_risk` score of `"HIGH"`.
7. **Backend Dispatch**: The `backend` consolidates the structured consultation report, prescription extractions, and safety alerts into a unified dashboard API payload.
8. **Doctor Review & Action**: Vaishak's `frontend` renders high-priority warning cards on the Doctor Dashboard. The reviewing physician reviews the alerts, cancels Ibuprofen/Amoxicillin, and prescribes safe clinical alternatives.

---

## 8. Common Error Response Format

All backend and module endpoints must adopt this standardized error structure in non-200 scenarios:

```json
{
  "success": false,
  "error": {
    "code": "INVALID_REQUEST",
    "message": "Required field 'patient_id' is missing from the payload"
  }
}
```

### Standardized Error Codes

| Error Code | HTTP Status | Description |
| :--- | :--- | :--- |
| `INVALID_REQUEST` | 400 Bad Request | Payload validation failure or missing required fields. |
| `PATIENT_NOT_FOUND` | 404 Not Found | Specified `patient_id` does not exist in the session database. |
| `INVALID_MEDICATION` | 422 Unprocessable | Medication name cannot be parsed or normalized by OCR/RAG. |
| `MODULE_ERROR` | 500 Internal Error | Execution failure inside an underlying Python/Node module. |
| `AI_SERVICE_ERROR` | 503 Service Unavailable | Upstream LLM or OCR API rate-limit/timeout. |
| `INTERNAL_ERROR` | 500 Internal Error | Unexpected gateway or database failure. |

---

## 9. Teammate Module Responsibilities Matrix

| Module | Owner | Input | Output | Core Question Answered |
| :--- | :--- | :--- | :--- | :--- |
| `modules/prescription_rag/` | **Keshav** | Raw prescription image or text | Normalized medication JSON & reference medical knowledge | *"What does the medical knowledge say?"* |
| `modules/safety_engine/` | **Sidharth** | Patient profile + Extracted prescription list | Safety risk report & alert badges (`LOW`-`CRITICAL`) | *"What of that knowledge applies to THIS patient?"* |
| `modules/consultation/` | **Namita** | Patient chat messages | Structured consultation report & urgency classification | *"What information should we collect from the patient and how should it be structured for the doctor?"* |
| `frontend/` & `backend/` | **Vaishak** | User UI inputs & API events | Integrated Web app, database records & doctor dashboard | *"How do we connect everything into one usable application?"* |

---

## 10. Hackathon MVP Scope vs. Future Roadmap

### 5-Hour Hackathon MVP Scope
- ✅ Synthetic patient profiles (Pre-loaded JSON test cases).
- ✅ Basic session authentication.
- ✅ AI pre-consultation chat interface.
- ✅ Structured consultation report generator (SOAP format).
- ✅ Prescription text/image upload and basic OCR extraction.
- ✅ Curated medical knowledge base (10-15 key medications).
- ✅ Basic RAG query prototype.
- ✅ Rule-based Safety Engine covering 5–10 high-confidence interactions & contraindications.
- ✅ Risk severity scoring (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`).
- ✅ Doctor Dashboard displaying patient report and safety alerts.
- ✅ End-to-end working demonstration flow.

### Future Production Roadmap (Post-Hackathon)
- 🚀 ABDM / ABHA ID integration with consent management framework.
- 🚀 Real clinical patient record integration (FHIR standards).
- 🚀 Comprehensive drug database (RxNorm, CDSCO, 100,000+ formulations).
- 🚀 AYUSH (Ayurvedic, Unani, Siddha, Homeopathic) drug interaction database.
- 🚀 Automated national pharmacovigilance reporting integration.
- 🚀 Specialist doctor marketplace and e-prescription signing.
- 🚀 Computer-vision handwritten prescription parsing model.
- 🚀 Live hospital EMR/HIS API connectors.

---

## 11. Development & Git Rules

1. **Feature Branch Isolation**: Teammates work strictly within their assigned feature branches:
   - Keshav: `feature/keshav-rag`
   - Sidharth: `feature/sidharth-safety`
   - Namita: `feature/namita-consultation`
   - Vaishak: `feature/vaishak-fullstack`
2. **No Direct Main Commits**: Do not push unreviewed feature commits directly to `main`.
3. **Pull Before Integration**: Run `git pull origin main` into your feature branch before initiating major integration testing.
4. **Pull Requests (PR)**: Submit PRs into `main` for integration.
5. **Respect Ownership**: Avoid modifying code files in another teammate's directory without prior coordination.
6. **Clean Commits**: Write clear, descriptive commit messages (e.g., `feat(safety): add drug-disease contraindication rule`).
7. **Secrets Prevention**: **NEVER** commit `.env` files, API keys, passwords, bearer tokens, or real patient health data.

---

## 12. Definition of Done (DoD)

The BharatRx hackathon integration is complete and verified when:

1. A patient can complete a pre-consultation chat session with Namita's `consultation` module.
2. A structured consultation summary report is automatically generated and delivered to Vaishak's `backend`.
3. The reviewing doctor can view the consultation report on Vaishak's `frontend` dashboard.
4. A prescription image/text is uploaded to the backend and parsed by Keshav's `prescription_rag` module.
5. Extracted medicines are processed by Sidharth's `safety_engine` against the patient's history and active conditions.
6. Calculated risk alerts (`DRUG_DRUG`, `DRUG_DISEASE`, `ALLERGY`) are prominently displayed on the Doctor Dashboard.
