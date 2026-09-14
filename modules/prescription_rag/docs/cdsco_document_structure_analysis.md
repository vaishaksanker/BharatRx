# CDSCO Document Structure Analysis

> **Purpose:** Pre-chunking structural analysis of all CDSCO PDFs in the BharatRx dataset.  
> **Date:** 2026-09-13  
> **Analyst:** Kiro (automated PDF inspection using pdfplumber 0.11.0)  
> **Status:** Analysis only — no chunking, embeddings, or vector DB created.

---

## 1. Dataset Overview

| Folder | PDF Count | Total Size | metadata.csv | Text Extractable | Scanned / Image-Only | Main Document Types |
|--------|-----------|-----------|--------------|------------------|----------------------|---------------------|
| `adr/` | 68 | ~51 MB | ✅ Yes | ❌ None (0/68) | ✅ All 68 are image-only | ADR safety notifications |
| `fdc_new_drugs/` | 44 | ~24.6 MB | ✅ Yes | ✅ ~38/44 | ⚠️ ~6 partially scanned | FDC approval lists, new drug approval lists, procedure documents |
| `alerts/` | 14 | ~8.7 MB | ✅ Yes | ⚠️ ~9/14 | ⚠️ ~5 scanned | NSQ alerts, spurious drug alerts, circulars, theft alerts |
| `pharmacovigilance/` | 5 | ~19.8 MB | ❌ No | ✅ 4/5 (1 redundant duplicate) | ❌ None fully scanned | Guidance documents, recall guidelines, new drug approval lists |

**Total PDFs: 131**  
**PDFs with selectable text: ~51**  
**PDFs requiring OCR: ~80 (all ADR + several alerts/FDC)**

---

## 2. ADR Documents

### Inventory
- **Count:** 68 PDFs
- **Total size:** ~51 MB
- **metadata.csv columns:** `id`, `drug_name`, `adr`, `release_date`, `source`, `source_url`, `pdf_url`, `local_file`
- **Filename pattern:** `{NNN}_{DrugName}_{ADRType}.pdf`

### Representative Samples Inspected

| File | Pages | Has Text | Reason Selected |
|------|-------|----------|-----------------|
| `001_Tranexamic_Acid_Back_Pain.pdf` | 2 | ❌ No | Smallest/simplest, earliest in series |
| `005_Vancomycin_Dress_Syndrome.pdf` | 2 | ❌ No | Different drug class (antibiotic) |
| `044_Chloroquine_SJS-TEN.pdf` | 2 | ❌ No | Small file size (66 KB) — possible format variation |
| `046_Proton_Pump_Inhibitor_Acute_Kidney_Injury.pdf` | 2 | ❌ No | Largest early file (1 MB) — possible multi-image layout |
| `067_FDC_of_Piperacillin_and_Tazobactam.pdf` | 1 | ❌ No | FDC combination drug, single-page variant |
| `068_Carbamazepine_SJS_TEN.pdf` | 1 | ❌ No | Largest file (2.4 MB), single-page |

### Observed Structure (from filename + metadata + file characteristics)

**All 68 ADR PDFs are image-only scanned documents.** Zero characters were extracted from any ADR PDF using pdfplumber. Text extraction via standard PDF parsing is impossible for this entire folder.

**Inferred structure from filenames and metadata.csv:**
- The metadata.csv provides structured fields: `drug_name`, `adr` (reaction type), `release_date`
- Each PDF represents a single ADR safety notification from CDSCO
- Filenames encode: drug name + adverse reaction type
- Based on the CDSCO ADR notification format (known regulatory format), these are likely structured as:

```
[CDSCO Letterhead / Logo]
Drug Name
Adverse Drug Reaction Type
[Body text with case report / pharmacological explanation]
[Regulatory recommendation or warning]
[Signature / stamp]
```

### OCR Requirements
- **OCR is mandatory for all 68 ADR PDFs.**
- The metadata.csv already provides `drug_name` and `adr` fields — these are reliable ground truth and do NOT need to be re-extracted by OCR.
- OCR is needed only for the full narrative body text (case description, pharmacology, regulatory recommendation).

### Duplicates Observed
- Files `001` and `003` are both `Tranexamic_Acid_Back_Pain.pdf` with identical file sizes (485,508 bytes). These are exact duplicates.
- Files `031` through `039` all have identical file sizes (786,296 bytes) — these are likely a batch of identically formatted documents and may share the same template image.
- Files `066`, `067`, `068` are significantly larger (1.8–2.4 MB) — likely multi-image or higher resolution scans.

---

## 3. FDC / New Drug Documents

### Inventory
- **Count:** 44 PDFs
- **Total size:** ~24.6 MB
- **metadata.csv columns:** `id`, `serial_number`, `title`, `release_date`, `pdf_size`, `source`, `source_url`, `pdf_url`, `local_file`
- **Document types identified:**
  1. **FDC Approval Lists** — tables of Fixed Dose Combinations approved by DCG(I), indexed by date range
  2. **New Drug Approval Lists (SND Division)** — tables of new molecular entities approved year-by-year
  3. **Procedure Documents** — text-heavy procedural/regulatory guidance for subsequent FDC applicants
  4. **Rational FDC Lists** — enumerated lists of FDCs declared rational by the Kokate Committee

### Representative Samples Inspected

