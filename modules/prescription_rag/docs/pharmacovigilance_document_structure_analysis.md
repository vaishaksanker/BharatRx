# Pharmacovigilance Document Structure Analysis

> **Purpose:** Pre-implementation structural analysis of all CDSCO Pharmacovigilance PDFs in the BharatRx dataset.
> **Date:** 2026-09-13
> **Analyst:** Kiro (automated PDF inspection using PyMuPDF 1.x + pdfplumber 0.11.0)
> **Status:** Analysis only — no chunking, embeddings, or vector DB created.
> **Constraint:** Read-only. No files modified.

---

## 1. Dataset Inventory

| File | Pages | Size (bytes) | SHA-256 | Type | Text Extractable | OCR Required |
|------|-------|-------------|---------|------|-----------------|--------------|
| `17RecallRapid.pdf` | 22 | 521,341 | `4c6adb26d47b…` | Recall/Rapid Alert Guideline | ✅ Yes | ❌ No |
| `Guidance_Documentpsur2.pdf` | 86 | 5,886,144 | `9142de7460f7…` | PSUR Guidance Document | ✅ Yes | ❌ No |
| `List of New Drugs approved in the year 2025.pdf` | 1 | 186,419 | `e44d18fd047d…` | New Drug Approval List | ✅ Yes | ❌ No |
| `Pv Guidancedoc24.pdf` | 116 | 7,116,125 | `91750e24b4f9…` | PV Guidance (Vaccines) | ✅ Yes | ❌ No |
| `Pv Guidancedoc24 on vaccines 2.0.pdf` | 116 | 7,116,125 | `91750e24b4f9…` | **EXACT DUPLICATE** of above | ✅ Yes | ❌ No |

Full SHA-256 values:
- `17RecallRapid.pdf`: `4c6adb26d47b29250f3816cd4129725456e0fbe19fbf99fcd0c5cafe8d6af4ed`
- `Guidance_Documentpsur2.pdf`: `9142de7460f75d5c52a4c7baa49416883f751b738ce39263f6cc84834eb3f09d`
- `List of New Drugs approved in the year 2025.pdf`: `e44d18fd047d5f28bfb9ea6b26122e97e5fe04468d6939202d4fd9f53fa09564`
- `Pv Guidancedoc24.pdf`: `91750e24b4f99c15c88a66315e6ab5a6181ae138cb80c5c7a50ea398ed626223`
- `Pv Guidancedoc24 on vaccines 2.0.pdf`: `91750e24b4f99c15c88a66315e6ab5a6181ae138cb80c5c7a50ea398ed626223`

**Effective unique documents: 4** (the two `Pv Guidancedoc24` files are byte-for-byte identical).

---

## 2. Document Classification

### `17RecallRapid.pdf` — Recall and Rapid Alert System Guideline
- **Classification:** Recall/Rapid Alert Guideline
- **Why:** Cover page reads "GUIDELINES ON RECALL AND RAPID ALERT SYSTEM FOR DRUGS (Including Biologicals & Vaccines)". Page 2 shows Document No: `CDSCO/RRAS Ver. 00`, Effective Date: `23/11/2012`, VERSION: `2017`. 22 pages. Sections 1.0–15.0. Standard CDSCO procedural document.
- **Content:** Defines recall classification (Class I/II/III), voluntary and statutory recall procedures, timelines, mock recall procedures, abbreviations, and references. Ends with SOP-style subsections (3.1–5.5) and annexure/format pages.

### `Guidance_Documentpsur2.pdf` — PSUR Guidance for MAHs
- **Classification:** PSUR Guidance Document
- **Why:** Cover page reads "Pharmacovigilance Guidance Document for Marketing Authorization Holders of Pharmaceutical Products, Version: 2.0". Published by NCC-PvPI / IPC / CDSCO. 86 pages. Structure uses "Chapter - N" organization with numbered subsections (1.0, 1.1, 1.2.1, etc.).
- **Content:** Guidance for Marketing Authorization Holders on Pharmacovigilance System Master File (PSMF), ICSR collection/reporting, PSUR preparation, QMS, audits, risk management plans. Has Appendices A–E.

### `List of New Drugs approved in the year 2025.pdf` — New Drug Approval List
- **Classification:** New Drug Approval List
- **Why:** Title "List of New Drugs approved in the year 2025 till date". 1 page. Contains a 4-column table: S.No. / Name of New Drug / Indication / Date of Approval. 3 drug entries extracted. Identical structure to FDC new drug lists already chunked.

### `Pv Guidancedoc24.pdf` — Pharmacovigilance Guidance for Vaccine MAHs
- **Classification:** PV Guidance Document (Vaccines)
- **Why:** 116-page guidance document. PREFACE + FOREWORD on pages 4–5. Table of contents on page 6. Body starts with "1. INTRODUCTION" on page 9. Structure uses `N.` (top-level: `1.`, `2.`, `3.`, `4.`) and dotted subsections (`2.2`, `2.2.1`, `4.1.3.2.1`, etc.). Full 4-level nesting confirmed.
- **Content:** PV for vaccines — roles of CDSCO, NCC-PvPI, Immunization Division; AEFI reporting; signal detection; PSUR; ICSR; Risk Management Plan; QMS.

