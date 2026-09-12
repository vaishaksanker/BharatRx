# Consultation AI Module (`modules/consultation/`)

## 👤 Module Owner
**Namita**

---

## 🎯 Module Overview
The `consultation` module powers the AI pre-consultation engine. It conducts adaptive, conversational intake with patients prior to their physician appointment. It systematically collects primary symptoms, duration, severity, vital signs, past medical history, known allergies, and current medications, generating a structured clinical consultation report for the physician.

---

## 🔑 Key Responsibilities
- AI-driven conversational dialogue management.
- Adaptive follow-up symptom probing based on medical intake logic.
- Comprehensive collection of:
  - Primary symptoms & onset duration
  - Severity indicators & progression
  - Vitals (blood pressure, temperature, heart rate, oxygen levels)
  - Medical history & chronic conditions
  - Known drug & food allergies
  - Current medications & supplements
- Generation of standardized clinical summary reports (SOAP note style).

---

## 📥 Expected Inputs
- **Conversational Messages**: Text/voice inputs from the patient during pre-consultation.
- **Initial Complaint / Chief Complaint**: Primary reason for consultation.
- **Patient Context**: Demographics, baseline profile (if available).

---

## 📤 Expected Outputs
- **Adaptive Questions**: Next conversational question tailored to previous answers.
- **Structured Consultation Report**: Standardized JSON/Markdown report containing categorized symptoms, history, allergies, and vitals for doctor review.

---

## 🔗 Integration with Main Backend
- Exposes a Python service / REST API consumed by `backend`.
- The backend orchestrates session lifecycle (Start Session -> Send Response -> Get Next Question -> Complete Session -> Retrieve Structured Summary Report).