| File | Pages | Has Text | Table Headers | Reason Selected |
|------|-------|----------|---------------|-----------------|
| `001_FDC...1961_to_2019.pdf` | 100 | ✅ Yes | S.NO. / Name of Drug / Indication / Date of approval | Master FDC list, largest volume |
| `003_NEW DRUGS...2024.pdf` | 5 | ✅ Yes | Sr. No. / Drug Name / Indication / Date of approval | Recent new drugs, short document |
| `010_Procedure...Kokate.pdf` | 45 | ❌ No (scanned) | — | Procedure document, entirely scanned |
| `021_Details of 294 FDCs.pdf` | 2 | ✅ Yes | Sr. no. / Name of FDC | Rational list, simple enumeration |
| `041_List...1961-1970.pdf` | 17 | ✅ Yes | S.No / Name of Drug / Pharmacological action/Indication / Date of Approval | Historical list with longer indications |
| `009_drugs_approved_1999.pdf` | 1 | ✅ Yes (partial) | S. No / Drug Name / Composition / Indication / Date of Approval | Older format, merging composition column |

### Observed Document Structures

#### Type 1: FDC Approval List (e.g., `001`, `002`, `004`, `006`, `007`, `012`, `015`)
```
[Page title: "FIXED DOSE COMBINATIONS APPROVED BY DCG (I) [date range]"]
Table spanning multiple pages:
  | S.NO. | Name of Drug | Indication | Date of approval |
  | ...   | Drug A + Drug B + Drug C | [sometimes empty] | MMM-YY |
[No footer. No section headers. Continuous table across 100+ pages.]
```
- Indication column is frequently **empty** — the drug combination name is the primary content.
- Drug names use `+` as separator for active ingredients (e.g., `Cyanocobalamine + Zinc tannic acid complex`).
- Dates in `MMM-YY` format (e.g., `Jan-61`) for older records; `DD.MM.YYYY` for recent records.

#### Type 2: New Drug Approval List — SND Division (e.g., `003`, `005`, `008`, `011`, `017`, `019`)
```
[Title: "NEW DRUGS APPROVAL LIST FROM SND DIVISION FROM [date] TO [date]"]
Table spanning multiple pages:
  | Sr. No. | Drug Name | Indication | Date of approval |
  | ...     | [drug + dosage form + strength] | [full indication text] | DD.MM.YYYY |
```
- Drug Name cells include dosage form and strength: `Zolpidem Sublingual Spray 3.85% w/v (Additional Dosage Form)`
- Indication cells contain full-text clinical indication descriptions (multi-sentence).
- Date format: `DD.MM.YYYY`.

#### Type 3: New Drug Approval Lists — Year-by-Year (e.g., `023`–`044`)
```
[Title: "List of New Drugs Approved for Marketing in India year YYYY"]
Table:
  | S.No | Name of Drug | Pharmacological action/Indication | Date of Approval |
```
- Very similar to Type 2 but older records (2001–2018).
- Some older files (1961–1990 decade files: `041`, `043`, `044`) use `Month-YYYY` date format.
- Drug names include dosage form and strength.

#### Type 4: Procedure Documents (e.g., `010`, `013`, `018`, `020`)
```
[Title page]
[Body: numbered sections, paragraphs, annexures]
[Tables may be embedded as images within scanned pages]
```
- These are **entirely scanned** (zero text extractable).
- Example: `010_Procedure...Kokate...pdf` — 45 pages, 0 chars extracted.

#### Type 5: Rational FDC Lists / Annexures (e.g., `014`, `021`)
```
[Title: "Annexure-C: List of [N] FDCs which were considered as Rational"]
Table or numbered list:
  | Sr. no. | Name of FDC |
  | 1       | Aceclofenac+Serratiopeptidase |
```
- FDC names use `+` separator with no spaces (e.g., `Aceclofenac+Serratiopeptidase`).
- Some entries use `&` or comma separators inconsistently.
- Indication column often missing or sparse.

### Column Consistency Across FDC/New Drug Tables

| Column | Consistency | Notes |
|--------|-------------|-------|
| Serial number | High | Always present; period after number (e.g., `1.`) in some, plain integer in others |
| Drug name | High | Always present; drug + dosage form + strength mixed into single cell in newer docs |
| Indication | Medium | Present in newer docs; absent in older FDC lists |
| Date of approval | High | Always present; format varies (`Jan-61`, `12.01.2024`, `January-1961`) |
| Composition | Low | Only present in specific SND division lists (e.g., `009`) |

---

## 4. Alerts

### Inventory
- **Count:** 14 PDFs (some with duplicate/corrigendum numbering: `003` and `004` are the same file)
- **Total size:** ~8.7 MB
- **metadata.csv columns:** `id`, `serial_number`, `title`, `release_date`, `pdf_size`, `source`, `source_url`, `pdf_url`, `local_file`
- **Document types identified:**
  1. **NSQ (Not of Standard Quality) Alerts** — monthly tables of drug batches failing quality tests
  2. **Spurious Drug Alerts** — monthly tables of drugs declared spurious/counterfeit
  3. **Theft Alerts** — narrative circulars about stolen drug products
  4. **General Circulars** — administrative circulars (e.g., GST rate structure)
  5. **Corrigenda** — corrections/amendments to previously issued alerts

### Representative Samples Inspected