### `Pv Guidancedoc24 on vaccines 2.0.pdf` — EXACT DUPLICATE
- **Classification:** Duplicate (do not index)
- **Why:** SHA-256 hash `91750e24b4f99c15c88a66315e6ab5a6181ae138cb80c5c7a50ea398ed626223` is identical to `Pv Guidancedoc24.pdf`. Same file size (7,116,125 bytes) and page count (116). Different filename only. Indexing both would double every chunk from this document in the vector store.

---

## 3. Reading Order Analysis

### PyMuPDF `page.get_text("text")` quality — verdict per document

**`17RecallRapid.pdf`** ✅ Single-column, clean
- Column detection: page 2 shows `x0_buckets: [100, 200]` (two margin values, not two text columns — this is the decorative border + main text).
- Page 5 and beyond: single column confirmed `x0_buckets: [50]`.
- Text is fully readable. Headings (sz=16.0, bold) are clearly separated from body (sz=10.0).
- Header/footer: "Central Drugs stanDarD Control organization" (mixed case decorative font) appears on multiple pages as a header strip — it is a page header, not content. Must be filtered.
- Page numbers appear as bare integers (`2`, `3`, etc.) in the running header — must be filtered.
- Mixed-case heading font (`introDuCtion`, `BaCkgrounD`, `sCoPe`) is purely cosmetic; the text content is correct and parseable by regex on the numbering pattern.
- **Conclusion:** Normal `page.get_text("text")` is sufficient. No coordinate ordering needed.

**`Guidance_Documentpsur2.pdf`** ✅ Single-column, clean
- Column detection: single column throughout (`x0_buckets: [50]`).
- Avg 1,536 chars/page over 86 pages. Some pages have low char counts (pp. 84–85: 0 chars each, pp. 53, 59, 65, 69–71: very low) — these are full-page figures/flow diagrams with no extractable text. They are interspersed through the document and must be treated as skipped pages, not section boundaries.
- Heading detection: section headings use a consistent pattern — chapter-level headings use large bold font (sz ≈ 19–20), section headings use sz=16.0 (larger than body sz≈11), subsection headings use sz=11.0 bold. All use decimal numbering (`1.0`, `1.1`, `1.2.1`, `1.2.2.1`).
- Page headers: repeated "CHAPTER - N" banners at top of each page — these are running headers, not unique content.
- Page numbers appear as isolated large-font numerals (`8`, `9`, `10`, etc.) — must be filtered.
- **Conclusion:** Normal `page.get_text("text")` is sufficient. Page headers and page-number spans need filtering.

**`Pv Guidancedoc24.pdf`** ✅ Single-column, clean
- Column detection: single column throughout.
- Avg 1,592 chars/page over 116 pages. Pages 1–3: near-zero chars (cover pages with embedded images). Pages 113–116: very low (trailing pages).
- Heading structure: uses `N.` for top-level (`1.`, `2.`, `3.`, `4.`), then `N.N` for level 2 (`2.2`, `3.2`, `4.1`), then `N.N.N` for level 3 (`2.2.1`, `4.1.3`), then `N.N.N.N` for level 4 (`4.1.3.2.1`, `4.2.2.3.1`). Body font ≈ 12.5–12.8 pt; section headings are bold + larger.
- False positives in heading detection: lines like `"1940 and Rules made thereunder..."`, `"2019. This Pharmacovigilance..."`, and table cell values containing years (`14 weeks`, `1 year of age`) were picked up because they start with a number. The heading regex must require that the trailing text be ≥ 3 meaningful words, not just a sentence fragment.
- **Conclusion:** Normal `page.get_text("text")` is sufficient, but heading detection regex must be tighter (see §4).

**`List of New Drugs approved in the year 2025.pdf`** ✅ Single-page table, clean
- pdfplumber correctly extracts a 4-row × 4-column table. No reading-order issues. This document needs no special handling.

---

## 4. Heading Hierarchy

### `17RecallRapid.pdf` — actual heading patterns

```
Document level: "GUIDELINES ON RECALL AND RAPID ALERT SYSTEM FOR DRUGS"  [sz=59, bold]

Section level (sz=16, bold, numbered):
  1.0 introDuCtion:          (page 4)
  2.0 BaCkgrounD:            (page 4)
  3.0 sCoPe:                 (page 4)
  4.0 DeFinitions:           (page 4)
  5.0 reCall ClassiFiCation: (page 5)
  6.0 reCall ProCeDures:     (page 5)
  7.0 leVels oF reCall:      (page 6)
  8.0 tiMe lines…:           (page 7)
  9.0 ProCeDure For raPiD…:  (page 7)
  10.0 oVerVieW…:            (page 8)
  11.0 stePWise reCall…:     (page 9)
  12.0 FolloW-uP aCtion…:    (page 9)
  13.0 MoCk reCall:          (page 10)
  14.0 aBBreViations          (not extracted as section heading — appears as SOP section)
  15.0 reFerenCes             (same)

Subsection level (sz=12, bold, numbered):
  6.1 VoluntarY reCall:      (page 5)
  6.2 statutorY reCall:      (page 6)

SOP-style (appended from page 11 onwards — appears to be a separate SOP document):
  1.0 PurPose   (page 11)
  2.0 sCoPe     (page 11)
  3.0 resPonsiBilitY  (page 11)
  3.1 – 3.4 subsections (page 11)
  4.0 aCCountaBilitY  (page 12)
  5.0 ProCeDure       (page 12)
  5.1 – 5.5 subsections
  6.0 annexure / ForMat (page 13)
  7.0 reFerenCes  (page 14)
  8.0 aBBreViation (page 14)
  9.0 reVision historY (page 14)
```

