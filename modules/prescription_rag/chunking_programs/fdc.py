"""
FDC / New Drug document chunker for BharatRx.

Chunking strategy
-----------------
1. FDC approval lists:
       one table row = one chunk

2. New Drug approval lists:
       one table row = one chunk

3. Rational FDC lists:
       one table/list entry = one chunk

4. Scanned FDC procedure documents:
       OCR -> section/procedure chunking

Important:
- Multi-page tables may NOT repeat headers.
- Header/schema information is therefore carried across pages.
- Multi-line cells are normalized.
- Each chunk is self-contained and includes useful metadata.

Public API:
    from fdc import chunking
    chunks = chunking()
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import fitz
import pandas as pd
import pytesseract
from PIL import Image


# ============================================================
# PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

FDC_DIR = PROJECT_ROOT / "data" / "cdsco" / "fdc_new_drugs"
METADATA_FILE = FDC_DIR / "metadata.csv"

PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

OCR_CACHE_DIR = PROCESSED_DIR / "fdc_ocr"
CHUNKS_FILE = PROCESSED_DIR / "fdc_chunks.json"


# ============================================================
# CHUNK OBJECT
# ============================================================

@dataclass
class Chunk:
    chunk_id: str
    text: str
    metadata: dict[str, Any]


# ============================================================
# TESSERACT
# ============================================================

def configure_tesseract() -> None:
    """
    Configure Tesseract executable.

    Adjust this path only if Tesseract is installed elsewhere.
    """

    possible_paths = [
        Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
        Path(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"),
    ]

    for path in possible_paths:
        if path.exists():
            pytesseract.pytesseract.tesseract_cmd = str(path)
            return


# ============================================================
# TEXT CLEANING
# ============================================================

def clean_text(text: Any) -> str:
    """
    Clean general extracted/OCR text.
    """

    if text is None:
        return ""

    text = str(text)

    text = text.replace("\r", "\n")

    # Join line breaks inside a logical sentence/cell.
    text = re.sub(r"\s*\n\s*", " ", text)

    # Normalize whitespace.
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def clean_cell(value: Any) -> str:
    """
    Clean an individual table cell.
    """

    if value is None:
        return ""

    if isinstance(value, float) and pd.isna(value):
        return ""

    return clean_text(value)


def normalize_header(header: Any) -> str:
    """
    Normalize table header text for matching.
    """

    text = clean_cell(header).lower()

    text = text.replace(".", "")
    text = text.replace(":", "")
    text = text.replace("-", " ")
    text = re.sub(r"\s+", " ", text)

    return text.strip()


# ============================================================
# DOCUMENT TYPE DETECTION
# ============================================================

def detect_document_type(title: str, filename: str) -> str:
    """
    Classify an FDC/New Drug document.
    """

    value = f"{title} {filename}".lower()

    if "procedure" in value:
        return "fdc_procedure"

    if "rational" in value or "kokate" in value:
        return "rational_fdc_list"

    if "new drug" in value or "new drugs" in value:
        return "new_drug_approval_list"

    if "snd" in value:
        return "new_drug_approval_list"

    if "fdc" in value or "fixed dose" in value:
        return "fdc_approval_list"

    # Fallback for unknown list documents.
    return "fdc_approval_list"


# ============================================================
# METADATA
# ============================================================

def load_metadata() -> pd.DataFrame:
    """
    Load FDC metadata.csv if available.
    """

    if not METADATA_FILE.exists():
        return pd.DataFrame()

    df = pd.read_csv(METADATA_FILE)

    return df


def metadata_for_file(
    metadata_df: pd.DataFrame,
    filename: str,
) -> dict[str, Any]:
    """
    Find metadata corresponding to a PDF filename.
    """

    if metadata_df.empty:
        return {}

    if "local_file" not in metadata_df.columns:
        return {}

    matches = metadata_df[
        metadata_df["local_file"].astype(str).str.strip() == filename
    ]

    if matches.empty:
        # Fallback to filename containment.
        matches = metadata_df[
            metadata_df["local_file"]
            .astype(str)
            .str.contains(
                re.escape(filename),
                case=False,
                na=False,
            )
        ]

    if matches.empty:
        return {}

    row = matches.iloc[0]

    result = {}

    for column in metadata_df.columns:
        value = row[column]

        if pd.isna(value):
            continue

        result[column] = value

    return result


# ============================================================
# DATE NORMALIZATION
# ============================================================

MONTH_MAP = {
    "jan": "01",
    "feb": "02",
    "mar": "03",
    "apr": "04",
    "may": "05",
    "jun": "06",
    "jul": "07",
    "aug": "08",
    "sep": "09",
    "oct": "10",
    "nov": "11",
    "dec": "12",
}


def normalize_approval_date(value: str) -> Optional[str]:
    """
    Normalize common CDSCO approval-date formats.

    Examples:
        12.01.2024 -> 2024-01-12
        Jan-61     -> 1961-01
        January-1961 -> 1961-01

    If the date cannot be safely normalized, return the
    original cleaned value.
    """

    value = clean_cell(value)

    if not value:
        return None

    # DD.MM.YYYY
    match = re.fullmatch(
        r"(\d{1,2})[./-](\d{1,2})[./-](\d{4})",
        value,
    )

    if match:
        day, month, year = match.groups()

        try:
            return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
        except ValueError:
            return value

    # DD/MM/YYYY
    match = re.fullmatch(
        r"(\d{1,2})/(\d{1,2})/(\d{4})",
        value,
    )

    if match:
        day, month, year = match.groups()

        try:
            return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
        except ValueError:
            return value

    # Month-YYYY / Month YYYY
    match = re.fullmatch(
        r"([A-Za-z]+)[\s-]+(\d{4})",
        value,
    )

    if match:
        month_name, year = match.groups()

        month_key = month_name[:3].lower()

        if month_key in MONTH_MAP:
            return f"{year}-{MONTH_MAP[month_key]}"

    # MMM-YY
    match = re.fullmatch(
        r"([A-Za-z]{3})[-\s]+(\d{2})",
        value,
    )

    if match:
        month_name, year = match.groups()

        month_key = month_name.lower()

        if month_key in MONTH_MAP:
            year_int = int(year)

            # CDSCO historical dates such as Jan-61 refer to 1961.
            full_year = 1900 + year_int

            return f"{full_year}-{MONTH_MAP[month_key]}"

    return value


# ============================================================
# PDF TEXT EXTRACTION
# ============================================================

def extract_pdf_text(pdf_path: Path) -> list[str]:
    """
    Extract page-level text using PyMuPDF.
    """

    page_texts = []

    with fitz.open(_windows_path(pdf_path)) as doc:
        for page in doc:
            page_texts.append(page.get_text("text"))

    return page_texts


def pdf_has_useful_text(pdf_path: Path) -> bool:
    """
    Determine whether the PDF contains usable selectable text.
    """

    try:
        pages = extract_pdf_text(pdf_path)

        total_chars = sum(
            len(clean_text(text))
            for text in pages
        )

        return total_chars > 100

    except Exception:
        return False


# ============================================================
# OCR
# ============================================================

def ocr_page(page: fitz.Page) -> tuple[str, float]:
    """
    OCR one PDF page.
    """

    configure_tesseract()

    matrix = fitz.Matrix(300 / 72, 300 / 72)

    pix = page.get_pixmap(
        matrix=matrix,
        alpha=False,
    )

    image = Image.frombytes(
        "RGB",
        [pix.width, pix.height],
        pix.samples,
    )

    data = pytesseract.image_to_data(
        image,
        lang="eng",
        config="--psm 6",
        output_type=pytesseract.Output.DICT,
    )

    texts = []
    confidences = []

    for text, confidence in zip(
        data["text"],
        data["conf"],
    ):
        text = clean_text(text)

        if not text:
            continue

        texts.append(text)

        try:
            confidence = float(confidence)

            if confidence >= 0:
                confidences.append(confidence)

        except (ValueError, TypeError):
            pass

    result = " ".join(texts)

    average_confidence = (
        sum(confidences) / len(confidences)
        if confidences
        else 0.0
    )

    return result, average_confidence


def ocr_pdf(
    pdf_path: Path,
) -> tuple[list[str], list[float]]:
    """
    OCR the entire PDF page-by-page.
    """

    texts = []
    confidences = []

    with fitz.open(_windows_path(pdf_path)) as doc:
        for page in doc:
            text, confidence = ocr_page(page)

            texts.append(text)
            confidences.append(confidence)

    return texts, confidences


# ============================================================
# OCR CACHE
# ============================================================

def ocr_cache_path(pdf_path: Path) -> Path:
    """
    Return the OCR cache file path for a PDF.

    We hash the stem rather than using it verbatim so that PDFs with very long
    filenames (which exceed Windows MAX_PATH when stored under OCR_CACHE_DIR)
    do not cause FileNotFoundError.
    """
    stem_hash = hashlib.sha256(pdf_path.stem.encode()).hexdigest()[:16]
    safe_stem = pdf_path.stem[:40].replace(" ", "_") + "_" + stem_hash
    return OCR_CACHE_DIR / f"{safe_stem}.json"


def save_ocr_cache(
    pdf_path: Path,
    texts: list[str],
    confidences: list[float],
) -> None:

    OCR_CACHE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    cache_file = ocr_cache_path(pdf_path)

    payload = {
        "file": pdf_path.name,
        "pages": [
            {
                "page_number": index + 1,
                "text": text,
                "confidence": confidence,
            }
            for index, (text, confidence)
            in enumerate(zip(texts, confidences))
        ],
    }

    cache_file.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def load_ocr_cache(
    pdf_path: Path,
) -> Optional[tuple[list[str], list[float]]]:

    cache_file = ocr_cache_path(pdf_path)

    if not cache_file.exists():
        return None

    try:
        payload = json.loads(
            cache_file.read_text(
                encoding="utf-8"
            )
        )

        pages = payload.get("pages", [])

        texts = [
            page.get("text", "")
            for page in pages
        ]

        confidences = [
            float(page.get("confidence", 0.0))
            for page in pages
        ]

        return texts, confidences

    except Exception:
        return None


# ============================================================
# PDF HASH
# ============================================================

def calculate_file_hash(pdf_path: Path) -> str:
    """
    SHA-256 hash for document traceability.
    """

    sha256 = hashlib.sha256()

    with open(_windows_path(pdf_path), "rb") as file:
        while True:
            block = file.read(1024 * 1024)

            if not block:
                break

            sha256.update(block)

    return sha256.hexdigest()


# ============================================================
# TABLE EXTRACTION
# ============================================================

def _windows_path(pdf_path: Path) -> str:
    """
    Return an extended-length Windows path string to avoid MAX_PATH (260 char) errors.

    Both fitz (PyMuPDF) and pdfplumber accept string paths.
    On non-Windows or short paths the original resolved string is returned.

    The correct Windows extended-path prefix is \\?\\ (2 backslashes + ? + 1 backslash).
    In Python source that is written as '\\\\?\\\\' — do NOT use a raw string r'\\\\?\\\\' here
    because that would produce 4 backslashes (\\\\?\\\\) which is wrong.

    We use os.listdir-based resolution for paths that exceed 260 chars and therefore
    cannot be accessed via pathlib.Path.exists() / .resolve().
    """

    import platform
    import os

    if platform.system() != "Windows":
        return str(pdf_path)

    # Build the absolute path string.
    # We cannot use pdf_path.resolve() when the path is longer than MAX_PATH
    # because resolve() itself may fail.  Use os.path.abspath instead, which
    # works on the string level without touching the filesystem.
    resolved = os.path.abspath(str(pdf_path))

    # The Windows extended-path prefix value is  \\?\  (4 chars).
    # Written as a Python regular string literal: '\\\\?\\\\'
    #   '\\\\' -> two backslashes
    #   '?'    -> question mark
    #   '\\\\'   -> one backslash
    _UNC_PREFIX = '\\\\?\\'

    if resolved.startswith(_UNC_PREFIX):
        # Already prefixed.
        return resolved

    return _UNC_PREFIX + resolved


def extract_tables_from_pdf(pdf_path: Path) -> list[dict[str, Any]]:
    """
    Extract tables page-by-page using pdfplumber.

    Returns:
        [
            {
                "page_number": 1,
                "table": [...]
            },
            ...
        ]
    """

    import pdfplumber

    results = []

    with pdfplumber.open(_windows_path(pdf_path)) as pdf:

        for page_number, page in enumerate(
            pdf.pages,
            start=1,
        ):

            tables = page.extract_tables()

            for table in tables:

                if not table:
                    continue

                results.append(
                    {
                        "page_number": page_number,
                        "table": table,
                    }
                )

    return results


# ============================================================
# HEADER DETECTION
# ============================================================

def _joined_header_text(rows: list[list[Any]]) -> str:
    """
    Merge several candidate rows column-wise and concatenate all cell text.

    This handles PDFs where a single header is split vertically:

        Row 0: ['S.No', 'Drug Name', 'Indication', 'Date of']
        Row 1: ['',     '',          '',           'Approval']

    becomes: 'Date of Approval' for the last column.
    """

    if not rows:
        return ""

    n_cols = max(len(r) for r in rows)

    merged_cells = []

    for col in range(n_cols):
        parts = []

        for row in rows:
            if col < len(row):
                cell = normalize_header(row[col])

                if cell:
                    parts.append(cell)

        merged_cells.append(" ".join(parts))

    return " ".join(merged_cells)


def is_header_text(joined: str) -> bool:
    """
    Determine whether a joined header text string is a valid FDC table header.

    Uses word-boundary checks for short keywords ('fdc', 'drug') to avoid false
    positives where these words appear inside drug names or indication text.
    """

    # Use word-boundary regex for short tokens that can appear mid-sentence.
    import re as _re
    _word = lambda w: bool(_re.search(r'\b' + _re.escape(w) + r'\b', joined))

    drug_present = (
        "name of drug" in joined
        or "name of fdc" in joined
        or "name of drugs" in joined
        or _word("drug name")
        or joined.strip() in {"fdc", "drug"}
        or "product name" in joined
    )

    # Highly specific drug/fdc column names qualify on their own.
    specific_drug = (
        "name of fdc" in joined
        or "name of drug" in joined
        or "name of drugs" in joined
    )

    approval_present = (
        "approval" in joined
        or "date of approval" in joined
        or "approval date" in joined
    )

    indication_present = (
        "indication" in joined
        or "pharmacological action" in joined
    )

    serial_present = (
        "s no" in joined
        or "sr no" in joined
        or "serial" in joined
    )

    return (
        (drug_present and approval_present)
        or (drug_present and indication_present)
        or (serial_present and drug_present)
        or specific_drug  # 'Name of FDC' alone is unambiguous
    )


def is_header_row(row: list[Any]) -> bool:
    """
    Detect whether a single row is a FDC/New Drug table header.
    """

    joined = _joined_header_text([row])
    return is_header_text(joined)


def _is_header_suffix_row(row: list[Any]) -> bool:
    """
    Return True if this row appears to be a header continuation/suffix row
    (safe to merge with the preceding header row) rather than a data row.

    A header suffix row:
      - has very few non-empty cells (≤ 3), AND
      - none of those cells looks like a drug name / meaningful data, AND
      - each non-empty cell is short (≤ 30 chars after stripping)

    Counter-example (data row): ['1.', 'Cyanocobalamine + Zinc tannic acid', 'Jan-61']
    Example (suffix row):       [None, 'No', None, None, None, 'Approval', None]
    """
    non_empty = [str(c).strip() for c in row if c is not None and str(c).strip()]

    if not non_empty:
        return True  # blank rows are trivially not data rows

    if len(non_empty) > 3:
        return False  # too many cells — looks like real data

    for cell in non_empty:
        if len(cell) > 30:
            return False  # cell too long — likely a drug name
        if _looks_like_drug_name(cell) and not cell.isdigit():
            # Must not be just a serial number digit
            # A real drug name has letters; filter out pure header words
            # like 'No', 'Approval', 'S.', 'no.'
            if len(cell.split()) >= 3:
                return False  # three or more words — likely drug name
            if any(char.isdigit() for char in cell) and len(cell) > 5:
                return False  # contains digits and is non-trivial — likely drug+dose

    return True


def find_header_row(
    table: list[list[Any]],
) -> Optional[tuple[list[Any], int]]:
    """
    Find the header row in the first 4 rows of a table.

    Returns:
        (merged_header_list, header_end_idx) if found, else (None, -1).

        merged_header_list  — a list whose length equals the number of columns
                              in the WIDEST raw row of the header group.  Each
                              element is the stitched header text for that
                              *original* column index.  Columns that contained
                              only empty/None cells carry an empty string.

        header_end_idx      — the exclusive end of the header block.
                              Data rows start at table[header_end_idx].
                              For a single-row header at index i  → i + 1.
                              For a merged group rows 0..end-1    → end.

    IMPORTANT — preserving original column indices
    -----------------------------------------------
    pdfplumber sometimes produces phantom empty columns.  A split header such as:

        row[0]: ['', 'S.', '', 'Drug Name', None, None, 'Composition', ...]
        row[1]: [None, 'No', None, None, None, None, None,   ...]

    merges to a list with 13 entries where:
        col 1 → 's. no'
        col 3 → 'drug name'
        col 11 → 'date of approval'
        all others → ''

    The returned list has one entry PER ORIGINAL COLUMN (including empties), so
    map_columns() receives the correct raw-row indices when it calls enumerate().

    Strategy
    --------
    1. Try single-row headers first (most common case — avoids accidentally
       consuming the first data row).
    2. If a single-row header is found at index i, check whether the NEXT row
       (i+1) is a header suffix (i.e. it contains only short header-fragment
       words like 'No' or 'Approval').  If so, merge them.
    3. If no single row qualifies, try merged pairs/triples (rare — only for
       documents where even the first row alone is not a valid header).
    """

    candidate_rows = table[:4]

    def _build_merged(group: list[list[Any]]) -> list[str]:
        """Stitch a group of rows column-wise, preserving original indices."""
        n_cols = max(len(r) for r in group)
        merged: list[str] = []
        for col in range(n_cols):
            parts = []
            for row in group:
                if col < len(row):
                    cell = normalize_header(row[col])
                    if cell:
                        parts.append(cell)
            merged.append(" ".join(parts))
        return merged

    # Strategy 1: single rows, with optional suffix extension
    for i, row in enumerate(candidate_rows):
        if not is_header_row(row):
            continue

        # Check whether the immediately following row is a header suffix.
        next_i = i + 1
        if next_i < len(candidate_rows):
            next_row = candidate_rows[next_i]
            if _is_header_suffix_row(next_row):
                # Merge header row + suffix row.
                return _build_merged([row, next_row]), next_i + 1

        # No suffix — return single-row header as-is.
        return list(row), i + 1

    # Strategy 2: merged pairs / triples (no individual row qualifies alone)
    # GUARD: only attempt merging when the first row is plausibly a header
    # (it passes is_header_row, is_header_suffix, OR is_header_text by itself).
    # This prevents three consecutive data rows whose combined text happens to
    # contain the words 'drug' and 'indication' from being treated as a header.
    first_row = candidate_rows[0] if candidate_rows else []
    first_row_text = _joined_header_text([first_row])
    first_row_is_header_candidate = (
        is_header_row(first_row)
        or _is_header_suffix_row(first_row)
        or is_header_text(first_row_text)
    )
    if not first_row_is_header_candidate:
        return None, -1

    for end in range(2, min(4, len(candidate_rows) + 1)):
        group = candidate_rows[:end]
        # Rows after the first must not look like drug data rows.
        if not all(_is_header_suffix_row(r) for r in group[1:]):
            break
        joined = _joined_header_text(group)
        if is_header_text(joined):
            return _build_merged(group), end

    return None, -1


# ============================================================
# COLUMN MAPPING
# ============================================================

def map_columns(
    headers: list[Any],
) -> dict[str, int]:
    """
    Map varying CDSCO table headers to canonical fields.

    The ``headers`` list must be indexed by ORIGINAL column position in the raw
    data rows (i.e. including any phantom/empty columns).  find_header_row()
    guarantees this — it always returns a list whose length equals the widest
    raw row in the header block, with empty strings for phantom columns.

    Extended to handle compact headers such as:
      - 'FDC'           (fixed dose combination drug column)
      - 'Drug'          (generic single-word drug column)
      - 'Approval Date' (compact date column)
      - 'Product Name'  (alternative name for drug column)
      - 'Date'          (ultra-minimal date column)
    """

    mapping: dict[str, int] = {}

    for index, header in enumerate(headers):

        normalized = normalize_header(header)

        if not normalized:
            # Skip phantom / empty columns.
            continue

        # ---- Drug / FDC name column ----
        if (
            "name of drug" in normalized
            or normalized in {
                "drug name",
                "name of fdc",
                "name of drugs",
                "drug",
                "fdc",
                "product name",
            }
            or normalized.startswith("fdc ")
        ):
            mapping["drug_name"] = index

        # ---- Indication column ----
        elif "indication" in normalized:
            mapping["indication"] = index

        elif "pharmacological action" in normalized:
            mapping["indication"] = index

        # ---- Approval date column ----
        elif (
            "date of approval" in normalized
            or "approval date" in normalized
            or "approval" in normalized
        ):
            # Do not stomp drug_name with a bare 'date' if already mapped
            if "date_of_approval" not in mapping:
                mapping["date_of_approval"] = index

        elif normalized == "date" and "date_of_approval" not in mapping:
            mapping["date_of_approval"] = index

        # ---- Serial number column ----
        elif (
            normalized in {"s no", "sr no", "sno", "serial no", "s. no", "sr. no.", "s. no."}
            or normalized.startswith("s no")
            or normalized.startswith("sr no")
            or normalized.startswith("s. no")
            or normalized.startswith("sr. no")
        ):
            mapping["serial_number"] = index

        # ---- Composition column ----
        elif "composition" in normalized:
            mapping["composition"] = index

    return mapping


# ============================================================
# ROW CLEANING
# ============================================================

def clean_table_row(
    row: list[Any],
) -> list[str]:

    return [
        clean_cell(value)
        for value in row
    ]


def is_empty_row(row: list[str]) -> bool:
    return not any(cell.strip() for cell in row)


def looks_like_artifact_row(
    row: list[str],
) -> bool:
    """
    Detect obvious pdfplumber artifacts.

    Example:
        ['', '', '', '']
    """

    if is_empty_row(row):
        return True

    non_empty = [
        cell
        for cell in row
        if cell.strip()
    ]

    # A single long address-like continuation should not
    # automatically become an independent drug record.
    if len(non_empty) == 1:

        text = non_empty[0].lower()

        address_terms = [
            "road",
            "street",
            "dist.",
            "district",
            "india",
            "pincode",
            "pin code",
            "nagar",
            "plot",
            "industrial area",
        ]

        if any(term in text for term in address_terms):
            return True

    return False


# ============================================================
# FDC TYPE DETECTION
# ============================================================

def determine_fdc_or_new_drug(
    document_type: str,
) -> str:

    if document_type == "new_drug_approval_list":
        return "new_drug"

    if document_type == "fdc_approval_list":
        return "FDC"

    if document_type == "rational_fdc_list":
        return "FDC"

    return "FDC"


# ============================================================
# COVERAGE PERIOD
# ============================================================

def extract_coverage_period(
    title: str,
) -> Optional[str]:

    # YYYY-YYYY
    match = re.search(
        r"(19\d{2}|20\d{2})\s*(?:to|-)\s*(19\d{2}|20\d{2})",
        title,
        flags=re.IGNORECASE,
    )

    if match:
        return f"{match.group(1)}-{match.group(2)}"

    # Single year
    match = re.search(
        r"\b(19\d{2}|20\d{2})\b",
        title,
    )

    if match:
        return match.group(1)

    return None


# ============================================================
# ROW CHUNK CREATION
# ============================================================

# Date-like pattern for approval-date plausibility check.
_DATE_PATTERN = re.compile(
    r"\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4}"
    r"|[A-Za-z]{3,}[\s\-]\d{2,4}"
    r"|\d{4}[.\-/]\d{1,2}[.\-/]\d{1,2}",
    re.IGNORECASE,
)


def _looks_like_date(value: str) -> bool:
    return bool(_DATE_PATTERN.search(value))


def _looks_like_drug_name(value: str) -> bool:
    """
    A plausible drug/FDC name contains at least one letter and
    is not just digits or a bare date/serial number.
    """

    if not value:
        return False

    if re.fullmatch(r"[\d.\s]+", value):
        return False

    if _looks_like_date(value) and len(value) < 20:
        return False

    return bool(re.search(r"[A-Za-z]", value))


def create_row_chunk(
    *,
    pdf_path: Path,
    document_metadata: dict[str, Any],
    document_type: str,
    page_number: int,
    row_number: int,
    row: list[str],
    column_mapping: dict[str, int],
    file_sha256: str,
) -> Optional[Chunk]:

    def get_field(name: str, *, plausible=None) -> str:
        """
        Retrieve a field value with a controlled neighbor fallback.

        If the mapped cell is empty, try index+1 then index-1.
        A plausibility function can restrict which neighbor values are accepted.
        """

        index = column_mapping.get(name)

        if index is None:
            return ""

        # Primary lookup
        primary = clean_cell(row[index]) if index < len(row) else ""

        if primary:
            return primary

        # Fallback: index + 1
        next_idx = index + 1
        if next_idx < len(row):
            candidate = clean_cell(row[next_idx])
            if candidate and (plausible is None or plausible(candidate)):
                return candidate

        # Fallback: index - 1
        prev_idx = index - 1
        if 0 <= prev_idx < len(row):
            candidate = clean_cell(row[prev_idx])
            if candidate and (plausible is None or plausible(candidate)):
                return candidate

        return ""

    drug_name = get_field("drug_name", plausible=_looks_like_drug_name)
    indication = get_field("indication")
    approval_date_raw = get_field("date_of_approval")
    serial_number = get_field("serial_number")
    composition = get_field("composition")

    if not drug_name:

        # Some rational FDC lists may have only a simple
        # "Name of FDC" column.
        return None

    approval_date = normalize_approval_date(
        approval_date_raw
    )

    fdc_or_new_drug = determine_fdc_or_new_drug(
        document_type
    )

    coverage_period = extract_coverage_period(
        str(
            document_metadata.get(
                "title",
                pdf_path.stem,
            )
        )
    )

    if document_type == "rational_fdc_list":
        text = (
            f"{drug_name} is listed as a rational "
            f"fixed dose combination (FDC) by CDSCO."
        )

    else:

        parts = [
            f"Drug: {drug_name}.",
        ]

        if indication:
            parts.append(
                f"Indication: {indication}."
            )

        if approval_date:
            parts.append(
                f"Date of approval: {approval_date}."
            )

        if document_type == "fdc_approval_list":

            parts.append(
                "This fixed dose combination was "
                "listed as approved by DCG(I)."
            )

        elif document_type == "new_drug_approval_list":

            parts.append(
                "This new drug was listed as approved "
                "for marketing in India."
            )

        text = " ".join(parts)

    chunk_id = (
        f"fdc_{document_metadata.get('id', pdf_path.stem)}"
        f"_p{page_number:03d}"
        f"_r{row_number:04d}"
    )

    metadata = {
        "document_id": document_metadata.get(
            "id",
            pdf_path.stem,
        ),
        "document_type": document_type,
        "document_title": document_metadata.get(
            "title",
            pdf_path.stem,
        ),
        "source": document_metadata.get(
            "source",
            "CDSCO",
        ),
        "source_url": document_metadata.get(
            "source_url"
        ),
        "release_date": document_metadata.get(
            "release_date"
        ),
        "local_file": document_metadata.get(
            "local_file",
            str(pdf_path.relative_to(PROJECT_ROOT)),
        ),
        "page_number": page_number,
        "chunk_type": "table_row",

        # FDC-specific fields
        "drug_name": drug_name,
        "indication": indication or None,
        "date_of_approval": approval_date,
        "coverage_period": coverage_period,
        "fdc_or_new_drug": fdc_or_new_drug,

        # Useful traceability
        "serial_number": serial_number or None,
        "composition": composition or None,
        "row_number": row_number,
        "file_sha256": file_sha256,
    }

    return Chunk(
        chunk_id=chunk_id,
        text=text,
        metadata=metadata,
    )


# ============================================================
# TABLE DOCUMENT PROCESSING
# ============================================================

def process_table_document(
    pdf_path: Path,
    document_metadata: dict[str, Any],
    document_type: str,
) -> tuple[list[Chunk], dict[str, Any]]:
    """
    Process a tabular FDC/New Drug PDF.

    Returns (chunks, log_info) where log_info carries per-document
    statistics for the validation log.
    """

    chunks: list[Chunk] = []

    file_sha256 = calculate_file_hash(
        pdf_path
    )

    tables = extract_tables_from_pdf(
        pdf_path
    )

    log = {
        "tables_detected": len(tables),
        "rows_detected": 0,
        "rows_skipped_artifact": 0,
        "rows_skipped_no_drug": 0,
        "rows_skipped_no_mapping": 0,
        "chunks_created": 0,
    }

    # CRITICAL:
    # These remain outside the page/table loop.
    #
    # FDC documents frequently do not repeat headers.
    # Therefore later pages reuse this mapping.
    current_headers: Optional[list[Any]] = None
    column_mapping: Optional[dict[str, int]] = None

    row_counter = 0

    for table_info in tables:

        page_number = table_info["page_number"]
        table = table_info["table"]

        if not table:
            continue

        # find_header_row now returns (merged_header, first_row_idx)
        header, header_end_idx = find_header_row(table)

        if header is not None:

            current_headers = [
                clean_cell(cell)
                for cell in header
            ]

            column_mapping = map_columns(
                current_headers
            )

            # header_end_idx is the exclusive end of the header rows:
            # for a single-row header at index i -> start_index = i + 1
            # for a merged group of rows 0..end-1  -> start_index = end
            start_index = header_end_idx

        else:

            # Headerless continuation page.
            #
            # IMPORTANT:
            # Do NOT treat the first row as a header.
            # It is a valid data row.
            if column_mapping is None:
                log["rows_skipped_no_mapping"] += len(table)
                continue

            start_index = 0

        for raw_row in table[start_index:]:

            row = clean_table_row(
                raw_row
            )

            log["rows_detected"] += 1

            if looks_like_artifact_row(row):
                log["rows_skipped_artifact"] += 1
                continue

            # Skip repeated headers if pdfplumber happens
            # to extract one somewhere later.
            if is_header_row(row):
                log["rows_skipped_artifact"] += 1
                continue

            row_counter += 1

            chunk = create_row_chunk(
                pdf_path=pdf_path,
                document_metadata=document_metadata,
                document_type=document_type,
                page_number=page_number,
                row_number=row_counter,
                row=row,
                column_mapping=column_mapping,
                file_sha256=file_sha256,
            )

            if chunk is not None:
                chunks.append(chunk)
            else:
                log["rows_skipped_no_drug"] += 1

    log["chunks_created"] = len(chunks)
    return chunks, log


# ============================================================
# NARRATIVE / PROCEDURE CHUNKING
# ============================================================

SECTION_PATTERN = re.compile(
    r"^\s*(\d+(?:\.\d+)*)[\.\)]?\s+(.{3,})$"
)


def split_into_sections(
    pages: list[str],
) -> list[dict[str, Any]]:
    """
    Split OCR/text content into numbered sections.

    Used primarily for scanned FDC procedure documents.
    """

    sections = []

    current_number = None
    current_heading = None
    current_text: list[str] = []
    current_page = None

    def flush():

        nonlocal current_number
        nonlocal current_heading
        nonlocal current_text
        nonlocal current_page

        if not current_text:
            return

        body = clean_text(
            " ".join(current_text)
        )

        if not body:
            return

        sections.append(
            {
                "section_number": current_number,
                "section_heading": current_heading,
                "text": body,
                "page_number": current_page,
            }
        )

        current_number = None
        current_heading = None
        current_text = []
        current_page = None

    for page_number, page_text in enumerate(
        pages,
        start=1,
    ):

    
        lines = page_text.splitlines()

        for line in lines:

            line = clean_text(line)

            if not line:
                continue

            match = SECTION_PATTERN.match(line)

            if match:

                flush()

                current_number = match.group(1)
                current_heading = match.group(2)
                current_page = page_number

            else:

                if current_page is None:
                    current_page = page_number

                current_text.append(line)

    flush()

    return sections


def create_procedure_chunks(
    pdf_path: Path,
    document_metadata: dict[str, Any],
    pages: list[str],
    confidences: list[float],
) -> list[Chunk]:

    sections = split_into_sections(
        pages
    )

    chunks = []

    file_sha256 = calculate_file_hash(
        pdf_path
    )

    average_confidence = (
        sum(confidences) / len(confidences)
        if confidences
        else 0.0
    )

    for index, section in enumerate(
        sections,
        start=1,
    ):

        section_number = section.get(
            "section_number"
        )

        heading = section.get(
            "section_heading"
        )

        body = section.get(
            "text",
            "",
        )

        if not body:
            continue

        if heading:

            text = (
                f"Section {section_number}: "
                f"{heading}. "
                f"{body}"
            )

        else:

            text = body

        chunk_id = (
            f"fdc_{document_metadata.get('id', pdf_path.stem)}"
            f"_section_{index:04d}"
        )

        metadata = {
            "document_id": document_metadata.get(
                "id",
                pdf_path.stem,
            ),
            "document_type": "fdc_procedure",
            "document_title": document_metadata.get(
                "title",
                pdf_path.stem,
            ),
            "source": document_metadata.get(
                "source",
                "CDSCO",
            ),
            "source_url": document_metadata.get(
                "source_url"
            ),
            "release_date": document_metadata.get(
                "release_date"
            ),
            "local_file": document_metadata.get(
                "local_file",
                str(
                    pdf_path.relative_to(
                        PROJECT_ROOT
                    )
                ),
            ),
            "page_number": section.get(
                "page_number"
            ),
            "chunk_type": "section",

            "section_number": section_number,
            "section_heading": heading,

            "ocr_average_confidence": average_confidence,

            "file_sha256": file_sha256,
        }

        chunks.append(
            Chunk(
                chunk_id=chunk_id,
                text=text,
                metadata=metadata,
            )
        )

    return chunks


# ============================================================
# DOCUMENT PROCESSOR
# ============================================================

def process_fdc_document(
    pdf_path: Path,
    metadata_df: pd.DataFrame,
) -> tuple[list[Chunk], dict[str, Any]]:
    """
    Process one FDC/New Drug PDF.

    Returns (chunks, log_info).
    """

    metadata = metadata_for_file(
        metadata_df,
        pdf_path.name,
    )

    title = str(
        metadata.get(
            "title",
            pdf_path.stem,
        )
    )

    document_type = detect_document_type(
        title,
        pdf_path.name,
    )

    # --------------------------------------------------------
    # Procedure documents — OCR path
    # --------------------------------------------------------

    if document_type == "fdc_procedure":

        ocr_used = False
        confidence = 0.0

        cached = load_ocr_cache(pdf_path)

        if cached is not None:
            pages, confidences = cached
        else:
            ocr_used = True
            pages, confidences = ocr_pdf(pdf_path)
            save_ocr_cache(pdf_path, pages, confidences)

        if confidences:
            confidence = sum(confidences) / len(confidences)

        chunks = create_procedure_chunks(
            pdf_path=pdf_path,
            document_metadata=metadata,
            pages=pages,
            confidences=confidences,
        )

        log = {
            "document_type": document_type,
            "ocr_used": ocr_used,
            "ocr_confidence": round(confidence, 2),
            "chunks_created": len(chunks),
            "tables_detected": 0,
            "rows_detected": 0,
            "rows_skipped_artifact": 0,
            "rows_skipped_no_drug": 0,
            "rows_skipped_no_mapping": 0,
        }

        return chunks, log

    # --------------------------------------------------------
    # Table documents — pdfplumber path
    # --------------------------------------------------------

    chunks, log = process_table_document(
        pdf_path=pdf_path,
        document_metadata=metadata,
        document_type=document_type,
    )

    log["document_type"] = document_type
    log["ocr_used"] = False
    log["ocr_confidence"] = None

    return chunks, log


# ============================================================
# MAIN CHUNKING FUNCTION
# ============================================================

def chunk_fdc_documents() -> list[Chunk]:
    """
    Process all FDC/New Drug PDFs.

    Returns:
        list[Chunk]
    """

    if not FDC_DIR.exists():
        raise FileNotFoundError(
            f"FDC directory not found: {FDC_DIR}"
        )

    PROCESSED_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    metadata_df = load_metadata()

    pdf_files = sorted(
        FDC_DIR.glob("*.pdf")
    )

    print(f"FDC PDFs found: {len(pdf_files)}")

    all_chunks: list[Chunk] = []
    failures = []
    zero_chunk_docs = []

    for pdf_path in pdf_files:

        try:
            chunks, log = process_fdc_document(
                pdf_path,
                metadata_df,
            )

            all_chunks.extend(chunks)

            # Per-document log line
            doc_type = log.get("document_type", "?")
            n_chunks = log.get("chunks_created", 0)
            n_rows = log.get("rows_detected", 0)
            skipped = (
                log.get("rows_skipped_artifact", 0)
                + log.get("rows_skipped_no_drug", 0)
                + log.get("rows_skipped_no_mapping", 0)
            )
            ocr_str = (
                f" OCR={'yes' if log.get('ocr_used') else 'no'}"
                f" conf={log.get('ocr_confidence')}"
                if doc_type == "fdc_procedure"
                else f" tables={log.get('tables_detected',0)}"
                f" rows={n_rows} skipped={skipped}"
            )

            print(
                f"  [{doc_type}] {pdf_path.name[:70]}"
                f" -> {n_chunks} chunks{ocr_str}"
            )

            if n_chunks == 0:
                zero_chunk_docs.append(pdf_path.name)

        except Exception as exc:
            failures.append(
                {
                    "file": pdf_path.name,
                    "error": str(exc),
                }
            )
            print(f"  [FAIL] {pdf_path.name[:70]}: {exc}")

    print(f"\nTotal chunks: {len(all_chunks)}")
    print(f"Failures: {len(failures)}")
    print(f"Zero-chunk docs: {len(zero_chunk_docs)}")

    if zero_chunk_docs:
        print("  Zero-chunk docs:")
        for name in zero_chunk_docs:
            print(f"    - {name}")

    return all_chunks


# ============================================================
# JSON SERIALIZATION
# ============================================================

def save_chunks_to_json(
    chunks: list[Chunk],
    output_file: Path = CHUNKS_FILE,
) -> None:

    output_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    payload = [
        {
            "chunk_id": chunk.chunk_id,
            "text": chunk.text,
            "metadata": chunk.metadata,
        }
        for chunk in chunks
    ]

    output_file.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )


# ============================================================
# PUBLIC API
# ============================================================

def chunking() -> list[Chunk]:
    """
    Public entry point.

    This is the function the later retrieval/indexing
    pipeline can import.

    Example:

        from chunking_programs.fdc import chunking

        chunks = chunking()
    """

    return chunk_fdc_documents()


# ============================================================
# SCRIPT ENTRY POINT
# ============================================================

if __name__ == "__main__":

    chunks = chunking()

    save_chunks_to_json(
        chunks
    )

    print(
        f"\nGenerated {len(chunks)} FDC chunks."
    )

    print(
        f"Saved to: {CHUNKS_FILE}"
    )