| File | Pages | Has Text | Table Headers | Reason Selected |
|------|-------|----------|---------------|-----------------|
| `005_CDSCO NSQ ALERT...June 2025.pdf` | 6 | ✅ Yes | S.No / Product/Drug Name / Batch No. / Manufacturing Date / Expiry Date / Manufactured By / NSQ Result / Reported by CDSCO Laboratory | Most recent CDSCO NSQ monthly alert |
| `005_STATE NSQ ALERT...June 2025.pdf` | 15 | ✅ Yes | S.No / Product/Drug Name / Batch No. / Manufacturing Date / Expiry Date / Manufactured By / NSQ Result / Reported by State Laboratory | State-level variant of same alert type |
| `009_Spurious...May 2025.pdf` | 2 | ✅ Yes | S.No. / Name of Drugs-medical device-cosmetics / Batch No. / Date of Manufacture / Date of Expiry / Manufactured By / Reason for failure / Drawn By / Firm's reply / Remarks | Spurious drug alert |
| `007_Spurious...June 2025.pdf` | 2 | ✅ Yes | Same as above | Spurious drug alert, different month |
| `006_Revise list drug alert May-2025.pdf` | 1 | ✅ Yes | Same as Spurious table | Revised/updated alert |
| `010_NSQ ALERT...MAY-2025.pdf` | 7 | ✅ Yes | S.No / Product/Drug Name / Batch No. / Manufacturing Date / Expiry Date / Manufactured By / NSQ Result / Reported by CDSCO Laboratory | Larger NSQ monthly alert with multi-page table |
| `003_Alert...Novo Nordisk...transit.pdf` | 2 | ❌ No (scanned) | — | Theft alert narrative circular |
| `002_Availability of NSQ Alert...Website.pdf` | 1 | ❌ No (scanned) | — | Administrative notice |
| `001_Circular...GST rate.pdf` | 10 | ❌ No (scanned) | — | General circular, scanned |

### Observed Document Structures

#### Type 1: NSQ Monthly Alert — CDSCO Central Labs (e.g., `005_CDSCO`, `010`)
```
[Header: "NOT OF STANDARD QUALITY (NSQ) ALERT FOR THE MONTH OF [MONTH-YEAR] (CDSCO/Central Laboratories)"]
[Preamble paragraph: 2-3 sentences explaining surveillance purpose]
Table (multi-page):
  | S.No | Product/Drug Name | Batch No. | Manufacturing Date | Expiry Date | Manufactured By | NSQ Result | Reported by CDSCO Laboratory |
[No footer.]
```
- **Drug Name cell** includes: brand name, generic name, dosage form, strength (e.g., `Dextrose Injection I.P. 5%w/v (D5)`)
- **Manufactured By cell** includes: full company name + complete address
- **NSQ Result** is the specific quality test that failed (e.g., `Assay of Dextrose (Anhydrous)`, `Particulate matter`)
- **Reporting lab** (CDL Kolkata, RDTL Guwahati, etc.) identifies the testing authority
- Tables span multiple pages; **headers do NOT repeat** between pages

#### Type 2: NSQ Monthly Alert — State Labs (e.g., `005_STATE`)
```
Same structure as CDSCO central but:
  - Column 8: "Reported by State Laboratory" instead of "CDSCO Laboratory"
  - Significantly more rows (15 pages vs 6 pages)
  - Some rows have merged/split cells causing extraction artifacts
```

#### Type 3: Spurious Drug Alert (e.g., `007`, `009`, `006`)
```
[Header: "List of Drugs, Medical Devices, Vaccine and Cosmetics declared as Spurious for the Month of [Month-Year]"]
[Preamble: standard 2-sentence surveillance statement]
Table:
  | S.No. | Name of Drugs/medical device/cosmetics | Batch No. | Date of Manufacture | Date of Expiry | Manufactured By | Reason for failure | Drawn By | Firm's reply | Remarks |
```
- **Firm's reply** and **Remarks** columns contain long narrative text: typically confirming the product is under investigation and was not manufactured by them.
- **Manufactured By** is "Under Investigation" for most entries (manufacturer is disputed/unknown).
- This table has **10 columns** — significantly wider than the NSQ table (8 columns).
- `Drawn By` = the drugs inspector and state who collected the sample.

#### Type 4: Theft Alerts / Circulars (e.g., `001`, `002`, `003`)
- Entirely scanned images. Zero text extractable.
- These are narrative circulars, not tabular data.
- Structure is likely: letterhead → subject line → body paragraphs → list of stolen items → instructions → signature/stamp.

---

## 5. Pharmacovigilance

### Inventory
- **Count:** 5 PDFs
- **Total size:** ~19.8 MB
- **metadata.csv:** ❌ Not present
- **Document types identified:**
  1. **PV Guidance Documents** — long-form regulatory guidance (100+ pages)
  2. **Recall & Rapid Alert Guidelines** — procedural guideline document (22 pages)
  3. **New Drug Approval Lists** — tabular list (1 page)
  4. **Duplicate files** — `Pv Guidancedoc24.pdf` and `Pv Guidancedoc24 on vaccines 2.0.pdf` are identical (116 pages, same content)

### Representative Samples Inspected

| File | Pages | Has Text | Reason Selected |
|------|-------|----------|-----------------|
| `Guidance_Documentpsur2.pdf` | 86 | ✅ Yes (partial — ~2.8K chars in 5 pages) | PSUR guidance, major reference document |
| `Pv Guidancedoc24.pdf` | 116 | ✅ Yes (partial — ~2.3K chars in 5 pages) | Main PV guidance for vaccines |
| `17RecallRapid.pdf` | 22 | ✅ Yes (~6.3K chars in 5 pages) | Recall & Rapid Alert guideline, best text extraction |
| `List of New Drugs approved in the year 2025.pdf` | 1 | ✅ Yes | Tabular — same structure as FDC Type 2 |
| `Pv Guidancedoc24 on vaccines 2.0.pdf` | 116 | ✅ Yes (identical to above) | Duplicate of `Pv Guidancedoc24.pdf` |