**Important structural observation:** The document has TWO distinct parts:
1. **Pages 1–15:** The main Recall & Rapid Alert System guideline (sections 1.0–15.0).
2. **Pages 11–22:** An embedded SOP document (sections 1.0–9.0) appended to the same PDF. Section numbering RESTARTS at 1.0 on page 11. Pages 16–22 contain annexure forms (letters, notification formats) with header "Central Drugs Standard Control Organization" but no section numbers — these are forms/templates, not prose content.

The heading numbering pattern is `N.N` decimal dot notation, mixed-case cosmetic font. Reliable detection: `^\d+\.\d*\s+` with sz ≥ 12 and bold flag.

### `Guidance_Documentpsur2.pdf` — actual heading patterns

```
Pre-chapter front matter:
  DISCLAIMER      [sz=20, bold, page 5]
  PREFACE         [sz=20, bold, page 6]
  Acknowledgements [sz=20, bold, page 7]
  CONTENTS        [sz=25, bold, page 19]
  ABBREVIATIONS   [sz≈20, bold, pages 12–13]
  INTRODUCTION    [sz≈20, bold, pages 14–15]
  ROLES & RESPONSIBILITIES…  [sz≈19, bold, pages 16–18]

Chapter level:
  Chapter - 1   [sz=20, bold, page 20]  Pharmacovigilance System Master File
  Chapter - 2   [sz=20, bold]           Collection/ICSR
  Chapter - 3   [sz=20, bold]           PSUR
  Chapter - 4   [sz=20, bold]           Quality Management System
  Chapter - 5   [sz=20, bold]           Audits and Inspections
  Chapter - 6   [sz=20, bold]           Risk Management Plan

Section level within chapters (sz=16, italic/larger):
  1.0 Introduction       (page 20)
  1.1 Scope              (page 20)
  1.2 Contents of PSMF   (page 20)

Subsection level (sz=11, bold):
  1.2.1  Pharmacovigilance personnel and their responsibilities
  1.2.2  Pharmacovigilance Organization Structure
  1.2.2.1  Marketing Authorization Holder
  1.2.2.2  Contract Research Organization (CRO)
  1.2.3  Sources of safety data
  1.2.4  Pharmacovigilance Processes
  1.2.4.1  Description
  1.2.4.2  SOPs should include the following
  1.2.4.3  Computerized systems and database
  1.2.4.4  Quality Management System (QMS) in Pharmacovigilance
```

Numbering depth goes to at least 4 levels (`1.2.2.1`). Pattern: `^\d+\.\d+(\.\d+)*\s+` is reliable. Body font = 10–11 pt. Section headings are bold + larger (≥11 pt for subsections, ≥16 for sections).

### `Pv Guidancedoc24.pdf` — actual heading patterns

```
Front matter:
  PREFACE    [sz=13.1, bold, page 4]
  FOREWORD   [sz=12.8, bold, page 5]
  Table of Contents [sz=14, bold, page 6]
  List of Abbreviations [sz=14, bold, page 7]

Top-level sections (sz=12.7–14, bold, numbered with bare integer):
  1.  INTRODUCTION              (page 9)
  2.  ROLES AND RESPONSIBILITIES OF AUTHORITIES  (page 14)
  3.  PHARMACOVIGILANCE PLAN    (page 26)
  4.  PHARMACOVIGILANCE CHAPTERS (page 29)
  5.  References               (not yet confirmed from first-80-heading sample)

Subsection level 2 (sz≈10.8–12, bold):
  2.2   Pharmacovigilance Programme of India (PvPI)
  2.3.1 Immunization Division brief from MoHFW
  2.3.2 Signal Detection and Management for Vaccines
  2.3.4 Strengthening Safety Surveillance for New Vaccine Introduction
  2.4.1 Sharing of AEFI with Marketing Authorization Holder
  3.1.1 Individual Case Safety Report
  3.2   Periodic Safety Update Report
  3.3   Post Marketing Trial (Phase-IV)
  4.1   Pharmacovigilance System Master File
  4.2   Collection, Processing, Reporting of ICSRs

Subsection level 3 (sz≈11.6, bold):
  4.1.1  Introduction
  4.1.2  Scope
  4.1.3  Contents of the PSMF
  4.2.1  Introduction
  4.2.2  Structure & Processes
  4.2.3  Collection and Collation of ICSR

Subsection level 4 (sz≈11.6–12.5, bold):
  4.1.3.1   Pharmacovigilance personnel and their responsibilities
  4.1.3.2.1  Marketing Authorization Holder
  4.1.3.2.2  Contract Research Organization (CRO)
  4.1.3.3   Sources of safety data
  4.1.3.4   Pharmacovigilance Processes
  4.1.3.4.1  Description
  4.1.3.4.2  PV System SOPs should include the followings
  4.2.2.1   Medical inquiries
  4.2.2.2   "Contact us", e-mails and website inquiry forms
  4.2.2.3   MAH's employees
  4.2.2.3.1  Contractual partners
  4.2.2.3.2  Information on Adverse Events from the internet or digital media
  4.2.2.3.3  Solicited Reports
  4.2.2.3.4  Miscellaneous sources for reporting
  4.2.5.1.1  Date of receipt
```

