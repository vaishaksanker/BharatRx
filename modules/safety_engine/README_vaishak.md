# Safety Engine Module (`modules/safety_engine/`)

## 👤 Module Owner
**Sidharth**

---

## 🎯 Module Overview
The `safety_engine` module is the core clinical risk analysis component of BharatRx. It performs algorithmic, patient-specific medication safety checks by cross-referencing extracted prescriptions against patient medical history, active conditions, known allergies, and current medications.

---

## 🔑 Key Responsibilities
- **Drug-Drug Interaction (DDI) Matching**: Identifying dangerous or interfering drug combinations.
- **Drug-Disease Contraindication Analysis**: Checking prescribed drugs against patient pre-existing conditions (e.g., NSAIDs in renal failure).
- **Allergy Checking**: Verifying prescribed compounds against patient-documented drug allergies and cross-reactivities.
- **Duplicate Therapy Detection**: Alerting on multiple prescribed medications belonging to the same therapeutic class.
- **Risk Severity Scoring**: Calculating quantitative risk scores and categorizing severity levels (Low, Moderate, High, Severe/Critical).
- **Safety Analysis API**: Exposing programmatic evaluation endpoints.

---

## 📥 Expected Inputs
- **Extracted Medications**: List of drugs (names, dosages, active ingredients) provided by `prescription_rag`.
- **Patient Profile Data**: Documented allergies, chronic diseases/diagnoses, past medical history, and existing medications provided by `consultation` or patient records.

---

## 📤 Expected Outputs
- **Safety Analysis Report**: Detailed breakdown of identified interactions, contraindications, allergy risks, and duplicate therapies.
- **Severity Scores & Badges**: Overall numerical risk score and categorized flags for rapid clinical review on the doctor dashboard.

---

## 🔗 Integration with Main Backend
- Exposes a dedicated Safety Analysis API endpoint.
- Called by `backend` whenever a new prescription or patient profile is submitted or modified.