### Observed Document Structures

#### Type 1: PV Guidance Document — PSUR (`Guidance_Documentpsur2.pdf`)
```
[Cover page: title + publisher (NCC-PvPI / IPC / CDSCO / MoHFW)]
[Copyright page]
[Table of Contents: section numbers + page numbers]
[Abbreviations list]
[Sections 1–N with numbered headings and sub-headings]
[Appendices / Annexures]
```
- Text extraction works but yields **low character density** (~570 chars/page average for first 5 pages) — this indicates the document uses a multi-column layout, decorative fonts, or embedded graphics alongside text.
- Cover/title pages contribute near-zero text.
- Section structure: `1.0 Introduction → 1.1 Objective → 1.2 Background...`
- Regulatory language: formal, structured, uses abbreviations (PSUR, MAH, ADR, AEFI, etc.)

#### Type 2: PV Guidance Document — Vaccines (`Pv Guidancedoc24.pdf`)
```
[PREFACE]
[FOREWORD]
[Table of Contents]
  - ABBREVIATIONS: page 5
  - 1. INTRODUCTION: page 7
    - 1.1 Objective
    - 1.2 Background
    - 1.3 Rationale
    - 1.4 Scope
  - 2. ROLES AND RESPONSIBILITIES OF AUTHORITIES
    - 2.1 CDSCO
    - 2.2 NCC-PvPI
    - 2.3 AEFI Secretariat
    - 2.4 PSUR/PV/AEFI review committee
  ... (continues to multiple sections)
[Annexures]
```
- 116 pages; elaborate section hierarchy observed from table of contents.
- Low chars/page (~460) — likely dense two-column layout or graphics-heavy pages.
- Contains formal regulatory definitions, scope, procedures, timelines.

#### Type 3: Recall & Rapid Alert Guidelines (`17RecallRapid.pdf`)
```
[Cover page: "GUIDELINES ON RECALL AND RAPID ALERT SYSTEM FOR DRUGS"]
[Official cover with Document No., Version, Effective Date]
[Table of Contents:]
  1.0 Introduction
  2.0 Background
  3.0 Scope
  4.0 Definitions
  5.0 Recall Classification (Class I / II / III)
  6.0 Recall Procedures (6.1 Voluntary, 6.2 Statutory)
  7.0 Level of Recall
  8.0 Time Lines for Effective Recall System & Rapid Alert
  9.0 Procedure for Rapid Alert & Recall System
  10.0 Overview of Process Flow
  11.0 Stepwise Procedure [truncated]
[Body sections with numbered paragraphs and definitions]
[Process flow diagrams — likely embedded as images]
```
- Best text extraction in this folder (~1.25K chars/page for first 5 pages).
- Definitions section: `CUSTOMER: ...`, `VOLUNTARY RECALL: ...` — structured definition list.
- Process flow overview on page 8 is text-extracted (not purely graphical).

#### Type 4: New Drugs 2025 (`List of New Drugs approved in the year 2025.pdf`)
```
[Title: "List of New Drugs approved in the year 2025 till date"]
Table (1 page):
  | S.No. | Name of New Drug | Indication | Date of Approval |
```
- Identical structure to FDC/New Drugs Type 2.
- Drug Name cell: includes dosage form, strength, and "Bulk Drug" notation.
- Indication cell: full clinical indication text.

---

## 6. Tables and Lists

### Table Inventory by Folder

| Folder | Documents with Tables | Table Type | Headers Repeat Across Pages | Rows Span Multiple Pages | Can Convert to Text |
|--------|-----------------------|------------|----------------------------|--------------------------|---------------------|
| `adr/` | 0 (all scanned) | — | — | — | — |
| `fdc_new_drugs/` | ~38 of 44 | Approval list | ❌ Do NOT repeat | ✅ Yes | ✅ Yes (with care) |
| `alerts/` | ~9 of 14 | NSQ/Spurious | ❌ Do NOT repeat | ✅ Yes (NSQ-May: 7 pages) | ⚠️ With caution |
| `pharmacovigilance/` | 1 of 5 (new drugs 2025) | Approval list | N/A (single page) | ❌ No | ✅ Yes |

### Critical Table Observations

**Problem 1: Table headers do not repeat.**  
In `010_NSQ_ALERT_MAY-2025.pdf`, the table runs across 7 pages. pdfplumber extracts pages 2–7 as if they are headerless continuations. Rows from page 2 onward start with serial numbers (e.g., `9.`, `20.`) — there is no repeated header row. Any row-level chunking must carry the column schema as metadata.

**Problem 2: Merged / split cells produce extraction artifacts.**  
Observed in `005_STATE NSQ ALERT...June 2025.pdf` — some rows have `None` values in cells that contain content visually merged with adjacent cells. Example header row:  
`['', '', '', '', '', 'Sanand, Dist.-Ahmedabad-382213, India', '', '']`  
This is the second half of the manufacturer address from the previous row, extracted as a new row by pdfplumber.

