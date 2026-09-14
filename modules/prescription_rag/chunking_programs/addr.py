"""
ADR OCR + Chunking for BharatRx

Pipeline:

    CDSCO ADR PDF
          ↓
    Render PDF page
          ↓
       Tesseract OCR
          ↓
     Clean OCR text
          ↓
    Combine page text
          ↓
    Attach metadata.csv
          ↓
    Create one Chunk per ADR PDF
          ↓
       list[Chunk]

ADR strategy:
    1 PDF = 1 semantic chunk

The resulting Chunk objects can later be passed to:
    - BM25 indexing
    - Embedding model
    - Vector database
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF
import pandas as pd
import pytesseract
from PIL import Image


# ============================================================
# PATHS
# ============================================================

# adr.py is located at:
#
# modules/
# └── prescription_rag/
#     └── chunking/
#         └── adr.py
#
# Therefore parents[1] = prescription_rag

PROJECT_ROOT = Path(__file__).resolve().parents[1]

ADR_DIR = PROJECT_ROOT / "data" / "cdsco" / "adr"

METADATA_FILE = ADR_DIR / "metadata.csv"

# OCR results will be cached here.
OCR_CACHE_DIR = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "adr_ocr"
)

# Final inspectable chunks.
CHUNKS_OUTPUT_FILE = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "adr_chunks.json"
)


# ============================================================
# OCR CONFIGURATION
# ============================================================

# 300 DPI gives Tesseract a reasonably high-resolution image.
OCR_DPI = 300

# Current ADR documents are English.
OCR_LANGUAGE = "eng"

# Tesseract page segmentation mode.
OCR_CONFIG = "--psm 6"


# ============================================================
# CHUNK DATA STRUCTURE
# ============================================================

@dataclass
class Chunk:
    """
    Common chunk structure.

    All four chunkers should eventually return
    this same type of object.
    """

    chunk_id: str
    text: str
    metadata: dict[str, Any]


# ============================================================
# TESSERACT CONFIGURATION
# ============================================================

def configure_tesseract() -> None:
    """
    Configure the Tesseract OCR executable.

    pytesseract is only the Python wrapper.
    The actual Tesseract OCR program must also be installed.
    """

    # --------------------------------------------------------
    # Option 1:
    # User explicitly provides Tesseract path.
    # --------------------------------------------------------

    configured_path = os.environ.get(
        "TESSERACT_CMD"
    )

    if configured_path:

        tesseract_path = Path(
            configured_path
        )

        if not tesseract_path.exists():

            raise FileNotFoundError(
                f"TESSERACT_CMD points to a file "
                f"that does not exist:\n"
                f"{tesseract_path}"
            )

        pytesseract.pytesseract.tesseract_cmd = (
            str(tesseract_path)
        )

        return

    # --------------------------------------------------------
    # Option 2:
    # Check common Windows installation paths.
    # --------------------------------------------------------

    possible_paths = [

        Path(
            r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        ),

        Path(
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"
        ),
    ]

    for path in possible_paths:

        if path.exists():

            pytesseract.pytesseract.tesseract_cmd = (
                str(path)
            )

            return

    # --------------------------------------------------------
    # Option 3:
    # Check if Tesseract is already in PATH.
    # --------------------------------------------------------

    try:

        pytesseract.get_tesseract_version()

        return

    except Exception:

        raise RuntimeError(
            "\nTesseract OCR was not found.\n\n"
            "Install Tesseract OCR on Windows.\n"
            "The common installation path is:\n\n"
            r"C:\Program Files\Tesseract-OCR\tesseract.exe"
            "\n\n"
            "Alternatively set the TESSERACT_CMD "
            "environment variable."
        )


# ============================================================
# OCR TEXT CLEANING
# ============================================================

def clean_ocr_text(text: str) -> str:
    """
    Perform conservative cleaning of OCR output.

    We do NOT attempt to medically correct OCR errors.

    The purpose is only to clean obvious formatting artifacts.
    """

    if not text:
        return ""

    # Normalize line endings.
    text = text.replace(
        "\r\n",
        "\n",
    )

    text = text.replace(
        "\r",
        "\n",
    )

    # Remove excessive spaces/tabs.
    text = re.sub(
        r"[ \t]+",
        " ",
        text,
    )

    # Remove whitespace surrounding newlines.
    text = re.sub(
        r"[ \t]*\n[ \t]*",
        "\n",
        text,
    )

    # Collapse more than two consecutive blank lines.
    text = re.sub(
        r"\n{3,}",
        "\n\n",
        text,
    )

    # Remove empty lines at the beginning/end.
    text = text.strip()

    return text


# ============================================================
# OCR ONE PAGE
# ============================================================

def ocr_page(
    page: fitz.Page,
) -> tuple[str, float | None]:
    """
    Render one PDF page and perform OCR.

    Returns:

        text
        average OCR confidence
    """

    # PDF points are based on 72 DPI.
    # Convert desired DPI to scaling factor.
    scale = OCR_DPI / 72

    matrix = fitz.Matrix(
        scale,
        scale,
    )

    # Render PDF page to an image.
    pixmap = page.get_pixmap(
        matrix=matrix,
        alpha=False,
    )

    # Convert rendered image into a Pillow Image.
    image = Image.frombytes(
        "RGB",
        [
            pixmap.width,
            pixmap.height,
        ],
        pixmap.samples,
    )

    # --------------------------------------------------------
    # OCR
    # --------------------------------------------------------

    text = pytesseract.image_to_string(
        image,
        lang=OCR_LANGUAGE,
        config=OCR_CONFIG,
    )

    # --------------------------------------------------------
    # OCR confidence
    # --------------------------------------------------------

    ocr_data = pytesseract.image_to_data(
        image,
        lang=OCR_LANGUAGE,
        config=OCR_CONFIG,
        output_type=pytesseract.Output.DICT,
    )

    confidences = []

    for confidence in ocr_data["conf"]:

        try:

            value = float(confidence)

            if value >= 0:
                confidences.append(value)

        except (
            ValueError,
            TypeError,
        ):

            continue

    if confidences:

        average_confidence = round(
            sum(confidences)
            / len(confidences),
            2,
        )

    else:

        average_confidence = None

    # Clean OCR text.
    text = clean_ocr_text(text)

    return (
        text,
        average_confidence,
    )


# ============================================================
# OCR ONE PDF
# ============================================================

def ocr_pdf(
    pdf_path: Path,
) -> dict[str, Any]:
    """
    OCR every page of one PDF.

    Returns:

    {
        "document_id": "001",
        "file_name": "...",
        "pages": [
            {
                "page_number": 1,
                "text": "...",
                "ocr_confidence": 91.5
            }
        ]
    }
    """

    document_id = (
        pdf_path.stem.split(
            "_",
            1,
        )[0]
    )

    pages = []

    with fitz.open(pdf_path) as document:

        total_pages = len(document)

        for page_number, page in enumerate(
            document,
            start=1,
        ):

            print(
                f"      OCR page "
                f"{page_number}/{total_pages}"
            )

            text, confidence = ocr_page(
                page
            )

            pages.append(
                {
                    "page_number": page_number,
                    "text": text,
                    "ocr_confidence": confidence,
                }
            )

    return {
        "document_id": document_id,
        "file_name": pdf_path.name,
        "pages": pages,
    }


# ============================================================
# OCR CACHE
# ============================================================

def get_cache_path(
    pdf_path: Path,
) -> Path:
    """
    Return the JSON file used to cache OCR results.
    """

    return (
        OCR_CACHE_DIR
        / f"{pdf_path.stem}.json"
    )


def load_cached_ocr(
    pdf_path: Path,
) -> dict[str, Any] | None:
    """
    Load cached OCR result if it exists.
    """

    cache_path = get_cache_path(
        pdf_path
    )

    if not cache_path.exists():
        return None

    try:

        with cache_path.open(
            "r",
            encoding="utf-8",
        ) as file:

            return json.load(file)

    except (
        json.JSONDecodeError,
        OSError,
    ):

        return None


def save_ocr_cache(
    pdf_path: Path,
    ocr_result: dict[str, Any],
) -> None:
    """
    Save OCR output to disk.
    """

    OCR_CACHE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    cache_path = get_cache_path(
        pdf_path
    )

    with cache_path.open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            ocr_result,
            file,
            ensure_ascii=False,
            indent=2,
        )


def get_ocr_for_pdf(
    pdf_path: Path,
) -> dict[str, Any]:
    """
    Get OCR result.

    If OCR was already performed:
        load cache

    Otherwise:
        run OCR
        save cache
    """

    cached_result = load_cached_ocr(
        pdf_path
    )

    if cached_result is not None:

        print(
            "      Using cached OCR"
        )

        return cached_result

    print(
        "      Running OCR..."
    )

    result = ocr_pdf(
        pdf_path
    )

    save_ocr_cache(
        pdf_path,
        result,
    )

    return result


# ============================================================
# LOAD ADR METADATA
# ============================================================

def load_metadata(
    metadata_file: Path,
) -> pd.DataFrame:
    """
    Load CDSCO ADR metadata.csv.
    """

    if not metadata_file.exists():

        raise FileNotFoundError(
            f"Metadata file not found:\n"
            f"{metadata_file}"
        )

    metadata = pd.read_csv(
        metadata_file,
        dtype=str,
    )

    # Remove accidental whitespace
    # from column names.
    metadata.columns = [
        column.strip()
        for column in metadata.columns
    ]

    return metadata


# ============================================================
# BUILD METADATA LOOKUP
# ============================================================

def build_metadata_lookup(
    metadata: pd.DataFrame,
) -> dict[str, dict[str, Any]]:
    """
    Convert metadata DataFrame into:

        document_id → metadata

    Example:

        {
            "001": {
                "id": "001",
                "drug_name": "Tranexamic Acid",
                "adr": "Back Pain",
                ...
            }
        }
    """

    lookup = {}

    for _, row in metadata.iterrows():

        row_dict = {}

        for key, value in row.to_dict().items():

            if pd.isna(value):

                row_dict[key] = None

            else:

                row_dict[key] = str(
                    value
                ).strip()

        document_id = row_dict.get(
            "id"
        )

        if not document_id:
            continue

        # Convert "1" → "001"
        if document_id.isdigit():

            document_id = document_id.zfill(
                3
            )

        lookup[document_id] = row_dict

    return lookup


# ============================================================
# COMBINE OCR PAGE TEXT
# ============================================================

def combine_page_text(
    ocr_result: dict[str, Any],
) -> tuple[
    str,
    list[dict[str, Any]],
]:
    """
    Combine all page text into one document.

    Page markers are retained so source-page
    information is not lost.
    """

    page_texts = []
    page_metadata = []

    for page in ocr_result["pages"]:

        page_number = page[
            "page_number"
        ]

        text = clean_ocr_text(
            page.get(
                "text",
                "",
            )
        )

        confidence = page.get(
            "ocr_confidence"
        )

        if text:

            page_texts.append(
                f"[Page {page_number}]\n"
                f"{text}"
            )

        page_metadata.append(
            {
                "page_number": page_number,
                "ocr_confidence": confidence,
            }
        )

    combined_text = "\n\n".join(
        page_texts
    )

    return (
        combined_text,
        page_metadata,
    )


# ============================================================
# FILE HASH
# ============================================================

def calculate_file_hash(
    file_path: Path,
) -> str:
    """
    Calculate SHA-256 hash of the PDF.

    This is useful for identifying exact duplicate files.

    We do NOT automatically remove duplicates here.
    """

    sha256 = hashlib.sha256()

    with file_path.open(
        "rb"
    ) as file:

        while True:

            block = file.read(
                1024 * 1024
            )

            if not block:
                break

            sha256.update(
                block
            )

    return sha256.hexdigest()


# ============================================================
# CREATE ADR CHUNK
# ============================================================

def create_adr_chunk(
    pdf_path: Path,
    ocr_result: dict[str, Any],
    metadata_lookup: dict[
        str,
        dict[str, Any],
    ],
) -> Chunk | None:
    """
    Convert one ADR PDF into one Chunk.

    Initial ADR strategy:

        1 PDF = 1 semantic chunk
    """

    document_id = (
        pdf_path.stem.split(
            "_",
            1,
        )[0]
    )

    if document_id.isdigit():

        document_id = document_id.zfill(
            3
        )

    # Get reliable structured metadata
    # from metadata.csv.
    csv_metadata = metadata_lookup.get(
        document_id,
        {},
    )

    # Combine OCR page text.
    text, page_metadata = (
        combine_page_text(
            ocr_result
        )
    )

    # Don't create an empty chunk.
    if not text:

        print(
            "      WARNING: OCR produced "
            "no text."
        )

        return None

    # --------------------------------------------------------
    # Average OCR confidence
    # --------------------------------------------------------

    confidences = [
        page["ocr_confidence"]
        for page in page_metadata
        if page["ocr_confidence"]
        is not None
    ]

    if confidences:

        average_confidence = round(
            sum(confidences)
            / len(confidences),
            2,
        )

    else:

        average_confidence = None

    # --------------------------------------------------------
    # File hash
    # --------------------------------------------------------

    file_hash = calculate_file_hash(
        pdf_path
    )

    # --------------------------------------------------------
    # Metadata
    # --------------------------------------------------------

    metadata = {

        "document_id": document_id,

        "document_type": "ADR",

        "document_title": pdf_path.stem,

        # These come from metadata.csv.
        "drug_name": csv_metadata.get(
            "drug_name"
        ),

        "adr_type": csv_metadata.get(
            "adr"
        ),

        "release_date": csv_metadata.get(
            "release_date"
        ),

        "source": csv_metadata.get(
            "source",
            "CDSCO",
        ),

        "source_url": csv_metadata.get(
            "source_url"
        ),

        "pdf_url": csv_metadata.get(
            "pdf_url"
        ),

        "local_file": str(
            pdf_path.relative_to(
                PROJECT_ROOT
            )
        ),

        "page_count": len(
            ocr_result["pages"]
        ),

        "ocr_average_confidence": (
            average_confidence
        ),

        "chunk_type": "adr_document",

        "file_sha256": file_hash,

        # Keep page-level provenance.
        "page_metadata": page_metadata,
    }

    return Chunk(

        chunk_id=f"adr_{document_id}",

        text=text,

        metadata=metadata,
    )


# ============================================================
# MAIN ADR CHUNKER
# ============================================================

def chunk_adr_documents(
    adr_dir: Path = ADR_DIR,
    metadata_file: Path = METADATA_FILE,
) -> list[Chunk]:
    """
    Process every ADR PDF.

    Returns:

        list[Chunk]
    """

    print()
    print("=" * 70)
    print("BHARATRX — ADR OCR + CHUNKING")
    print("=" * 70)

    print(
        f"ADR directory:\n{adr_dir}"
    )

    print(
        f"\nMetadata file:\n{metadata_file}"
    )

    print(
        f"\nOCR cache:\n{OCR_CACHE_DIR}"
    )

    print()

    # --------------------------------------------------------
    # Configure Tesseract
    # --------------------------------------------------------

    configure_tesseract()

    # --------------------------------------------------------
    # Load metadata
    # --------------------------------------------------------

    metadata = load_metadata(
        metadata_file
    )

    metadata_lookup = (
        build_metadata_lookup(
            metadata
        )
    )

    # --------------------------------------------------------
    # Find PDFs
    # --------------------------------------------------------

    if not adr_dir.exists():

        raise FileNotFoundError(
            f"ADR directory not found:\n"
            f"{adr_dir}"
        )

    pdf_files = sorted(
        adr_dir.glob("*.pdf")
    )

    print(
        f"Found {len(pdf_files)} ADR PDFs."
    )

    print()

    # --------------------------------------------------------
    # Process PDFs
    # --------------------------------------------------------

    chunks: list[Chunk] = []

    for index, pdf_path in enumerate(
        pdf_files,
        start=1,
    ):

        print(
            f"[{index}/{len(pdf_files)}] "
            f"{pdf_path.name}"
        )

        try:

            # PDF → OCR
            ocr_result = get_ocr_for_pdf(
                pdf_path
            )

            # OCR → Chunk
            chunk = create_adr_chunk(
                pdf_path=pdf_path,
                ocr_result=ocr_result,
                metadata_lookup=metadata_lookup,
            )

            if chunk is not None:

                chunks.append(
                    chunk
                )

                print(
                    f"      Created: "
                    f"{chunk.chunk_id}"
                )

            else:

                print(
                    "      Chunk not created."
                )

        except Exception as error:

            print(
                f"      ERROR: "
                f"{error}"
            )

        print()

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    print("=" * 70)
    print(
        f"Created {len(chunks)} chunks "
        f"from {len(pdf_files)} PDFs."
    )
    print("=" * 70)

    return chunks


# ============================================================
# SAVE CHUNKS
# ============================================================

def save_chunks_to_json(
    chunks: list[Chunk],
    output_file: Path,
) -> None:
    """
    Save chunks to JSON.

    This is mainly for:
        - debugging
        - inspecting OCR
        - validating metadata

    Later the same Chunk objects can be sent
    directly to BM25 and the vector DB.
    """

    output_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    data = [
        asdict(chunk)
        for chunk in chunks
    ]

    with output_file.open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=2,
        )

    print(
        f"\nSaved chunks to:\n"
        f"{output_file}"
    )


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    chunks = chunk_adr_documents()

    # Save chunks for inspection.
    save_chunks_to_json(
        chunks,
        CHUNKS_OUTPUT_FILE,
    )

    # --------------------------------------------------------
    # Show first chunk
    # --------------------------------------------------------

    if chunks:

        first_chunk = chunks[0]

        print()
        print("=" * 70)
        print("FIRST CHUNK")
        print("=" * 70)

        print(
            f"\nChunk ID:\n"
            f"{first_chunk.chunk_id}"
        )

        print(
            f"\nDrug:\n"
            f"{first_chunk.metadata.get('drug_name')}"
        )

        print(
            f"\nADR:\n"
            f"{first_chunk.metadata.get('adr_type')}"
        )

        print(
            f"\nRelease date:\n"
            f"{first_chunk.metadata.get('release_date')}"
        )

        print(
            f"\nPages:\n"
            f"{first_chunk.metadata.get('page_count')}"
        )

        print(
            f"\nOCR confidence:\n"
            f"{first_chunk.metadata.get('ocr_average_confidence')}"
        )

        print()
        print("OCR TEXT PREVIEW")
        print("-" * 70)

        print(
            first_chunk.text[:3000]
        )

        print("-" * 70)