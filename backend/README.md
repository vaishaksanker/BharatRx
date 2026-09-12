# BharatRx - Backend Module

## 👤 Module Owner
**Vaishak** (Fullstack & Lead Architect)

---

## 🎯 Module Overview
The `backend` module serves as the central server and orchestration layer for the BharatRx application. It manages data persistence, authentication, file processing queues, and coordinates workflows across the three core AI modules (`consultation`, `prescription_rag`, and `safety_engine`).

---

## 📥 Expected Inputs
- **HTTP Requests**: REST API calls from the frontend for auth, patient profiles, pre-consultation state, and doctor dashboard queries.
- **Multipart Data**: Image/PDF prescription uploads.
- **Internal Payload Routing**: Data objects exchanged between the three underlying AI modules.

---

## 📤 Expected Outputs
- **Structured JSON APIs**: Standardized response payloads for frontend components.
- **Database Records**: User accounts, consultation records, uploaded prescriptions, and generated safety reports.
- **Secure Auth Tokens**: JWT / session management tokens.

---

## 🔗 Integration with AI Modules
- **Consultation Module (`modules/consultation/`)**: Invokes consultation engine API to initiate intake sessions, process user answers, and retrieve structured clinical summary reports.
- **Prescription RAG Module (`modules/prescription_rag/`)**: Sends uploaded prescription documents for OCR extraction and RAG knowledge retrieval.
- **Safety Engine Module (`modules/safety_engine/`)**: Passes combined patient profile, active conditions, and extracted medications to trigger comprehensive safety risk analysis.
