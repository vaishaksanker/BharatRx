# Prescription RAG Module (`modules/prescription_rag/`)

## 👤 Module Owner
**Keshav**

---

## 🎯 Module Overview
The `prescription_rag` module provides intelligent Optical Character Recognition (OCR) and Retrieval-Augmented Generation (RAG) capabilities. It processes physical prescription images or text documents, extracts prescribed drugs, dosages, and instructions, and retrieves verified medical knowledge regarding drug properties, interactions, contraindications, and adverse effects.

---

## 🔑 Key Responsibilities
- **Prescription OCR & Extraction**: Parsing digital and handwritten prescription images to extract drug names, strengths, dosages, frequency, and duration.
- **Medical Knowledge Base Integration**: Indexing clinical reference datasets (drug databases, pharmacological indices).
- **RAG Pipeline**: Vector embeddings and semantic search pipeline to retrieve contextually accurate drug knowledge.
- **Pharmacological Detail Retrieval**: Fetching side effects, mechanism of action, black-box warnings, and standard usage guidelines.

---

## 📥 Expected Inputs
- **Prescription Documents**: Image files (JPEG, PNG) or PDFs of prescriptions.
- **Query Terms**: Specific medicine names or active ingredients requested for lookup.

---

## 📤 Expected Outputs
- **Extracted Prescription Data**: Structured JSON object containing parsed medication list, dosages, frequencies, and administration instructions.
- **Medical Reference Context**: Pharmacological facts, contraindications, and interaction reference data grounded in verified medical sources.

---

## 🔗 Integration with Main Backend
- Exposes a service API for OCR ingestion and RAG querying.
- Called by `backend` upon file upload to receive structured medication lists, which are then passed to `modules/safety_engine/`.