Numbering pattern: bare integer for top level (`1.`, `2.`), then `N.N`, `N.N.N`, `N.N.N.N`, `N.N.N.N.N` for deeper levels. **Critical issue:** the top-level numbering (`1.`, `2.`) uses a period after the digit — the regex must match both `1.` and `1.0` patterns.

**Reliable heading detection for PvGuidancedoc24:**
- Pattern: `^\s*(\d+\.(?:\d+\.?)*)\s+(.{3,})`
- Must additionally require `bold=True` at the span level, because plain numbered sentences in the body text (years like "1940.", "2019.") would otherwise match.
- `bold + numbering_pattern` together is the cleanest signal.

---

## 5. Chunking Strategy by Document

| Document | Strategy | Primary Chunk Boundary | Secondary Split | OCR | Key Notes |
|----------|----------|----------------------|-----------------|-----|-----------|
| `17RecallRapid.pdf` | Section/subsection | Subsection (e.g., 6.1, 6.2) | Paragraph if > ~1500 chars | ❌ | Two embedded documents (pages 1–15 and 11–22 SOP); annexure pages 16–22 are forms |
| `Guidance_Documentpsur2.pdf` | Chapter/section | Section within chapter (e.g., 1.2.1, 1.2.2) | Paragraph if section > 2000 chars | ❌ | "Chapter - N" is the parent; skip repeated chapter banners and page numbers |
| `Pv Guidancedoc24.pdf` | Section/subsection | Subsection (level 3–4 where available) | Paragraph if > 2000 chars | ❌ | Deepest numbered subsection = preferred chunk unit |
| `List of New Drugs 2025.pdf` | Row-level table | One table row = one chunk | — | ❌ | 4 columns, 3 data rows; reuse FDC new_drug_approval_list parser |
| `Pv Guidancedoc24 on vaccines 2.0.pdf` | **SKIP** (duplicate) | — | — | — | Exact SHA-256 duplicate; index only `Pv Guidancedoc24.pdf` |

---

## 6. Section/Subsection Examples (Representative Real Structures)

### `17RecallRapid.pdf`

```
Page 4:
  [sz=16 bold]  1.0 introDuCtion:
                [body ~870 chars]  Introduction describes purpose of recall guidelines...

  [sz=16 bold]  2.0 BaCkgrounD:
                [body ~721 chars]  Background on regulatory framework...

Page 5:
  [sz=16 bold]  5.0 reCall ClassiFiCation:
                [body — Class I, II, III definitions]

  [sz=16 bold]  6.0 reCall ProCeDures:
  [sz=12 bold]    6.1 VoluntarY reCall:
                  [body — steps 1–5, each a numbered bullet]
                  [sz=12 bold]  6.2 statutorY reCall:
                  [body — steps 1–4]

Page 9:
  [sz=16 bold]  11.0 stePWise reCall ProCeDure:
                [body — multi-page, largest section at ~3617 chars on page 9]
```

### `Guidance_Documentpsur2.pdf`

```
Page 20-21:
  [sz=20 bold]  Chapter - 1: Pharmacovigilance System Master File (PSMF)

  [sz=16]  1.0 Introduction
           [body]
  [sz=16]  1.1 Scope
           [body]
  [sz=16]  1.2 Contents of the PSMF
  [sz=11 bold]  1.2.1 Pharmacovigilance personnel and their responsibilities
               [body]
  [sz=11 bold]  1.2.2 Pharmacovigilance Organization Structure
  [sz=11 bold]    1.2.2.1 Marketing Authorization Holder
                 [body]
  [sz=11 bold]    1.2.2.2 Contract Research Organization (CRO)
                 [body]
```

### `Pv Guidancedoc24.pdf`