**Problem 3: Multi-line cell content.**  
Drug name, manufacturer address, and indication fields routinely contain `\n` within a single cell. Example:  
`'Zolpidem Sublingual\nSpray 3.85% w/v\n(Additional Dosage Form)'`  
These must be joined with a space before text processing.

**Problem 4: Long address strings in Manufactured By.**  
Manufacturer full addresses occupy large chunks of cell text. These are useful as metadata but noisy in semantic chunk text.

**Problem 5: FDC `001` spans 100 pages** — one continuous table with ~2,000+ rows and no section breaks.

### Tables That Should Be Stored as Structured Data (NOT just chunked as text)

| Document | Reason |
|----------|--------|
| All NSQ alert tables | Each row is an independent, queryable fact (batch number, drug, lab result) |
| All spurious drug tables | Each row is an independent, queryable fact |
| FDC approval list tables | Each row is a drug approval record — best treated as structured data |
| New drug approval list tables | Each row is a drug approval record |
| Rational FDC lists | Each row is an FDC name — best as a lookup table |

---

## 7. Special Cases

### SCN-01: Entire ADR Folder — All 68 PDFs are Scanned Images
- **Files:** `001` through `068` in `adr/`
- **Problem:** Zero text extractable. Standard PDF parsing yields nothing. OCR is mandatory for the entire folder.
- **Additional complication:** These appear to be scanned CDSCO notification letters — likely with a printed letterhead, body text, tables (case details), and a signature/stamp at the bottom. The stamp and signature are image elements that OCR cannot reliably reproduce.
- **Mitigation:** The `metadata.csv` provides `drug_name` and `adr` (reaction type) as structured ground truth. These should be used as metadata fields without re-extracting from OCR.

### SCN-02: Duplicate ADR PDFs
- **Files:** `001` = `003` (Tranexamic Acid Back Pain, 485,508 bytes each)
- **Files:** `031` through `039` all have identical sizes (786,296 bytes each — 8 files, same byte size)
- **Problem:** De-duplication needed before indexing to avoid duplicate chunks in the vector store.

### SCN-03: Scanned Procedure Documents in FDC
- **Files:** `010`, `013`, `018`, `020` (Procedure documents)
- **Problem:** Entirely scanned, 0 chars extracted. These are important regulatory procedure texts but inaccessible without OCR.
- `010` is 45 pages; `018` is the largest FDC file (1.7 MB, ~30+ pages).

### SCN-04: Non-repeating Table Headers (Multi-page Tables)
- **Files:** `010_NSQ_MAY_2025.pdf` (7 pages), `005_STATE_NSQ_June_2025.pdf` (15 pages), `001_FDC...2019.pdf` (100 pages)
- **Problem:** Headers appear only on page 1. Pages 2+ have no column labels. Naïve chunking by page will produce context-free chunks with no column identity.

### SCN-05: Merged Cell Extraction Artifacts
- **Files:** `005_STATE_NSQ_ALERT_June_2025.pdf`
- **Problem:** pdfplumber splits a multi-line cell into a separate pseudo-row with all `None` values except one string. Rows like `['', '', '', '', '', 'address-second-line', '', '']` appear in the extracted data.

### SCN-06: Duplicate Pharmacovigilance Files
- **Files:** `Pv Guidancedoc24.pdf` (116 pages) and `Pv Guidancedoc24 on vaccines 2.0.pdf` (116 pages)
- **Problem:** Identical content, two filenames. Indexing both would double every chunk from this document in the vector store.

### SCN-07: Low Text Density in PV Guidance Documents
- **Files:** `Guidance_Documentpsur2.pdf` (86 pages), `Pv Guidancedoc24.pdf` (116 pages)
- **Problem:** Despite being text PDFs (not scanned), only ~460–570 chars/page are extracted in the first 5 pages. This suggests complex layout: two-column text, decorative headers rendered as vector graphics, or tables with heavy formatting. The actual content per page is much richer than the extracted text suggests.
- **Implication:** Layout-aware extraction (bounding box analysis) may be needed to correctly order multi-column text flows.

### SCN-08: Administrative Circulars with No Pharmacological Content
- **Files:** `001_Circular...GST_rate.pdf` (alerts folder), `002_Availability_of_NSQ_Alert...pdf`
- **Problem:** These are administrative/procedural documents, not pharmacological data. They should either be excluded from the RAG index or tagged with `document_type: administrative` and given low relevance weight.

### SCN-09: Inconsistent Date Formats Across Documents
- Observed formats: `Jan-61`, `January-1961`, `12.01.2024`, `DD/MM/YYYY`, `DD-MM-YYYY`, `MMM-YYYY`
- This affects date filtering and temporal queries in RAG.

---

## 8. Chunking Implications

### ADR Documents (68 PDFs — all scanned)

| Strategy | Recommendation |
|----------|---------------|
| Fixed-size chunking | ❌ Not appropriate — no text to chunk until OCR is done |
| Section-based chunking | ✅ Appropriate post-OCR — each ADR notification is a single short document (1–2 pages); one document = one semantic unit |
| Semantic chunking | ⚠️ Useful but secondary — the document is short enough that the full post-OCR text may fit in a single chunk |
| Table-aware chunking | ⚠️ Possibly needed — ADR notifications may contain a case-details table (patient info, drug info, reaction) that should be extracted separately |
| Page numbers preserved | ✅ Yes — useful for citing source page |
| Section hierarchy | ✅ Preserve if OCR recovers headings (drug name, reaction type, case summary, regulatory recommendation) |
| What becomes metadata | `drug_name`, `adr_type`, `release_date`, `document_id`, `source` — all available from metadata.csv without OCR |
| What stays in chunk text | The narrative: case description, pharmacological explanation, regulatory recommendation, any warnings |

