"""
CDSCO Alert Chunker for BharatRx

Chunking strategy
-----------------
1. NSQ alerts:
   - Extract table rows
   - 1 alert row = 1 chunk

2. Spurious alerts:
   - Extract table rows
   - 1 alert row = 1 chunk

3. Theft / Circular / Corrigendum:
   - Extract text if available
   - Otherwise OCR with Tesseract
   - Split into narrative chunks

The output uses the same Chunk structure as adr.py.

No BM25, embeddings, vector DB, or LangGraph logic belongs here.
"""

import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

import fitz
import pandas as pd
import pytesseract
from PIL import Image


# ============================================================
# PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

ALERT_DIR = PROJECT_ROOT / "data" / "cdsco" / "alerts"
METADATA_FILE = ALERT_DIR / "metadata.csv"

PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
OCR_CACHE_DIR = PROCESSED_DIR / "alert_ocr"
CHUNKS_FILE = PROCESSED_DIR / "alert_chunks.json"

OCR_DPI = 300
OCR_LANGUAGE = "eng"
OCR_CONFIG = "--psm 6"


# ============================================================
# CHUNK OBJECT
# ============================================================

@dataclass
class Chunk:
    chunk_id: str
    text: str
    metadata: dict


# ============================================================
# TESSERACT
# ============================================================

def configure_tesseract():
    """
    Locate Tesseract automatically.

    On Windows, also checks the standard installation path.
    """

    env_path = os.environ.get("TESSERACT_CMD")

    if env_path and Path(env_path).exists():
        pytesseract.pytesseract.tesseract_cmd = env_path
        return env_path

    common_paths = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ]

    for path in common_paths:
        if Path(path).exists():
            pytesseract.pytesseract.tesseract_cmd = path
            return path

    # Let pytesseract find it through PATH
    try:
        version = pytesseract.get_tesseract_version()
        return "PATH:" + str(version)
    except Exception:
        raise RuntimeError(
            "Tesseract OCR was not found. "
            "Install Tesseract or set TESSERACT_CMD."
        )


# ============================================================
# TEXT CLEANING
# ============================================================

def clean_text(text: str) -> str:
    """
    General text cleanup.
    """

    if not text:
        return ""

    text = text.replace("\x00", " ")

    # Normalize line endings
    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")

    # Remove excessive whitespace
    text = re.sub(r"[ \t]+", " ", text)

    # Remove excessive blank lines
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)

    return text.strip()


def clean_cell(value) -> str:
    """
    Clean a table cell.

    Important for Alert tables because the structural analysis
    found multi-line cells and merged-cell extraction artifacts.
    """

    if value is None:
        return ""

    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass

    text = str(value)

    text = text.replace("\r", " ")
    text = text.replace("\n", " ")

    # Collapse whitespace
    text = re.sub(r"\s+", " ", text)

    return text.strip()


# ============================================================
# DOCUMENT TYPE
# ============================================================

def detect_alert_type(title: str, filename: str = "") -> str:
    """
    Detect the Alert document type from title/filename.

    Possible values:
        NSQ
        spurious
        theft
        circular
        corrigendum
        unknown
    """

    combined = f"{title} {filename}".lower()

    if "corrigendum" in combined:
        return "corrigendum"

    if "spurious" in combined:
        return "spurious"

    if "nsq" in combined:
        return "NSQ"

    if "theft" in combined or "stolen" in combined:
        return "theft"

    if "circular" in combined:
        return "circular"

    return "unknown"


