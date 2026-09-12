# BharatRx - Frontend Module

## 👤 Module Owner
**Vaishak** (Fullstack & Lead Architect)

---

## 🎯 Module Overview
The `frontend` module provides the client-side user experience for the BharatRx platform. It includes responsive web interfaces tailored for two main user personas:
1. **Patient Interface**: Interactive pre-consultation chat application, symptom recorder, prescription image uploader, and patient safety report viewer.
2. **Doctor Clinical Dashboard**: Streamlined clinical decision support view showcasing AI-generated consultation summaries, prescription OCR extractions, and prioritized medication safety risk alerts.

---

## 📥 Expected Inputs
- **User Interactions**: Patient symptom responses, conversational inputs, and clinical history forms.
- **File Uploads**: High-resolution image/PDF uploads of physical prescriptions.
- **Doctor Actions**: Clinical review overrides, recommendation acknowledgments, and prescription verification.

---

## 📤 Expected Outputs
- Interactive UI rendering for pre-consultation conversations.
- Dynamic visual widgets for safety risk indicators (Low, Moderate, High severity alerts).
- Formatted clinical summary reports ready for physician review.
- Accessible patient guidance cards detailing medication schedules and precautions.

---

## 🔗 Integration with Main Backend
- Communicates via RESTful / WebSocket API endpoints hosted by the `backend` module.
- Handles user authentication state (JWT/Session tokens).
- Sends raw prescription images to backend storage endpoints and listens for asynchronous OCR/RAG & Safety engine analysis results.