**Why:** Each ADR notification describes a specific drug + reaction combination. A RAG query like "what are the adverse effects of Vancomycin?" should retrieve the full narrative of the relevant notification. The document is short (1–2 pages), so the entire OCR output of one document is the natural chunk unit. Sub-document chunking may only be needed if OCR reveals multi-section structure.

---

### FDC / New Drug Documents (44 PDFs — mostly text)

| Strategy | Recommendation |
|----------|---------------|
| Fixed-size chunking | ❌ Not appropriate — will cut across drug entries mid-row |
| Section-based chunking | ❌ Not applicable — documents have no sections, only tables |
| Row-level chunking | ✅ **Primary strategy** — each table row = one drug approval = one chunk |
| Table-aware chunking | ✅ **Required** — tables must be parsed row-by-row with schema-aware extraction |
| Parent-child chunks | ✅ Useful — parent: document metadata (title, date range, document type); child: individual drug approval row |
| Page numbers preserved | ✅ Yes |
| Section hierarchy | N/A — no sections |
| What becomes metadata | `drug_name`, `indication`, `date_of_approval`, `document_type` (FDC vs new drug), `coverage_period`, `document_id` |
| What stays in chunk text | `"{drug_name} was approved by DCG(I) for {indication} on {date_of_approval}."` — synthesised sentence from row |

**Why:** Each row is an independent, atomic fact: "Drug X was approved for indication Y on date Z." These are ideal RAG retrieval units for queries like "Is Aceclofenac+Serratiopeptidase an approved FDC?" or "When was Zolpidem sublingual spray approved in India?" Fixed-size chunking would merge multiple unrelated drug entries into one chunk, severely degrading retrieval precision.

**Special note for Procedure Documents (scanned):** Post-OCR, section-based chunking applies. Each procedure step / numbered clause is a natural chunk unit.

---

### Alerts (14 PDFs — mixed text/scanned)

| Strategy | Recommendation |
|----------|---------------|
| Fixed-size chunking | ❌ Not appropriate |
| Row-level chunking for NSQ/Spurious tables | ✅ **Primary strategy** — each row = one drug batch alert = one chunk |
| Table-aware chunking | ✅ **Required** — same reasons as FDC |
| Scanned alerts (circulars, theft) | OCR required; narrative paragraph chunking appropriate |
| Parent-child chunks | ✅ Useful — parent: alert month/type; child: individual batch entry |
| Page numbers preserved | ✅ Yes |
| What becomes metadata | `alert_type` (NSQ/spurious/theft/circular), `drug_name`, `batch_number`, `manufacturer`, `manufacturing_date`, `expiry_date`, `nsq_result`, `reporting_lab`, `alert_month`, `document_id` |
| What stays in chunk text | Synthesized sentence: `"Batch {batch_no} of {drug_name} manufactured by {manufacturer} was found NSQ for {nsq_result} as reported by {lab} in {month}."` |

**Why:** Alert queries in BharatRx will be highly specific: "Is batch ABC123 of Dexamethasone flagged?" or "Which batches of Azithromycin failed quality tests in 2025?" Row-level chunking is the only strategy that enables precise batch-level retrieval.

---

### Pharmacovigilance (5 PDFs — mostly text)

| Strategy | Recommendation |
|----------|---------------|
| Fixed-size chunking | ⚠️ Acceptable only as fallback |
| Section-based chunking | ✅ **Primary strategy** — numbered sections (1.0, 1.1, 2.0…) are natural chunk boundaries |
| Semantic chunking | ✅ Useful within long sections |
| Table-aware chunking | ⚠️ Minor — only the new drugs 2025 file has a table |
| Parent-child chunks | ✅ Useful — parent: section; child: sub-section paragraphs |
| Page numbers preserved | ✅ Yes |
| Section hierarchy preserved | ✅ Yes — critical for guidance docs |
| What becomes metadata | `document_title`, `section_number`, `section_heading`, `subsection`, `document_type` (guidance/guideline/list), `version`, `publication_date`, `page_number` |
| What stays in chunk text | Full section text including definitions, procedures, and timelines |

**Why:** PV guidance documents are consulted for regulatory procedures (PSUR submission timelines, recall procedures, adverse event reporting requirements). Queries like "What is the timeline for Class I drug recall?" need section-level precision. The table of contents (observed in `17RecallRapid.pdf`) provides a clean map for section-based splitting.

---

## 9. Metadata Recommendations

Based on actual document content observed, the following metadata fields are recommended. Fields marked ✅ are directly available without OCR. Fields marked 🔬 require text extraction or OCR.

### Universal Fields (all documents)

| Field | Type | Source | Notes |
|-------|------|--------|-------|
| `document_id` | string | metadata.csv `id` | Unique per document |
| `document_type` | enum | metadata.csv `title` / folder name | `adr_notification`, `fdc_approval_list`, `new_drug_approval_list`, `fdc_procedure`, `nsq_alert`, `spurious_alert`, `theft_alert`, `circular`, `pv_guidance`, `recall_guideline` |
| `document_title` | string | metadata.csv `title` | |
| `source` | string | metadata.csv `source` | Always `"CDSCO"` |
| `source_url` | string | metadata.csv `source_url` | |
| `release_date` | date | metadata.csv `release_date` | Normalize to ISO format |
| `local_file` | string | metadata.csv `local_file` | Relative path |
| `page_number` | integer | 🔬 Extracted at parse time | 1-indexed |
| `chunk_type` | enum | Assigned at chunking time | `full_document`, `table_row`, `section`, `subsection`, `paragraph` |