```
Page 34 onwards:
  [sz=14 bold]  4.2 Collection, Processing, Reporting of Individual Case Safety Reports by MAH
  [sz=11.6 bold]  4.2.1 Introduction
                 [body]
  [sz=11.6 bold]  4.2.2 Structure & Processes
  [sz=12.5 bold]    4.2.2.1 Medical inquiries
                   [body]
  [sz=12.5 bold]    4.2.2.2 "Contact us", e-mails and website inquiry forms
                   [body]
  [sz=12.5 bold]    4.2.2.3 MAH's employees
  [sz=12.5 bold]      4.2.2.3.1 Contractual partners
                     [body]
  [sz=12.5 bold]      4.2.2.3.2 Information on Adverse Events from the internet or digital media
  [sz=12.5 bold]      4.2.2.3.3 Solicited Reports
  [sz=12.5 bold]      4.2.2.3.4 Miscellaneous sources for reporting
```

---

## 7. Large Section Analysis

### `17RecallRapid.pdf`

| Section | Page | Approx Chars | Needs Split? |
|---------|------|-------------|--------------|
| 11.0 Stepwise Recall Procedure | 9 | ~3,617 (page 9 alone) | ⚠️ Possibly |
| 9.0 Procedure for Rapid Alert | 7 | ~2,883 | ✅ Fits in one chunk |
| 4.0 Definitions | 4 | ~2,827 | ✅ Fits |
| 6.0 Recall Procedures (total) | 5–6 | ~4,500 est. | ⚠️ Split at 6.1/6.2 |

Section 11.0 spans pages 9–10 and contains the most detailed procedural content. The numbered sub-steps (1., 2., 3., etc. inside 11.0) provide natural paragraph split points if needed. Recommendation: try subsection-first; fall back to paragraph splitting for any block exceeding 2,000 characters.

### `Guidance_Documentpsur2.pdf`

Most pages average 1,500–2,500 chars. The body chapters run pages 21–83. Individual subsections (e.g., `1.2.4.1`, `1.2.4.2`) are typically 200–800 chars each — well within a single chunk. No section appears to require aggressive splitting. The "ROLES & RESPONSIBILITIES" section spans pages 16–18 (~6,000 chars total across 3 pages) — this should be split by subsection (CDSCO, NCC-PvPI, CRO, etc.), not as one chunk.

### `Pv Guidancedoc24.pdf`

Most subsections are leaf-level (4 levels deep) and contain 200–800 chars. The `ROLES AND RESPONSIBILITIES OF AUTHORITIES` section and `PHARMACOVIGILANCE CHAPTERS` span many pages but have abundant 4th-level subsections to chunk by. No section requires fixed-size splitting — the existing decimal numbering structure provides enough granularity.

**General rule:** Any section/subsection exceeding ~1,800 characters should be split at paragraph boundaries (blank line + new sentence start). No arbitrary fixed-size splits.

---

## 8. Metadata Schema

### Universal Metadata (all PV chunks)

| Field | Type | Source | Notes |
|-------|------|--------|-------|
| `document_id` | string | filename stem (slugified) | e.g., `pv_guidancedoc24`, `recall_rapid_17` |
| `document_type` | enum | Detected from title/content | `pv_guidance`, `psur_guidance`, `recall_guideline`, `new_drug_approval_list` |
| `document_title` | string | Page 2–3 cover text | Extracted from first non-blank cover content |
| `source` | string | Always `"CDSCO"` | Hardcoded |
| `source_url` | string | metadata.csv if exists; else `None` | No metadata.csv for PV folder |
| `release_date` | string | Cover page, effective date field | e.g., `"2017"` (Recall), `"2.0"` implies version |
| `local_file` | string | Relative path from project root | |
| `page_number` | integer | PyMuPDF page index + 1 | 1-based |
| `chunk_type` | enum | Assigned at chunking time | `section`, `subsection`, `table_row` |
| `file_sha256` | string | SHA-256 of PDF | For deduplication and traceability |

### PV-Specific Metadata

| Field | Type | Source | Applicable To |
|-------|------|--------|---------------|
| `section_number` | string | Extracted heading pattern | All guidance/guideline docs |
| `section_heading` | string | Text after section number | All guidance/guideline docs |
| `parent_section` | string | Parent heading number | Subsections only |
| `section_depth` | integer | Count of `.` in section number + 1 | All guidance docs |
| `document_version` | string | Cover page "Version: N.N" or "VERSION: YYYY" | PSUR2 (`2.0`), Recall (`2017`) |
| `effective_date` | string | Cover page `Effective Date:` field | Recall only (`2012-11-23`) |
| `chapter` | string | `"Chapter - N"` label where present | PSUR2 only |

**Fields NOT recommended** (not reliably available):
- `subsection` as a separate field — covered by `section_number` + `section_depth`
- `publication_date` — only `Recall` document has an explicit effective date; others show only version number
- `author` — no consistent author field extractable

### New Drug List Metadata (reuses FDC schema)

| Field | Type | Source |
|-------|------|--------|
| `drug_name` | string | Table col 2 |
| `indication` | string | Table col 3 |
| `date_of_approval` | string | Table col 4 (DD.MM.YYYY) |
| `fdc_or_new_drug` | string | Always `"new_drug"` |
| `serial_number` | string | Table col 1 |

---