def extract_alert_month(title: str) -> Optional[str]:
    """
    Try to extract a month/year from the document title.

    Examples:
        June 2025
        May 2025
        MAY-2025
    """

    if not title:
        return None

    patterns = [
        r"\b(January|February|March|April|May|June|July|August|"
        r"September|October|November|December)[\s\-]+(\d{4})\b",

        r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
        r"[\s\-]+(\d{4})\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, title, re.IGNORECASE)

        if match:
            return f"{match.group(1)} {match.group(2)}"

    return None


# ============================================================
# METADATA
# ============================================================

def load_metadata() -> pd.DataFrame:
    """
    Load Alert metadata.csv.

    Some PDFs in the alerts folder may not have corresponding
    metadata rows, so the chunker must tolerate missing metadata.
    """

    if not METADATA_FILE.exists():
        print(f"Warning: metadata file not found: {METADATA_FILE}")
        return pd.DataFrame()

    df = pd.read_csv(METADATA_FILE)

    return df


def build_metadata_lookup() -> dict:
    """
    Build lookup using zero-padded IDs.

    Example:
        1 -> 001
    """

    df = load_metadata()

    lookup = {}

    if df.empty:
        return lookup

    for _, row in df.iterrows():

        raw_id = row.get("id")

        if pd.isna(raw_id):
            continue

        try:
            document_id = f"{int(raw_id):03d}"
        except Exception:
            document_id = str(raw_id).strip()

        lookup[document_id] = {
            key: (
                None
                if pd.isna(value)
                else str(value).strip()
            )
            for key, value in row.to_dict().items()
        }

    return lookup


# ============================================================
# PDF TEXT EXTRACTION
# ============================================================

def extract_pdf_text(pdf_path: Path) -> list[dict]:
    """
    Extract selectable text page-by-page.

    Returns:
        [
            {
                "page_number": 1,
                "text": "..."
            }
        ]
    """

    pages = []

    with fitz.open(pdf_path) as doc:

        for page_number, page in enumerate(doc, start=1):

            text = page.get_text("text")

            pages.append({
                "page_number": page_number,
                "text": clean_text(text),
            })

    return pages


def pdf_has_useful_text(pages: list[dict], threshold: int = 100) -> bool:
    """
    Determine whether the PDF contains enough selectable text
    to avoid OCR.
    """

    total_chars = sum(
        len(page["text"])
        for page in pages
    )

    return total_chars >= threshold


# ============================================================
# OCR
# ============================================================

def ocr_page(page, page_number: int) -> dict:
    """
    OCR one PDF page.
    """

    zoom = OCR_DPI / 72

    matrix = fitz.Matrix(zoom, zoom)

    pix = page.get_pixmap(
        matrix=matrix,
        alpha=False
    )

    image = Image.frombytes(
        "RGB",
        [pix.width, pix.height],
        pix.samples
    )

    text = pytesseract.image_to_string(
        image,
        lang=OCR_LANGUAGE,
        config=OCR_CONFIG
    )

    # Calculate confidence
    data = pytesseract.image_to_data(
        image,
        lang=OCR_LANGUAGE,
        config=OCR_CONFIG,
        output_type=pytesseract.Output.DICT
    )

    confidences = []

    for confidence in data["conf"]:
        try:
            value = float(confidence)

            if value >= 0:
                confidences.append(value)

        except (ValueError, TypeError):
            continue

    average_confidence = (
        sum(confidences) / len(confidences)
        if confidences
        else 0.0
    )

    return {
        "page_number": page_number,
        "text": clean_text(text),
        "ocr_confidence": round(average_confidence, 2),
    }


def ocr_pdf(pdf_path: Path) -> dict:
    """
    OCR all pages in a PDF.
    """

    pages = []

    with fitz.open(pdf_path) as doc:

        for page_number, page in enumerate(doc, start=1):

            pages.append(
                ocr_page(page, page_number)
            )

    confidences = [
        page["ocr_confidence"]
        for page in pages
        if page["ocr_confidence"] > 0
    ]

    average_confidence = (
        sum(confidences) / len(confidences)
        if confidences
        else 0.0
    )

    return {
        "pages": pages,
        "average_confidence": round(
            average_confidence,
            2
        ),
    }


# ============================================================
# OCR CACHE
# ============================================================

def get_cache_path(pdf_path: Path) -> Path:
    return OCR_CACHE_DIR / f"{pdf_path.stem}.json"


def load_cached_ocr(pdf_path: Path) -> Optional[dict]:

    cache_path = get_cache_path(pdf_path)

    if not cache_path.exists():
        return None

    try:
        with open(
            cache_path,
            "r",
            encoding="utf-8"
        ) as file:
            return json.load(file)

    except Exception:
        return None


def save_ocr_cache(
    pdf_path: Path,
    ocr_result: dict
):

    OCR_CACHE_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    cache_path = get_cache_path(pdf_path)

    with open(
        cache_path,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            ocr_result,
            file,
            ensure_ascii=False,
            indent=2
        )


def get_ocr_for_pdf(pdf_path: Path) -> dict:

    cached = load_cached_ocr(pdf_path)

    if cached is not None:
        return cached

    configure_tesseract()

    result = ocr_pdf(pdf_path)

    save_ocr_cache(
        pdf_path,
        result
    )

    return result


# ============================================================
# TABLE EXTRACTION
# ============================================================

def extract_tables_from_pdf(pdf_path: Path) -> list[list[list]]:
    """
    Extract tables using pdfplumber.

    pdfplumber is imported lazily because it is only needed
    for tabular Alert documents.
    """

    try:
        import pdfplumber
    except ImportError:
        raise RuntimeError(
            "pdfplumber is required for Alert table extraction."
        )

    all_tables = []

    with pdfplumber.open(pdf_path) as pdf:

        for page in pdf.pages:

            tables = page.extract_tables()

            for table in tables:

                if table:
                    all_tables.append(table)

    return all_tables


# ============================================================
# TABLE HEADER DETECTION
# ============================================================

def normalize_header(header: str) -> str:
    """
    Normalize a table header for matching.
    """

    header = clean_cell(header).lower()

    header = re.sub(
        r"[^a-z0-9]+",
        " ",
        header
    )

    return header.strip()


def detect_table_type(table: list[list]) -> Optional[str]:
    """
    Determine whether a table is NSQ or Spurious based
    on its headers.
    """

    if not table:
        return None

    header_text = " ".join(
        normalize_header(cell)
        for cell in table[0]
        if cell
    )

    if (
        "batch" in header_text
        and "nsq" in header_text
    ):
        return "NSQ"

    if (
        "batch" in header_text
        and "spurious" in header_text
    ):
        return "spurious"

    if (
        "firm reply" in header_text
        or "drawn by" in header_text
    ):
        return "spurious"

    if (
        "reported by" in header_text
        and "batch" in header_text
    ):
        return "NSQ"

    return None


# ============================================================
# TABLE CLEANING
# ============================================================

def is_empty_row(row: list) -> bool:

    cleaned = [
        clean_cell(cell)
        for cell in row
    ]

    return not any(cleaned)


def looks_like_continuation_row(row: list) -> bool:
    """
    Detect rows created by merged/multi-line cells.

    Example:

    ['', '', '', '', '',
     'Sanand, Ahmedabad, India',
     '', '']

    Such a row should not become an independent Alert chunk.
    """

    cleaned = [
        clean_cell(cell)
        for cell in row
    ]

    non_empty_indices = [
        index
        for index, value in enumerate(cleaned)
        if value
    ]

    if len(non_empty_indices) != 1:
        return False

    # If the only value is not a serial number, it is likely
    # a continuation of the previous row.
    value = cleaned[non_empty_indices[0]]

    if re.fullmatch(r"\d+\.?", value):
        return False

    return True


def clean_table(
    table: list[list],
    previous_headers: Optional[list[str]] = None
) -> tuple[list[str], list[list[str]]]:
    """
    Clean a raw extracted table.

    Returns:
        headers
        rows
    """

    if not table:
        return [], []

    if previous_headers is not None:
        header = previous_headers
        start_idx = 0
    else:
        header = [
            clean_cell(cell)
            for cell in table[0]
        ]
        start_idx = 1

    rows = []

    for raw_row in table[start_idx:]:

        if is_empty_row(raw_row):
            continue

        cleaned_row = [
            clean_cell(cell)
            for cell in raw_row
        ]

        # Ignore obvious continuation/artifact rows here.
        # These can be handled more intelligently if required.
        if looks_like_continuation_row(raw_row):

            if rows:
                non_empty = [
                    value
                    for value in cleaned_row
                    if value
                ]

                if non_empty:

                    for index, value in enumerate(
                        cleaned_row
                    ):
                        if value and index < len(rows[-1]):

                            if rows[-1][index]:
                                rows[-1][index] += " " + value
                            else:
                                rows[-1][index] = value

                continue

        # Make row length equal to header length
        if len(cleaned_row) < len(header):

            cleaned_row.extend(
                [""] * (
                    len(header) - len(cleaned_row)
                )
            )

        elif len(cleaned_row) > len(header):

            cleaned_row = cleaned_row[:len(header)]

        rows.append(cleaned_row)

    return header, rows


# ============================================================
# COLUMN MAPPING
# ============================================================

def map_columns(
    headers: list[str],
    alert_type: str
) -> dict:
    """
    Map inconsistent CDSCO table headers to normalized
    BharatRx field names.
    """

    mapping = {}

    for index, header in enumerate(headers):

        h = normalize_header(header)

        if h in {"s no", "s no.", "serial no", "serial number"}:
            mapping["serial_number"] = index

        elif (
            "product" in h
            or "drug name" in h
            or "name of drug" in h
            or "name of drugs" in h
        ):
            mapping["drug_name"] = index

        elif "batch" in h:
            mapping["batch_number"] = index

        elif (
            "manufacturing date" in h
            or "date of manufacture" in h
        ):
            mapping["manufacturing_date"] = index

        elif (
            "expiry date" in h
            or "date of expiry" in h
        ):
            mapping["expiry_date"] = index

        elif "manufactured by" in h:
            mapping["manufacturer"] = index

        elif (
            "nsq result" in h
            or "reason for failure" in h
        ):
            mapping["nsq_result"] = index

        elif "reported by" in h:
            mapping["reporting_lab"] = index

        elif "drawn by" in h:
            mapping["drawn_by"] = index

        elif "firm" in h and "reply" in h:
            mapping["firm_reply"] = index

        elif "remarks" in h:
            mapping["remarks"] = index

    return mapping


def get_row_value(
    row: list[str],
    mapping: dict,
    field: str
) -> str:

    index = mapping.get(field)

    if index is None:
        return ""

    if index >= len(row):
        return ""

    return clean_cell(row[index])


# ============================================================
# DATE NORMALIZATION
# ============================================================

def normalize_date(value: str) -> Optional[str]:

    if not value:
        return None

    value = value.strip()

    formats = [
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%d.%m.%Y",
        "%d/%m/%y",
        "%d-%m-%y",
        "%d.%m.%y",
    ]

    for fmt in formats:

        try:
            date = pd.to_datetime(
                value,
                format=fmt
            )

            return date.strftime("%Y-%m-%d")

        except Exception:
            pass

    # Let pandas attempt flexible parsing
    try:

        date = pd.to_datetime(
            value,
            dayfirst=True
        )

        return date.strftime("%Y-%m-%d")

    except Exception:

        return value


# ============================================================
# HASH
# ============================================================

def calculate_file_hash(pdf_path: Path) -> str:

    sha256 = hashlib.sha256()

    with open(pdf_path, "rb") as file:

        while True:

            block = file.read(1024 * 1024)

            if not block:
                break

            sha256.update(block)

    return sha256.hexdigest()


# ============================================================
# TABLE ROW → CHUNK
# ============================================================

def create_table_chunk(
    pdf_path: Path,
    document_id: str,
    metadata: dict,
    alert_type: str,
    alert_month: Optional[str],
    row_number: int,
    headers: list[str],
    row: list[str],
    column_mapping: dict,
    page_number: Optional[int] = None,
) -> Chunk:

    drug_name = get_row_value(
        row,
        column_mapping,
        "drug_name"
    )

    batch_number = get_row_value(
        row,
        column_mapping,
        "batch_number"
    )

    manufacturer = get_row_value(
        row,
        column_mapping,
        "manufacturer"
    )

    manufacturing_date = normalize_date(
        get_row_value(
            row,
            column_mapping,
            "manufacturing_date"
        )
    )

    expiry_date = normalize_date(
        get_row_value(
            row,
            column_mapping,
            "expiry_date"
        )
    )

    nsq_result = get_row_value(
        row,
        column_mapping,
        "nsq_result"
    )

    reporting_lab = get_row_value(
        row,
        column_mapping,
        "reporting_lab"
    )

    drawn_by = get_row_value(
        row,
        column_mapping,
        "drawn_by"
    )

    firm_reply = get_row_value(
        row,
        column_mapping,
        "firm_reply"
    )

    remarks = get_row_value(
        row,
        column_mapping,
        "remarks"
    )

    # --------------------------------------------------------
    # Build self-contained searchable text
    # --------------------------------------------------------

    text_parts = [
        f"Alert Type: {alert_type}",
    ]

    if alert_month:
        text_parts.append(
            f"Alert Month: {alert_month}"
        )

    if drug_name:
        text_parts.append(
            f"Product/Drug Name: {drug_name}"
        )

    if batch_number:
        text_parts.append(
            f"Batch Number: {batch_number}"
        )

    if manufacturing_date:
        text_parts.append(
            f"Manufacturing Date: {manufacturing_date}"
        )

    if expiry_date:
        text_parts.append(
            f"Expiry Date: {expiry_date}"
        )

    if manufacturer:
        text_parts.append(
            f"Manufactured By: {manufacturer}"
        )

    if nsq_result:
        if alert_type == "spurious":
            text_parts.append(
                f"Reason for Failure: {nsq_result}"
            )
        else:
            text_parts.append(
                f"NSQ Result: {nsq_result}"
            )

    if reporting_lab:
        text_parts.append(
            f"Reported By Laboratory: {reporting_lab}"
        )

    if drawn_by:
        text_parts.append(
            f"Drawn By: {drawn_by}"
        )

    if firm_reply:
        text_parts.append(
            f"Firm's Reply: {firm_reply}"
        )

    if remarks:
        text_parts.append(
            f"Remarks: {remarks}"
        )

    text = "\n".join(text_parts)

    # --------------------------------------------------------
    # Metadata
    # --------------------------------------------------------

    chunk_metadata = {
        "document_id": document_id,
        "document_type": (
            "nsq_alert"
            if alert_type == "NSQ"
            else f"{alert_type}_alert"
        ),

        "document_title": metadata.get(
            "title"
        ),

        "alert_type": alert_type,
        "alert_month": alert_month,

        "drug_name": drug_name or None,
        "batch_number": batch_number or None,
        "manufacturer": manufacturer or None,

        "manufacturing_date": (
            manufacturing_date
        ),

        "expiry_date": expiry_date,

        "nsq_result": nsq_result or None,
        "reporting_lab": reporting_lab or None,

        "drawn_by": drawn_by or None,
        "firm_reply": firm_reply or None,
        "remarks": remarks or None,

        "row_number": row_number,
        "page_number": page_number,

        "chunk_type": "table_row",

        "source": metadata.get(
            "source",
            "CDSCO"
        ),

        "source_url": metadata.get(
            "source_url"
        ),

        "pdf_url": metadata.get(
            "pdf_url"
        ),

        "release_date": metadata.get(
            "release_date"
        ),

        "local_file": metadata.get(
            "local_file"
        ),

        "file_sha256": calculate_file_hash(
            pdf_path
        ),
    }

    return Chunk(
        chunk_id=(
            f"alert_{document_id}"
            f"_row_{row_number:03d}"
        ),

        text=text,

        metadata=chunk_metadata
    )


# ============================================================
# NARRATIVE CHUNKING
# ============================================================

def split_narrative_text(
    pages: list[dict],
    max_chars: int = 4000
) -> list[dict]:
    """
    Split narrative Alert documents into reasonably sized
    paragraph chunks.

    Page boundaries are preserved.
    """

    chunks = []

    for page in pages:

        page_number = page["page_number"]
        text = clean_text(page["text"])

        if not text:
            continue

        paragraphs = re.split(
            r"\n\s*\n",
            text
        )

        current = ""

        for paragraph in paragraphs:

            paragraph = clean_text(
                paragraph
            )

            if not paragraph:
                continue

            if (
                current
                and len(current) + len(paragraph) + 2
                > max_chars
            ):

                chunks.append({
                    "page_number": page_number,
                    "text": current.strip(),
                })

                current = paragraph

            else:

                if current:
                    current += "\n\n"

                current += paragraph

        if current:
            chunks.append({
                "page_number": page_number,
                "text": current.strip(),
            })

    return chunks


def create_narrative_chunks(
    pdf_path: Path,
    document_id: str,
    metadata: dict,
    alert_type: str,
    pages: list[dict],
    ocr_confidence: Optional[float] = None,
) -> list[Chunk]:

    alert_month = extract_alert_month(
        metadata.get("title", "")
    )

    narrative_parts = split_narrative_text(
        pages
    )

    file_hash = calculate_file_hash(
        pdf_path
    )

    chunks = []

    for index, item in enumerate(
        narrative_parts,
        start=1
    ):

        text = item["text"]

        chunk_text = (
            f"Alert Type: {alert_type}\n"
        )

        if alert_month:
            chunk_text += (
                f"Alert Month: {alert_month}\n"
            )

        chunk_text += (
            f"\n{text}"
        )

        chunk_metadata = {
            "document_id": document_id,

            "document_type": (
                f"{alert_type}_alert"
            ),

            "document_title": metadata.get(
                "title"
            ),

            "alert_type": alert_type,
            "alert_month": alert_month,

            "page_number": item[
                "page_number"
            ],

            "chunk_type": "paragraph",

            "ocr_average_confidence": (
                ocr_confidence
            ),

            "source": metadata.get(
                "source",
                "CDSCO"
            ),

            "source_url": metadata.get(
                "source_url"
            ),

            "pdf_url": metadata.get(
                "pdf_url"
            ),

            "release_date": metadata.get(
                "release_date"
            ),

            "local_file": metadata.get(
                "local_file"
            ),

            "file_sha256": file_hash,
        }

        chunks.append(
            Chunk(
                chunk_id=(
                    f"alert_{document_id}"
                    f"_chunk_{index:03d}"
                ),

                text=chunk_text,

                metadata=chunk_metadata
            )
        )

    return chunks


# ============================================================
# TABLE ALERT PROCESSING
# ============================================================

def process_table_alert(
    pdf_path: Path,
    document_id: str,
    metadata: dict,
    alert_type: str,
) -> list[Chunk]:

    tables = extract_tables_from_pdf(
        pdf_path
    )

    alert_month = extract_alert_month(
        metadata.get("title", "")
    )

    chunks = []

    global_row_number = 0
    current_headers = None
    current_mapping = None
    current_detected_type = None

    for table in tables:

        if not table:
            continue

        temp_headers = [clean_cell(cell) for cell in table[0]] if table else []
        temp_type = detect_table_type(table) or alert_type
        temp_mapping = map_columns(temp_headers, temp_type)

        if "drug_name" in temp_mapping and "batch_number" in temp_mapping:
            current_detected_type = temp_type
            current_headers = temp_headers
            current_mapping = temp_mapping
            headers, rows = clean_table(table, previous_headers=None)
        else:
            if current_mapping is None:
                continue
            headers, rows = clean_table(table, previous_headers=current_headers)

        for row in rows:

            drug_name = get_row_value(
                row,
                current_mapping,
                "drug_name"
            )

            batch_number = get_row_value(
                row,
                current_mapping,
                "batch_number"
            )

            # Avoid accidental header/artifact rows
            if (
                not drug_name
                and not batch_number
            ):
                continue

            global_row_number += 1

            chunk = create_table_chunk(
                pdf_path=pdf_path,
                document_id=document_id,
                metadata=metadata,
                alert_type=current_detected_type,
                alert_month=alert_month,
                row_number=global_row_number,
                headers=current_headers,
                row=row,
                column_mapping=current_mapping,
            )

            chunks.append(chunk)

    return chunks


# ============================================================
# SINGLE DOCUMENT PROCESSING
# ============================================================

def process_alert_document(
    pdf_path: Path,
    metadata_lookup: dict,
) -> list[Chunk]:

    # ----------------------------------------------------------------
    # Build a document_id that is UNIQUE per file.
    #
    # Root cause of the duplicate-ID bug:
    #   Multiple PDFs in the alerts folder share the same numeric
    #   prefix (e.g. both 005_STATE_NSQ… and 005_CDSCO_NSQ… map to
    #   document_id "005"), so every chunk generated from them gets
    #   the same ID (alert_005_row_001, alert_005_row_002, …).
    #
    # Fix:
    #   1. Extract the leading zero-padded numeric prefix for the
    #      metadata lookup (unchanged behaviour).
    #   2. Build a slug from the *full* filename stem and use THAT
    #      as the document_id embedded in every chunk_id.
    #
    # Examples:
    #   005_CDSCO NSQ ALERT FOR THE MONTH OF June 2025.pdf
    #     → numeric prefix (for metadata) : "005"
    #     → document_id (for chunk IDs)   : "005_cdsco_nsq_alert_for_the_month_of_june_2025"
    #
    #   005_STATE NSQ ALERT FOR THE MONTH OF June 2025.pdf
    #     → numeric prefix (for metadata) : "005"
    #     → document_id (for chunk IDs)   : "005_state_nsq_alert_for_the_month_of_june_2025"
    # ----------------------------------------------------------------

    # Step 1: numeric prefix → metadata lookup key (keep existing logic)
    match = re.match(r"(\d+)_", pdf_path.name)

    if match:
        numeric_prefix = match.group(1)
        try:
            numeric_prefix = f"{int(numeric_prefix):03d}"
        except Exception:
            pass
    else:
        numeric_prefix = pdf_path.stem

    # Step 2: full-stem slug → globally unique chunk-ID namespace
    #   - lowercase the stem
    #   - replace any run of non-alphanumeric characters with a single "_"
    #   - strip leading/trailing underscores
    slug = re.sub(r"[^a-z0-9]+", "_", pdf_path.stem.lower()).strip("_")
    document_id = slug

    metadata = metadata_lookup.get(
        numeric_prefix,
        {}
    )

    title = metadata.get(
        "title",
        pdf_path.stem
    )

    alert_type = detect_alert_type(
        title,
        pdf_path.name
    )

    # --------------------------------------------------------
    # NSQ / Spurious → table row chunking
    # --------------------------------------------------------

    if alert_type in {
        "NSQ",
        "spurious",
    }:

        chunks = process_table_alert(
            pdf_path,
            document_id,
            metadata,
            alert_type
        )

        if chunks:
            return chunks

        # If table extraction fails, fall back
        # to text/OCR rather than losing the document.

    # --------------------------------------------------------
    # Narrative → text/OCR
    # --------------------------------------------------------

    pages = extract_pdf_text(
        pdf_path
    )

    if pdf_has_useful_text(pages):

        return create_narrative_chunks(
            pdf_path=pdf_path,
            document_id=document_id,
            metadata=metadata,
            alert_type=alert_type,
            pages=pages,
        )

    # OCR fallback
    ocr_result = get_ocr_for_pdf(
        pdf_path
    )

    return create_narrative_chunks(
        pdf_path=pdf_path,
        document_id=document_id,
        metadata=metadata,
        alert_type=alert_type,
        pages=ocr_result["pages"],
        ocr_confidence=ocr_result[
            "average_confidence"
        ],
    )


# ============================================================
# MAIN CHUNKING FUNCTION
# ============================================================

def chunk_alert_documents() -> list[Chunk]:
    """
    Process all Alert PDFs.

    Returns:
        list[Chunk]
    """

    if not ALERT_DIR.exists():
        raise FileNotFoundError(
            f"Alert directory not found: {ALERT_DIR}"
        )

    metadata_lookup = (
        build_metadata_lookup()
    )

    pdf_files = sorted(
        ALERT_DIR.glob("*.pdf")
    )

    print(
        f"Alert PDFs found: {len(pdf_files)}"
    )

    all_chunks = []

    failures = []

    for index, pdf_path in enumerate(
        pdf_files,
        start=1
    ):

        print(
            f"[{index}/{len(pdf_files)}] "
            f"{pdf_path.name}"
        )

        try:

            chunks = process_alert_document(
                pdf_path,
                metadata_lookup
            )

            all_chunks.extend(chunks)

            print(
                f"    → {len(chunks)} chunks"
            )

        except Exception as error:

            failures.append({
                "file": pdf_path.name,
                "error": str(error),
            })

            print(
                f"    ERROR: {error}"
            )

    print()
    print(
        f"Total chunks created: "
        f"{len(all_chunks)}"
    )

    print(
        f"Failures: {len(failures)}"
    )

    if failures:

        print("\nFailures:")

        for failure in failures:

            print(
                f"  {failure['file']}: "
                f"{failure['error']}"
            )

    return all_chunks


# ============================================================
# SAVE
# ============================================================

def save_chunks_to_json(
    chunks: list[Chunk],
    output_path: Path = CHUNKS_FILE,
):

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    data = [
        asdict(chunk)
        for chunk in chunks
    ]

    with open(
        output_path,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=2
        )

    print(
        f"Saved {len(chunks)} chunks to:"
        f"\n{output_path}"
    )


# ============================================================
# PUBLIC API
# ============================================================

def chunking() -> list[Chunk]:
    """
    Public chunking interface.

    This matches the interface we want for the
    other BharatRx chunkers.
    """

    return chunk_alert_documents()


# ============================================================
# SCRIPT ENTRY POINT
# ============================================================

if __name__ == "__main__":

    chunks = chunking()

    save_chunks_to_json(
        chunks
    )

    # Preview
    print("\n--- First 3 chunks ---")

    for chunk in chunks[:3]:

        print(
            f"\nChunk ID: {chunk.chunk_id}"
        )

        print(
            chunk.text[:1000]
        )

        print(
            "\nMetadata:"
        )

        print(
            json.dumps(
                chunk.metadata,
                indent=2,
                ensure_ascii=False
            )
        )