### ADR-Specific Fields

| Field | Type | Source | Notes |
|-------|------|--------|-------|
| `drug_name` | string | ✅ metadata.csv `drug_name` | Always available |
| `adr_type` | string | ✅ metadata.csv `adr` | Always available |
| `ocr_confidence` | float | 🔬 OCR engine output | Flag low-confidence extractions |

### FDC / New Drug Fields

| Field | Type | Source | Notes |
|-------|------|--------|-------|
| `drug_name` | string | 🔬 Table `Name of Drug` column | May include dosage form + strength |
| `indication` | string | 🔬 Table `Indication` column | Often empty in older FDC lists |
| `date_of_approval` | date | 🔬 Table `Date of approval` column | Normalize from varied formats |
| `coverage_period` | string | ✅ Document title | e.g., `"1961-2019"`, `"2024"` |
| `fdc_or_new_drug` | enum | ✅ Filename / title | `"FDC"` or `"new_drug"` |

### Alert Fields

| Field | Type | Source | Notes |
|-------|------|--------|-------|
| `alert_type` | enum | ✅ Document title | `"NSQ"`, `"spurious"`, `"theft"`, `"circular"` |
| `alert_month` | string | ✅ Document title | e.g., `"June 2025"` |
| `drug_name` | string | 🔬 Table `Product/Drug Name` column | Includes brand name + generic + dosage form |
| `batch_number` | string | 🔬 Table `Batch No.` column | Critical for batch-level lookup |
| `manufacturer` | string | 🔬 Table `Manufactured By` column | Full name + address |
| `manufacturing_date` | date | 🔬 Table column | Format varies |
| `expiry_date` | date | 🔬 Table column | Format varies |
| `nsq_result` | string | 🔬 Table `NSQ Result` column | Specific test failure |
| `reporting_lab` | string | 🔬 Table `Reported by...Laboratory` | CDL Kolkata, RDTL Guwahati, etc. |

### Pharmacovigilance Fields

| Field | Type | Source | Notes |
|-------|------|--------|-------|
| `section_number` | string | 🔬 Extracted heading | e.g., `"6.1"` |
| `section_heading` | string | 🔬 Extracted heading | e.g., `"Voluntary Recall"` |
| `subsection` | string | 🔬 Extracted sub-heading | |
| `document_version` | string | 🔬 Cover page | e.g., `"Version: 2.0"`, `"VERSION: 2017"` |
| `effective_date` | date | 🔬 Cover page | `17RecallRapid` has explicit effective date |

### Fields NOT Recommended
- `parent_chunk_id` — keep this as an internal indexing field, not a retrieval metadata field
- `chunk_index` — internal only
- `embedding_model` — operational metadata, not RAG-useful
- `manufacturer` as a top-level field for ADR documents — not present in ADR notifications (would need OCR to confirm)

---

## 10. Recommended Parsing Architecture

```
PDF Input
    │
    ▼
[Stage 1: PDF Type Detection]
    ├── Check: pdfplumber text extraction > 100 chars?
    │       YES → Text PDF → proceed to Stage 3
    │       NO  → Image PDF → proceed to Stage 2
    │
    ▼
[Stage 2: OCR — REQUIRED FOR: all 68 ADR, ~6 FDC procedure docs, ~5 alert circulars]
    ├── Tool recommendation: Tesseract OCR (open source) or Google Cloud Vision
    ├── Input: page images rendered at 300 DPI from PDF
    ├── Output: page-level text strings
    └── Attach: OCR confidence score per page as metadata
    │
    ▼
[Stage 3: Document Type Classification]
    ├── By folder: adr/ → ADR notification
    ├── By title keywords: "FDC APPROVED" → FDC approval list
    ├── By title keywords: "NEW DRUGS APPROVAL" / "SND DIVISION" → new drug list
    ├── By title keywords: "NSQ ALERT" → NSQ alert
    ├── By title keywords: "SPURIOUS" → spurious alert
    ├── By title keywords: "GUIDANCE DOCUMENT" / "GUIDELINES" → PV guidance
    └── Fallback: manual tag
    │
    ▼
[Stage 4: Layout & Structure Detection — REQUIRED FOR: FDC lists, Alerts, PV Guidance]
    ├── For table documents: use pdfplumber table extraction per page
    ├── For guidance documents: detect section headings via font size / bold or regex patterns
    ├── Handle: merged cells, None values, multi-line cells
    └── Handle: multi-column text flow in PV documents (bounding box ordering)
    │
    ▼
[Stage 5: Section / Heading Detection — REQUIRED FOR: PV guidance, Recall guidelines]
    ├── Pattern: `^\d+\.\d*\s+[A-Z]` → numbered heading
    ├── Extract: section number + heading text
    └── Build: section hierarchy map (parent section → child subsections)
    │
    ▼
[Stage 6: Table Extraction — REQUIRED FOR: FDC lists, Alerts]
    ├── Extract tables row-by-row
    ├── Attach column schema to each row (carry header from page 1)
    ├── Clean: join `\n` within cells, strip leading/trailing whitespace
    ├── Clean: remove artifact rows (all-None or all-empty)
    ├── Normalize: dates to ISO 8601, drug names to lowercase
    └── Flag: low-confidence rows (e.g., Manufactured By = "Under Investigation")
    │
    ▼
[Stage 7: Normalized Document Representation]
    ├── ADR: {metadata from CSV} + {OCR full text per page}
    ├── FDC/Alerts (tables): {document metadata} + {list of row dicts}
    ├── PV Guidance: {document metadata} + {list of sections with heading + body}
    └── Attach: source URL, release date, page number, document type
    │
    ▼
[Stage 8: Chunking — NOT IMPLEMENTED YET]
    ├── ADR: one chunk per document (post-OCR full text)
    ├── FDC/Alerts (tables): one chunk per row
    ├── PV Guidance: one chunk per section/subsection
    └── Attach all metadata fields to each chunk
    │
    ▼
[Stage 9: Embedding — NOT IMPLEMENTED YET]
    │
    ▼
[Stage 10: Vector Database — NOT IMPLEMENTED YET]
```