## 9. Recall/Rapid Alert Document (`17RecallRapid.pdf`) — Detailed Structure

### Document has TWO parts in one PDF

**Part 1 (pages 1–15): Main Recall Guideline**
- Sections 1.0–15.0 with subsections 6.1, 6.2
- Pages 1–3: cover, inner cover, table of contents
- Pages 4–14: actual content (sections 1.0–15.0)
- Page 15: blank/footer only

**Part 2 (pages 11–22): Embedded SOP document**
- Sections 1.0–9.0 (numbering restarts)
- SOP header: "1 of 5", "2 of 5", etc. — appears in running header
- Pages 16–22: annexure forms — standard format letters, notification templates, flow diagrams
- Pages 20–21: blank/image pages (0 chars)

### Chunking Recommendation for 17RecallRapid.pdf

- **Part 1 sections 1.0–15.0:** Each section (and subsection where present) becomes one chunk. Total estimated: ~13 meaningful content chunks (sections 1–13 + abbreviations + references).
- **Part 2 SOP sections 1.0–9.0:** Each section becomes a chunk. ~7 content sections.
- **Annexure pages 16–22:** Skip page-number-only and blank pages. The actual letter formats/notifications on pages 16–19 contain meaningful procedural text (~2,000 chars/page) — include as `chunk_type: annexure` with `section_number: "Annexure"`.
- **Procedure steps:** The numbered steps inside sections (1., 2., 3., 4., 5. inside 6.1 Voluntary Recall; 3.1–3.4 inside 3.0 Responsibility) should remain together as one chunk for their parent subsection, not become individual micro-chunks. Each step is 1–3 sentences; splitting them would destroy context.

### Header/Footer Filtering for 17RecallRapid.pdf

The string `"Central Drugs stanDarD Control organization"` (mixed case, sz=12) appears at the top of many pages as a running page header. Must be stripped. Pattern: any line matching `(?i)central drugs standar[d] control organi[sz]ation` at the start of a block.

Page numbers appear as a bare integer on its own line (e.g., just `"2"`, `"3"`, ...) as a span with sz=12 on the header line — must be stripped.

---

## 10. 2025 New Drug Table — Exact Structure

### pdfplumber extraction result

```
Table: 4 rows × 4 columns

Row 0 (header):  ['S.No.', 'Name of New Drug', 'Indication', 'Date of Approval']

Row 1:  ['1.', 'Tafamidis Bulk Drug', '', '16.01.2025']
Row 2:  ['2.', 'Letermovir Bulk Drug &Letermovir Tablets 240mg and 480 mg',
         'Letermovir is indicated for prophylaxis of cytomegalovirus (CMV) infection...',
         '17.01.2025']
Row 3:  ['3.', 'Fexuprazan hydrochloride Bulk Drug and Fexuprazan hydrochloride Tablets 40mg',
         'Indicated for the treatment of erosive esophagitis(EE).',
         '10.02.2025']
```

### Observations

- **Header row present, correctly detected.** Column names map exactly to the FDC schema: `serial_number` → col 0, `drug_name` → col 1, `indication` → col 2, `date_of_approval` → col 3.
- **Row 1 (Tafamidis) has empty indication.** Acceptable — older entries in the FDC list also have empty indications.
- **Row 2 indication is truncated** in pdfplumber output (60-char truncation in my test). Full text from PyMuPDF raw: "Letermovir is indicated for prophylaxis of cytomegalovirus (CMV) infection and disease in adult CMV-seropositive recipients [R+] of an allogeneic hematopoietic stem cell transplant (HSCT). It is also indicated for prophylaxis of CMV disease in adult kidney transplant recipients at high risk (Donor CMV seropositive/Recipient CMV seronegative[D+/R-])"
- **Dates in `DD.MM.YYYY` format** — normalized by existing `normalize_approval_date()`.
- **Strategy: one row = one chunk.** This is identical to the FDC `new_drug_approval_list` path. The existing `process_table_document()` function from `fdc.py` will work directly on this document if the column mapping is correct. No specialized parser needed.
- **Only 3 drug entries.** This is a "till date" list covering early 2025.

---

## 11. Duplicate Analysis

### SHA-256 Comparison

| File | SHA-256 |
|------|---------|
| `Pv Guidancedoc24.pdf` | `91750e24b4f99c15c88a66315e6ab5a6181ae138cb80c5c7a50ea398ed626223` |
| `Pv Guidancedoc24 on vaccines 2.0.pdf` | `91750e24b4f99c15c88a66315e6ab5a6181ae138cb80c5c7a50ea398ed626223` |

**Conclusion: Byte-for-byte identical.** Same SHA-256, same file size (7,116,125 bytes), same page count (116). The second filename suggests it was uploaded as "version 2.0" but the file is identical. Only `Pv Guidancedoc24.pdf` should be indexed. The chunker must check SHA-256 at startup and skip any file whose hash matches an already-indexed document.

---

## 12. OCR Requirements

