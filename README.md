# BharatRx

BharatRx is an India-focused AI-powered prescription safety and pre-consultation platform designed to help identify potential medication risks and prepare structured patient information for clinical review.

> **IMPORTANT DISCLAIMER**  
> BharatRx is designed strictly as a clinical decision-support and pre-consultation intelligence system. It **does NOT** autonomously diagnose, prescribe medication, or replace professional medical advice and evaluation from a qualified healthcare practitioner.

---

## 📌 Project Purpose

In healthcare settings across India, clinical consultations often face constraints of time and high patient volume. BharatRx aims to bridge critical clinical information gaps by providing:
1. **Intelligent Pre-Consultation**: Capturing patient symptoms, medical history, vitals, allergies, and active medications in an adaptive, conversational intake process prior to meeting the doctor.
2. **Prescription Extraction & RAG Knowledge Pipeline**: Extracting medication information from prescription images/documents and grounding it in trusted medical knowledge databases.
3. **Automated Medication Safety Engine**: Analyzing patient profiles against extracted prescriptions for drug-drug interactions, drug-disease contraindications, duplicate therapies, and allergen risks.

---

## 🏗️ High-Level Architecture

The BharatRx platform follows a modular architecture separating fullstack web services from core AI/ML domain modules:

```
[ Patient / Doctor UI (Frontend) ]
                │
                ▼
      [ Main Backend API ]
         │          │          │
         ▼          ▼          ▼
 ┌──────────────┐ ┌──────────────────┐ ┌────────────────┐
 │ Pre-Consult. │ │ Prescription RAG │ │ Safety Engine  │
 │   Module     │ │     Module       │ │     Module     │
 └──────────────┘ └──────────────────┘ └────────────────┘
```

1. **Frontend**: React-based patient interface and clinical doctor dashboard.
2. **Backend**: Node.js/Python API server managing user sessions, database storage, file uploads, and orchestrating requests across AI modules.
3. **AI Modules**:
   - **Consultation Engine**: Adaptive patient symptom gathering and clinical summary generation.
   - **Prescription RAG**: OCR/Extraction and knowledge retrieve-and-generate pipeline for drug info.
   - **Safety Engine**: Algorithmic rules and severity scoring for patient safety checks.

---

## 👥 Team Responsibilities

BharatRx is built as a multi-developer project with clear module ownership:

| Teammate | Primary Area | Key Responsibilities |
| :--- | :--- | :--- |
| **Keshav** | `modules/prescription_rag/` | Medical knowledge base, prescription OCR & data extraction, medicine information lookup, drug interactions DB, contraindications, adverse effects knowledge, RAG pipeline. |
| **Sidharth** | `modules/safety_engine/` | Patient-specific medication safety analysis, drug-drug interaction matching, drug-disease contraindication evaluation, allergy checking, duplicate therapy detection, risk severity calculation & scoring, safety API. |
| **Namita** | `modules/consultation/` | AI pre-consultation engine, patient symptom conversation, adaptive follow-up questions, structured data collection (symptoms, duration, severity, vitals, history, allergies, medications), clinical report generation. |
| **Vaishak** | `frontend/` & `backend/` | Main application frontend & backend, database schema & ORM, user authentication, patient UI & doctor dashboard, image storage, API routing, integration of consultation, RAG, and safety modules. |

---

## 📁 Folder Structure

```
BharatRx/
│
├── frontend/
│   └── README.md             # React/Vite Frontend (Owner: Vaishak)
│
├── backend/
│   └── README.md             # Node.js/Python API Backend (Owner: Vaishak)
│
├── modules/
│   │
│   ├── consultation/
│   │   └── README.md         # Pre-Consultation AI Engine (Owner: Namita)
│   │
│   ├── prescription_rag/
│   │   └── README.md         # OCR & Prescription RAG Pipeline (Owner: Keshav)
│   │
│   └── safety_engine/
│       └── README.md         # Patient Safety & Risk Engine (Owner: Sidharth)
│
├── data/
│   ├── medical/
│   │   └── README.md         # Reference medical DBs & knowledge schemas
│   │
│   └── demo/
│       └── README.md         # Synthetic demo patient profiles & test data
│
├── docs/
│   └── README.md             # Architecture docs, API specs & team guides
│
├── .gitignore                # Global Git ignore rules
└── README.md                 # Root project documentation
```

---

## 🔄 Planned Module Integration Flow

```
1. Patient Intake  ---> [Consultation Module] ---> Generates Structured Summary Report
2. Prescription    ---> [Prescription RAG]   ---> Extracts Medications & Drug Knowledge
3. Safety Audit    ---> [Safety Engine]       ---> Evaluates Summary + Meds for Interaction & Risk Scores
4. Clinical View   ---> [Backend -> Frontend] ---> Displays Warnings & Clinical Insights on Doctor Dashboard
```

1. **Pre-Consultation Flow**: Patient engages with the `consultation` module to record symptoms, history, and vitals. A structured summary report is produced.
2. **Prescription Processing**: Patient or doctor uploads a prescription. The `prescription_rag` module performs OCR, extracts drug names, dosages, and fetches medical references.
3. **Safety Engine Evaluation**: The `backend` passes the extracted prescription data along with patient history (allergies, conditions) to the `safety_engine` module.
4. **Unified Presentation**: The backend consolidates the consultation summary, prescription insights, and safety risk alerts to render on the `frontend` doctor dashboard.

---

## 🚀 Development & Git Workflow

### Branch Strategy

To ensure parallel development without conflict, each team member works on their dedicated feature branch:

- `main` : Production-ready code. All PRs require review before merging.
- `feature/keshav-rag` : RAG pipeline and prescription OCR development (`modules/prescription_rag/`).
- `feature/sidharth-safety` : Safety analysis engine development (`modules/safety_engine/`).
- `feature/namita-consultation` : Pre-consultation chatbot & report generator (`modules/consultation/`).
- `feature/vaishak-fullstack` : Frontend, backend, database, and system integration (`frontend/`, `backend/`).

### Recommended Git Commands for Teammates

1. **Clone repository**:
   ```bash
   git clone <repository-url>
   cd BharatRx
   ```
2. **Create and switch to your feature branch**:
   ```bash
   # Example for Keshav
   git checkout -b feature/keshav-rag
   ```
3. **Push changes to your feature branch**:
   ```bash
   git add .
   git commit -m "feat(rag): initial knowledge base setup"
   git push -u origin feature/keshav-rag
   ```
4. **Merge Process**: Open a Pull Request (PR) from your feature branch to `main` for code review.