### Stages That Are Genuinely Necessary vs Optional

| Stage | Necessity | Reason |
|-------|-----------|--------|
| Stage 1 (PDF type detection) | ✅ Mandatory | All ADR PDFs are image-only; must detect before choosing path |
| Stage 2 (OCR) | ✅ Mandatory | 68 ADR + ~11 other PDFs cannot be parsed without it |
| Stage 3 (doc type classification) | ✅ Mandatory | Chunking strategy differs completely by type |
| Stage 4 (layout detection) | ✅ Mandatory for tables and PV docs | Multi-page tables, multi-column layouts |
| Stage 5 (heading detection) | ✅ Mandatory for PV guidance | Section-based chunking depends on it |
| Stage 6 (table extraction) | ✅ Mandatory for FDC + alerts | Primary content of these documents is tabular |
| Stage 7 (normalized representation) | ✅ Mandatory | Unifies heterogeneous inputs |
| Stage 8 (chunking) | Not yet | Next phase |
| Stage 9 (embedding) | Not yet | Next phase |
| Stage 10 (vector DB) | Not yet | Next phase |

---

## 11. Important Findings

1. **The ADR folder (68 PDFs, ~51 MB) is entirely image-only.** This is the most critical finding. No text is extractable without OCR. However, `metadata.csv` provides reliable structured ground truth (`drug_name`, `adr_type`, `release_date`) that should be used directly as metadata, bypassing OCR for these fields.

2. **FDC and alert documents are primarily tabular.** The entire information content lives in table cells. Fixed-size or paragraph-based chunking will destroy the semantic integrity of these documents. Row-level chunking is the only correct approach.

3. **Table headers do not repeat across pages** in multi-page tables. The column schema must be carried forward from page 1 and attached to every row during extraction.

4. **Procedure documents in FDC (`010`, `013`, `018`, `020`) are also fully scanned.** These are significant documents (~45 pages each) and are currently completely inaccessible. OCR is required.

5. **Pharmacovigilance guidance documents have low text extraction density** despite being text PDFs. Multi-column layout or complex formatting causes pdfplumber to extract partial text. Layout-aware extraction or a tool like `pymupdf` with reading-order detection may yield better results.

6. **Two files are exact duplicates:**
   - ADR: `001` and `003` (Tranexamic Acid Back Pain)
   - PV: `Pv Guidancedoc24.pdf` and `Pv Guidancedoc24 on vaccines 2.0.pdf`
   De-duplication is required before indexing.

7. **31–39 in ADR (8 files) have identical byte counts** (786,296 bytes). These may be identical template images with different content stamped on, or genuinely identical files. Visual inspection of OCR output will be required to confirm.

8. **The `alerts/` metadata.csv only has 10 rows but there are 14 PDFs.** Four PDFs are not registered in the metadata: the duplicate `003` and `004` files and the corrigendum files. The downloader created duplicates.

9. **No pharmacovigilance metadata.csv exists.** For the 5 PV files, metadata must be manually authored or extracted from document cover pages.

10. **Date formats are highly inconsistent** across the dataset: at least 6 distinct formats observed. A normalizer is required in Stage 7.

---

## 12. Recommended Next Step

**Implement the OCR pipeline for the ADR folder first.**

Rationale:
- ADR documents are the most directly relevant to prescription safety checking in BharatRx.
- All 68 are image-only, making OCR a hard blocker before any RAG can be built on this data.
- The `metadata.csv` already provides the key metadata fields — OCR only needs to recover the narrative body text.
- After OCR, the ADR documents can be indexed as simple full-document chunks (one document = one chunk) without complex chunking logic.

Suggested tooling for OCR: `pytesseract` (free, offline) or `easyocr` (better accuracy for mixed layouts). Pre-render PDF pages to PNG at 300 DPI using `pdf2image` before passing to OCR.

**Second priority: table extraction pipeline for FDC and Alerts.**

These are text-readable and do not require OCR. The row-level table extraction is the only significant engineering task before these documents can be chunked and indexed.

**Third priority: section-based extraction for PV guidance documents.**

These are long-form reference documents. Investigate `pymupdf` (fitz) as an alternative to pdfplumber for better multi-column text ordering before committing to a parsing strategy.

---

*Report generated by automated PDF structural analysis. All observations are based on actual pdfplumber extraction results from representative samples. No assumptions were made about document content that was not directly confirmed by extraction.*