| Document | OCR Required? | Reason |
|----------|---------------|--------|
| `17RecallRapid.pdf` | ❌ No | 34,264 total chars; avg 1,557/page; text fully readable. One zero-char page (p20) is a blank page — skip. |
| `Guidance_Documentpsur2.pdf` | ❌ No | 132,103 total chars; avg 1,536/page. Zero-char pages (pp. 53, 59, 65, 69–71, 84–85) are embedded figures — skip silently. |
| `Pv Guidancedoc24.pdf` | ❌ No | 184,621 total chars; avg 1,592/page. Zero-char pages (pp. 1–3, 113–116) are cover/blank — skip. |
| `List of New Drugs 2025.pdf` | ❌ No | 776 chars on 1 page; table extracted cleanly. |
| `Pv Guidancedoc24 on vaccines 2.0.pdf` | **SKIP ENTIRELY** | Duplicate. |

**OCR is not required for any PV document.** All five files are text-based PDFs with good extraction quality. PyMuPDF `get_text("text")` is sufficient for all.

---

## 13. Recommended Parser Architecture

```
pharmacovigilance/
  ├── Input: PV_DIR/*.pdf
  │
  ├── Step 1: Inventory + deduplication
  │     For each PDF:
  │       - compute SHA-256
  │       - if hash already seen → skip (duplicate)
  │       - else → proceed
  │
  ├── Step 2: Document type detection
  │     Classify by filename + cover page text:
  │       "Recall" / "Rapid Alert"    → recall_guideline
  │       "PSUR" / "Marketing Auth"   → psur_guidance
  │       "vaccine" / "Guidancedoc24" → pv_guidance_vaccines
  │       "New Drugs approved"        → new_drug_approval_list
  │
  ├── Step 3: Per-type parser
  │
  │   ── new_drug_approval_list ──────────────────────────────────
  │     Use existing process_table_document() from fdc.py
  │     (column mapping: S.No / Name of New Drug / Indication / Date of Approval)
  │     Output: one Chunk per table row
  │
  │   ── recall_guideline / psur_guidance / pv_guidance_vaccines ─
  │     1. Extract full text page-by-page via PyMuPDF get_text("dict")
  │     2. For each page:
  │          a. Filter running headers (regex: known header strings)
  │          b. Filter bare page-number spans
  │          c. Collect spans with (text, size, bold, page_number)
  │     3. Heading detection:
  │          Candidate = span where (bold AND size > body_size + 0.5)
  │                      OR (numbering_pattern matches AND bold)
  │          numbering_pattern = r"^\d+\.(\d+\.)*\d*\s+"
  │     4. Build section tree:
  │          section_stack = []
  │          On each heading:
  │            depth = count of dots in numbering
  │            push to stack at correct depth level
  │            flush previous leaf section as a chunk
  │     5. Chunk text = heading text + body text accumulated until next heading
  │     6. If chunk text > 1800 chars → split at paragraph boundaries
  │        (paragraph boundary = double newline or new sentence after blank line)
  │
  ├── Step 4: Chunk creation
  │     Chunk(
  │       chunk_id = f"pv_{document_id}_{section_number_slug}",
  │       text     = f"Section {section_number}: {heading}. {body_text}",
  │       metadata = { universal + pv_specific fields }
  │     )
  │
  └── Step 5: Output
        list[Chunk] — same interface as fdc.py / alerts.py
```

### Where specialized parsers are needed

| Document | Specialized Handling |
|----------|---------------------|
| `List of New Drugs 2025.pdf` | **No specialized parser.** Use existing FDC table parser directly. |
| `17RecallRapid.pdf` | Specialized heading detection needed: mixed-case font (`introDuCtion`), split headings (heading text wraps across two lines on pages 7–8), SOP restart at page 11. |
| `Guidance_Documentpsur2.pdf` | Specialized: "Chapter - N" level above numbered sections; running chapter headers must be filtered. |
| `Pv Guidancedoc24.pdf` | Specialized: top-level sections use `N.` (not `N.0`); 4-level nesting; running page-number spans must be filtered. |

---

## 14. Risks / Edge Cases

### R1: Mixed-case cosmetic font in 17RecallRapid
Headings appear as `"introDuCtion"`, `"BaCkgrounD"`, `"reCall"` — decorative alternating caps. These are correctly read by PyMuPDF (text content is correct), but the text does not match standard title-case patterns. Heading detection must NOT rely on the text casing — rely on font size + bold flag + numbering pattern instead.

### R2: Split heading text across spans
In `Guidance_Documentpsur2.pdf`, heading "Pharmacovigilance System Master File (PSMF)" is split across multiple bold spans on consecutive lines (e.g., `"Pharmacovigilance System Master File"` + `"(PSMF)"`). Similarly, `"8.0 tiMe lines For eFFeCtiVe reCall"` + `"sYsteM & raPiD alert:"` appear as two consecutive bold-large lines. The heading accumulator must join adjacent bold-large lines until a non-heading line is encountered.

### R3: Running page headers contaminating content
"Central Drugs stanDarD Control organization" appears as a running page header (sz=12, some pages sz=12.8) on almost every page of 17RecallRapid and some pages of PSUR2. If not filtered, this string will appear at the start of many chunks. Filter by exact string match (case-insensitive).

### R4: Page numbers mixed into text
Bare page-number integers (`"8"`, `"9"`, `"10"`) appear as isolated spans with sz=13 (bold) in PSUR2, or sz=8 (small) in the SOP part of 17RecallRapid. Must be identified and filtered: a span whose entire text is a small integer (≤ 3 digits) with no surrounding text is a page number.

### R5: Embedded figures (zero-char pages)
Pages 84–85 in PSUR2, pages 20–21 in 17RecallRapid, and pages 1–3 and 113–116 in PvGuidancedoc24 are either completely blank or contain only embedded images. These must be silently skipped — they are not OCR candidates (the images are diagrams/flowcharts, not text).

### R6: SOP restart in 17RecallRapid
The section numbering restarts at `1.0` on page 11. If the parser sees two `"1.0"` sections, it must not collapse them. Suggested handling: treat pages 1–15 and pages 11–22 as two distinct logical "parts" of the document, or use page number as a tiebreaker in chunk_id.

### R7: Table on page 17 in PvGuidancedoc24 (vaccine schedule table)
Page 17 contains an AEFI schedule table with cells like `"14 weeks"`, `"1 year of age"`, `"5 years of age"` — these were incorrectly picked up as numbered headings by the heading detector (because they start with digits). The heading detector must require `bold=True` to avoid false positives from table cell content.

### R8: Annexure forms in 17RecallRapid (pages 16–22)
Pages 16–22 contain standard CDSCO notification letters (pre-printed forms). These have low information density for RAG but contain the actual recall notification format. Recommended: include as `chunk_type: annexure` with a note that they are template documents, OR skip if retrieval value is low.

### R9: Abbreviation sections
Both `Guidance_Documentpsur2.pdf` and `Pv Guidancedoc24.pdf` have abbreviation lists (ABBREVIATIONS, LIST OF ABBREVIATIONS sections). These are lists of acronym → expansion pairs. Chunking them as a single `section` chunk is correct — they are useful for RAG queries about acronyms. Do NOT split individual abbreviation entries.

### R10: 2025 New Drug List — only 3 entries
This list is dated "till date" and likely to be updated. The chunker must handle it gracefully if future versions have more rows or different column layouts. The existing FDC table parser already handles this correctly.

### R11: No metadata.csv for PV folder
Unlike FDC and ADR folders, the `pharmacovigilance/` directory has no `metadata.csv`. All metadata (`document_title`, `release_date`, `document_version`) must be extracted from the PDFs themselves (cover pages) or inferred from filenames.

---

## 15. Final Recommended Strategy

### Summary

| Document | Parser Type | Est. Chunks | Primary Split Level |
|----------|-------------|-------------|---------------------|
| `17RecallRapid.pdf` | `pv_section_parser` | ~20 | Subsection (6.1, 6.2) + SOP sections |
| `Guidance_Documentpsur2.pdf` | `pv_section_parser` | ~60–80 | Subsection within chapter (e.g., 1.2.1, 1.2.2) |
| `Pv Guidancedoc24.pdf` | `pv_section_parser` | ~80–100 | Level-3 or level-4 subsection |
| `List of New Drugs 2025.pdf` | FDC `process_table_document` | 3 | One row = one chunk |
| `Pv Guidancedoc24 on vaccines 2.0.pdf` | **SKIP** | 0 | Exact duplicate |

### Architecture decisions

1. **One unified `pv_section_parser()` function** handles all three guidance/guideline documents. Document-specific differences (mixed-case headings, chapter-level grouping, restart numbering) are handled by configurable flags or post-processing steps within the same function.

2. **The 2025 New Drug List** reuses the existing FDC `process_table_document()` function with no new code — it is structurally identical to other FDC new_drug_approval_list documents.

3. **SHA-256 deduplication** at the start of `chunking()` prevents the duplicate `Pv Guidancedoc24 on vaccines 2.0.pdf` from being processed. Log a warning: "Skipping [filename]: duplicate of [original]".

4. **No OCR needed** for any document. All PDFs are text-extractable.

5. **Heading detection signal** (in priority order):
   - `bold=True` + `decimal_numbering_pattern` → strongest signal
   - `bold=True` + `size > body_size + 1.5` → section title (unnumbered, e.g., PREFACE, CHAPTERS)
   - `decimal_numbering_pattern` alone → only if size ≥ body_size (avoids table cell false positives)

6. **Paragraph splitting** as fallback for any section > 1,800 chars: split at double-newline boundaries, keeping each paragraph as a sub-chunk with the same `section_number` but an appended `_p1`, `_p2` suffix.

7. **Running headers filter** (exact strings): strip any text block matching `r"(?i)central drugs standar[d] control organi[sz]ation"` and bare page-number spans.

---

*Report generated by automated PDF structural analysis using PyMuPDF and pdfplumber. All findings are based on actual extraction results from the five PV PDFs. No assumptions made about document content that was not directly observed.*
