"""
CDSCO Pharmacovigilance Chunker
--------------------------------
Document-specific chunker for:
    - PSUR Guidance
    - Pharmacovigilance Guidance
    - Recall / Rapid Alert Guidelines
    - 2025 New Drug Approval List

Public API:
    from pharmacovigilance import chunking
    chunks = chunking()

The chunker intentionally does NOT use OCR because the inspected PV PDFs
are text PDFs. Guidance documents are chunked by numbered sections/subsections.
The 2025 New Drug table reuses the existing FDC chunker's table parser when
available.

Output:
    data/processed/pv_chunks.json
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional

import fitz  # PyMuPDF


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]

PV_DIR = PROJECT_ROOT / "data" / "cdsco" / "pharmacovigilance"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
OUTPUT_FILE = PROCESSED_DIR / "pv_chunks.json"


# ---------------------------------------------------------------------------
# Unified chunk structure
# ---------------------------------------------------------------------------

@dataclass
class Chunk:
    chunk_id: str
    text: str
    metadata: dict[str, Any]


# ---------------------------------------------------------------------------
# Document identification
# ---------------------------------------------------------------------------

def normalize_filename(filename: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", filename.lower()).strip()


def detect_document_type(filename: str) -> str:
    """
    Classify the inspected PV documents into stable parser categories.
    """
    name = normalize_filename(filename)

    if "recall" in name or "rapid" in name:
        return "recall_rapid_alert"

    if "new drugs" in name or "new drug" in name:
        return "new_drug_approval_list"

    if "psur" in name:
        return "psur_guidance"

    if "vaccine" in name:
        return "pv_guidance_vaccines"

    if "pv guidance" in name or "pv guidancedoc" in name:
        return "pv_guidance"

    return "pv_guidance"


# ---------------------------------------------------------------------------
# Text cleaning
# ---------------------------------------------------------------------------

RUNNING_HEADER_PATTERNS = [
    r"^central drugs standard control organization$",
    r"^central drugs standard control organisation$",
    r"^central drugs standard control",
    r"^cdsco$",
]


def clean_line(line: str) -> str:
    line = line.replace("\xa0", " ")
    line = re.sub(r"[ \t]+", " ", line)
    return line.strip()


def is_running_header(line: str) -> bool:
    normalized = re.sub(r"[^a-z]+", " ", line.lower()).strip()

    for pattern in RUNNING_HEADER_PATTERNS:
        if re.search(pattern, normalized):
            return True

    return False


def clean_text(text: str) -> str:
    """
    Conservative cleaning. Do not aggressively rewrite source text because
    regulatory wording must be preserved.
    """
    lines = []

    for raw_line in text.splitlines():
        line = clean_line(raw_line)

        if not line:
            continue

        if is_running_header(line):
            continue

        lines.append(line)

    return "\n".join(lines).strip()


# ---------------------------------------------------------------------------
# PDF extraction
# ---------------------------------------------------------------------------

def extract_pdf_pages(pdf_path: Path) -> list[dict[str, Any]]:
    """
    Extract normal text from each PDF page using PyMuPDF.

    The structure investigation confirmed that the PV guidance PDFs are
    single-column and normal page.get_text() reading order is sufficient.
    """
    pages: list[dict[str, Any]] = []

    with fitz.open(pdf_path) as doc:
        for page_number, page in enumerate(doc, start=1):
            raw_text = page.get_text("text")
            text = clean_text(raw_text)

            pages.append(
                {
                    "page_number": page_number,
                    "text": text,
                }
            )

    return pages


# ---------------------------------------------------------------------------
# Hashing / duplicate detection
# ---------------------------------------------------------------------------

def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)

    return digest.hexdigest()


# ---------------------------------------------------------------------------
# Heading detection
# ---------------------------------------------------------------------------

# Confirmed structure:
#   1.0 Introduction
#   1.1 Objective
#   1.1.1 ...
#
# The bold requirement is important because ordinary table cells can contain
# values such as "1940." which otherwise look like numbered headings.

SECTION_NUMBER_RE = re.compile(
    r"^\s*(\d+(?:\.\d+)+)\s*[\.\)]?\s*(.*)$"
)

# Some documents may use a top-level "1." form.
SIMPLE_SECTION_NUMBER_RE = re.compile(
    r"^\s*(\d+)\s*[\.\)]\s*(.+)$"
)


def get_bold_lines(page: fitz.Page) -> list[dict[str, Any]]:
    """
    Extract visually meaningful lines with a bold-font signal.

    Each returned item contains:
        text
        page_number
        bold
        max_font_size
    """
    results: list[dict[str, Any]] = []

    blocks = page.get_text("dict").get("blocks", [])

    for block in blocks:
        if block.get("type") != 0:
            continue

        for line in block.get("lines", []):
            spans = line.get("spans", [])
            if not spans:
                continue

            text = clean_line("".join(span.get("text", "") for span in spans))
            if not text:
                continue

            bold = any(
                bool(span.get("flags", 0) & 16)
                or "bold" in str(span.get("font", "")).lower()
                for span in spans
            )

            max_font_size = max(
                float(span.get("size", 0.0)) for span in spans
            )

            results.append(
                {
                    "text": text,
                    "bold": bold,
                    "max_font_size": max_font_size,
                }
            )

    return results


def numbered_heading_match(text: str) -> Optional[re.Match[str]]:
    """
    Match decimal section numbering.
    """
    match = SECTION_NUMBER_RE.match(text)
    if match:
        return match

    return SIMPLE_SECTION_NUMBER_RE.match(text)


def is_heading_candidate(text: str, bold: bool) -> bool:
    """
    Confirmed heading signal:
        numbered + bold

    Font size is intentionally not used as the primary criterion.
    """
    if not bold:
        return False

    if is_running_header(text):
        return False

    return numbered_heading_match(text) is not None


def heading_parts(text: str) -> tuple[Optional[str], str]:
    """
    Return (section_number, heading_text).
    """
    match = numbered_heading_match(text)

    if not match:
        return None, text.strip()

    number = match.group(1).strip()
    title = match.group(2).strip()

    return number, title


# ---------------------------------------------------------------------------
# Multi-line heading handling
# ---------------------------------------------------------------------------

@dataclass
class DetectedHeading:
    section_number: str
    heading: str
    page_number: int
    line_index: int


def detect_headings_from_page(
    page: fitz.Page,
    page_number: int,
) -> list[DetectedHeading]:
    """
    Detect bold numbered headings and join adjacent bold lines when the
    heading continues on the next line.

    Example confirmed in the source:
        8.0 tiMe lines...
        sYsteM & raPiD alert:

    becomes one heading.
    """
    lines = get_bold_lines(page)
    headings: list[DetectedHeading] = []

    i = 0

    while i < len(lines):
        current = lines[i]
        text = current["text"]

        if not is_heading_candidate(text, current["bold"]):
            i += 1
            continue

        section_number, title = heading_parts(text)

        if not section_number:
            i += 1
            continue

        title_parts = [title] if title else []

        j = i + 1

        while j < len(lines):
            nxt = lines[j]

            # Continuation must be bold and must NOT itself begin a new
            # numbered section.
            if not nxt["bold"]:
                break

            next_text = nxt["text"]

            if numbered_heading_match(next_text):
                break

            if is_running_header(next_text):
                j += 1
                continue

            title_parts.append(next_text)
            j += 1

        headings.append(
            DetectedHeading(
                section_number=section_number,
                heading=" ".join(part for part in title_parts if part).strip(),
                page_number=page_number,
                line_index=i,
            )
        )

        i = max(j, i + 1)

    return headings


# ---------------------------------------------------------------------------
# More reliable section extraction
# ---------------------------------------------------------------------------

def detect_heading_lines(page: fitz.Page) -> list[tuple[int, str, str]]:
    """
    Return heading positions using the page's actual text lines.

    Output:
        (line_index, section_number, heading_text)

    This function works from get_text("dict") so bold information is retained.
    """
    blocks = page.get_text("dict").get("blocks", [])

    lines: list[dict[str, Any]] = []

    for block in blocks:
        if block.get("type") != 0:
            continue

        for line in block.get("lines", []):
            spans = line.get("spans", [])
            if not spans:
                continue

            text = clean_line("".join(span.get("text", "") for span in spans))

            if not text:
                continue

            bold = any(
                bool(span.get("flags", 0) & 16)
                or "bold" in str(span.get("font", "")).lower()
                for span in spans
            )

            lines.append(
                {
                    "text": text,
                    "bold": bold,
                }
            )

    headings: list[tuple[int, str, str]] = []
    i = 0

    while i < len(lines):
        current = lines[i]

        if not is_heading_candidate(current["text"], current["bold"]):
            i += 1
            continue

        number, title = heading_parts(current["text"])

        if number is None:
            i += 1
            continue

        title_parts = [title] if title else []
        j = i + 1

        # Join adjacent bold non-numbered lines.
        while j < len(lines):
            nxt = lines[j]

            if not nxt["bold"]:
                break

            if numbered_heading_match(nxt["text"]):
                break

            if is_running_header(nxt["text"]):
                j += 1
                continue

            title_parts.append(nxt["text"])
            j += 1

        heading_title = " ".join(
            part.strip() for part in title_parts if part.strip()
        ).strip()

        headings.append(
            (
                i,
                number,
                heading_title,
            )
        )

        i = max(j, i + 1)

    return headings


def extract_page_lines(page: fitz.Page) -> list[str]:
    """
    Extract normal text lines in PyMuPDF's confirmed reading order.
    """
    text = page.get_text("text")

    result = []

    for raw_line in text.splitlines():
        line = clean_line(raw_line)

        if not line:
            continue

        if is_running_header(line):
            continue

        result.append(line)

    return result


# ---------------------------------------------------------------------------
# Heading hierarchy
# ---------------------------------------------------------------------------

def section_level(section_number: str) -> int:
    """
    1.0       -> 2
    1.1       -> 2
    1.1.1     -> 3
    10.0      -> 2
    """
    return len(section_number.split("."))


def parent_section_number(section_number: str) -> Optional[str]:
    parts = section_number.split(".")

    if len(parts) <= 2:
        return None

    return ".".join(parts[:-1])


# ---------------------------------------------------------------------------
# Guidance / recall section parser
# ---------------------------------------------------------------------------

def parse_sections(
    pdf_path: Path,
    document_id: str,
    document_type: str,
) -> list[Chunk]:
    """
    Parse a guidance/recall PDF into section/subsection chunks.

    Each chunk starts at a detected numbered bold heading and continues until
    the next detected heading.

    Page boundaries are preserved in metadata.
    """
    chunks: list[Chunk] = []
    # Track emitted chunk_ids within this document so collisions from
    # repeated section numbers are caught and disambiguated.
    _seen_ids: set[str] = set()

    with fitz.open(pdf_path) as doc:
        # Build one continuous cleaned text representation while retaining
        # page boundaries.
        page_lines: list[tuple[int, str]] = []

        for page_number, page in enumerate(doc, start=1):
            for line in extract_page_lines(page):
                page_lines.append((page_number, line))

        # Detect headings from the same page representation.
        heading_positions: list[tuple[int, str, str, int]] = []

        global_index = 0

        for page_number, page in enumerate(doc, start=1):
            lines = extract_page_lines(page)

            headings = detect_heading_lines(page)

            for line_index, number, title in headings:
                # Map page-local line index into global line index.
                heading_positions.append(
                    (
                        global_index + line_index,
                        number,
                        title,
                        page_number,
                    )
                )

            global_index += len(lines)

        # Sort in document order.
        heading_positions.sort(key=lambda item: item[0])

        if not heading_positions:
            return create_fallback_document_chunk(
                pdf_path=pdf_path,
                document_id=document_id,
                document_type=document_type,
                page_lines=page_lines,
            )

        for idx, heading in enumerate(heading_positions):
            start_index, section_number, title, start_page = heading

            if idx + 1 < len(heading_positions):
                end_index = heading_positions[idx + 1][0]
            else:
                end_index = len(page_lines)

            body_items = page_lines[start_index + 1:end_index]

            body_text = "\n".join(
                text for _, text in body_items
            ).strip()

            heading_text = (
                f"{section_number} {title}".strip()
            )

            full_text = heading_text

            if body_text:
                full_text += "\n\n" + body_text

            if not full_text.strip():
                continue

            end_page = (
                body_items[-1][0]
                if body_items
                else start_page
            )

            parent = parent_section_number(section_number)

            metadata = {
                "document_id": document_id,
                "document_type": document_type,
                "document_title": pdf_path.stem,
                "source": "CDSCO",
                "source_url": "",
                "release_date": "",
                "local_file": str(pdf_path),
                "page_number": start_page,
                "page_start": start_page,
                "page_end": end_page,
                "chunk_type": "section",
                "section_number": section_number,
                "section_heading": title,
                "parent_section": parent,
                "section_level": section_level(section_number),
                "sha256": sha256_file(pdf_path),
            }

            # Build a base chunk_id and disambiguate with page number if the
            # same section_number appears more than once in this document.
            # This handles:
            #   (a) inline numbered lists ("1.", "2.") that are bold and
            #       match the heading pattern — they reuse small integers
            #       like 1, 2, 3 that also appear as real top-level sections.
            #   (b) source documents that genuinely reuse section numbers
            #       (e.g. 4.2.3 appears twice with different headings).
            # The section_number value in metadata is never changed; only
            # the chunk_id gains a _p{page} suffix when necessary.
            base_id = (
                f"pv_{document_id}_section_"
                f"{section_number.replace('.', '_')}"
            )

            if base_id not in _seen_ids:
                chunk_id = base_id
            else:
                chunk_id = f"{base_id}_p{start_page}"
                # If even the page-qualified id collides (same section number
                # on the same page, e.g. 4.6.3.2 twice on page 71), add an
                # incrementing counter.
                counter = 2
                while chunk_id in _seen_ids:
                    chunk_id = f"{base_id}_p{start_page}_{counter}"
                    counter += 1

            _seen_ids.add(chunk_id)

            chunks.append(
                Chunk(
                    chunk_id=chunk_id,
                    text=full_text,
                    metadata=metadata,
                )
            )

    return chunks


def create_fallback_document_chunk(
    pdf_path: Path,
    document_id: str,
    document_type: str,
    page_lines: list[tuple[int, str]],
) -> list[Chunk]:
    """
    Safety fallback for an unexpected document with no detectable headings.
    """
    text = "\n".join(line for _, line in page_lines).strip()

    if not text:
        return []

    pages = [page for page, _ in page_lines]

    metadata = {
        "document_id": document_id,
        "document_type": document_type,
        "document_title": pdf_path.stem,
        "source": "CDSCO",
        "source_url": "",
        "release_date": "",
        "local_file": str(pdf_path),
        "page_number": min(pages) if pages else 1,
        "page_start": min(pages) if pages else 1,
        "page_end": max(pages) if pages else 1,
        "chunk_type": "document_fallback",
        "section_number": None,
        "section_heading": None,
        "parent_section": None,
        "section_level": None,
        "sha256": sha256_file(pdf_path),
    }

    return [
        Chunk(
            chunk_id=f"pv_{document_id}_document",
            text=text,
            metadata=metadata,
        )
    ]


# ---------------------------------------------------------------------------
# Recall / Rapid Alert embedded-document handling
# ---------------------------------------------------------------------------

def split_restarted_documents(chunks: list[Chunk]) -> list[Chunk]:
    """
    17RecallRapid.pdf contains two embedded documents and section numbering
    restarts at 1.0 on page 11.

    We retain both documents as chunks, annotate each with
    ``embedded_document`` (1 or 2), and suffix the chunk_id for the second
    sequence so that every ID is globally unique.

    Part 1 IDs:  pv_17RecallRapid_section_1_0_doc1
    Part 2 IDs:  pv_17RecallRapid_section_1_0_doc2
    """
    if not chunks:
        return chunks

    restart_seen = False
    previous_page = 0
    sequence = 1

    result: list[Chunk] = []

    for chunk in chunks:
        page_start = int(chunk.metadata.get("page_start", 0))
        section_number = chunk.metadata.get("section_number")

        if (
            section_number == "1.0"
            and previous_page > 0
            and page_start > previous_page
        ):
            sequence += 1
            restart_seen = True

        # Annotate metadata with the embedded-document sequence number.
        chunk.metadata["embedded_document"] = sequence

        # Always suffix chunk_id with _doc{N} so Part 1 and Part 2 IDs
        # never collide even when section numbers repeat.
        chunk.chunk_id = f"{chunk.chunk_id}_doc{sequence}"

        result.append(chunk)
        previous_page = page_start

    return result


# ---------------------------------------------------------------------------
# 2025 New Drug table reuse
# ---------------------------------------------------------------------------

def try_import_fdc_chunker():
    """
    Import the existing FDC chunker if available.

    This avoids duplicating the table parser for the 2025 New Drug List.
    """
    candidates = [
        "fdc",
        "modules.prescription_rag.chunking_programs.fdc",
    ]

    for module_name in candidates:
        try:
            module = __import__(module_name, fromlist=["*"])
            return module
        except ImportError:
            continue

    return None


def process_new_drug_2025(
    pdf_path: Path,
    document_id: str,
) -> list[Chunk]:
    """
    Reuse the existing FDC table parser.

    If the FDC module exposes process_fdc_document(), use it. Otherwise,
    perform a small table fallback so this chunker remains usable.
    """
    fdc_module = try_import_fdc_chunker()

    if fdc_module is not None:
        process_fn = getattr(fdc_module, "process_fdc_document", None)

        if process_fn is not None:
            try:
                result = process_fn(
                    pdf_path=pdf_path,
                    document_id=document_id,
                )

                if result:
                    # Ensure the output uses this module's Chunk dataclass.
                    converted: list[Chunk] = []

                    for item in result:
                        if isinstance(item, Chunk):
                            converted.append(item)
                            continue

                        text = getattr(item, "text", "")
                        metadata = getattr(item, "metadata", {}) or {}
                        chunk_id = getattr(item, "chunk_id", "")

                        if not chunk_id:
                            chunk_id = (
                                f"pv_{document_id}_new_drug_"
                                f"{len(converted) + 1:03d}"
                            )

                        metadata = dict(metadata)
                        metadata.update(
                            {
                                "document_id": document_id,
                                "document_type": "new_drug_approval_list",
                                "chunk_type": "table_row",
                                "local_file": str(pdf_path),
                                "sha256": sha256_file(pdf_path),
                            }
                        )

                        converted.append(
                            Chunk(
                                chunk_id=chunk_id,
                                text=text,
                                metadata=metadata,
                            )
                        )

                    if converted:
                        return converted

            except Exception:
                # Fall through to the local minimal parser.
                pass

    return fallback_new_drug_table_parser(pdf_path, document_id)


def fallback_new_drug_table_parser(
    pdf_path: Path,
    document_id: str,
) -> list[Chunk]:
    """
    Small fallback parser for the confirmed 4-column 2025 table.

    This is intentionally conservative and is only used if the existing FDC
    parser cannot be imported.
    """
    try:
        import pdfplumber
    except ImportError:
        return []

    chunks: list[Chunk] = []
    digest = sha256_file(pdf_path)

    with pdfplumber.open(str(pdf_path)) as pdf:
        row_number = 0

        for page_number, page in enumerate(pdf.pages, start=1):
            tables = page.extract_tables()

            for table in tables:
                if not table:
                    continue

                header_index = None

                for i, row in enumerate(table[:5]):
                    cells = [
                        clean_line(str(cell or ""))
                        for cell in row
                    ]

                    joined = " ".join(cells).lower()

                    if (
                        "drug" in joined
                        and "indication" in joined
                        and "approval" in joined
                    ):
                        header_index = i
                        break

                if header_index is None:
                    continue

                header = [
                    clean_line(str(cell or "")).lower()
                    for cell in table[header_index]
                ]

                def find_column(*terms: str) -> Optional[int]:
                    for index, value in enumerate(header):
                        if any(term in value for term in terms):
                            return index
                    return None

                sno_idx = find_column("s.no", "sr.no", "serial")
                drug_idx = find_column("drug")
                indication_idx = find_column("indication")
                approval_idx = find_column("approval")

                if drug_idx is None:
                    continue

                for row in table[header_index + 1:]:
                    cells = [
                        re.sub(r"\s+", " ", str(cell or "").replace("\n", " ")).strip()
                        for cell in row
                    ]

                    if not any(cells):
                        continue

                    def value(index: Optional[int]) -> str:
                        if index is None or index >= len(cells):
                            return ""
                        return cells[index]

                    serial = value(sno_idx)
                    drug = value(drug_idx)
                    indication = value(indication_idx)
                    approval = value(approval_idx)

                    if not drug:
                        continue

                    # Skip obvious repeated headers.
                    if drug.lower() in {
                        "name of new drug",
                        "drug name",
                        "name of drug",
                    }:
                        continue

                    row_number += 1

                    sentence = f"{drug}."

                    if indication:
                        sentence = (
                            f"{drug} was approved for {indication}"
                        )

                    if approval:
                        sentence += f" on {approval}."

                    metadata = {
                        "document_id": document_id,
                        "document_type": "new_drug_approval_list",
                        "document_title": pdf_path.stem,
                        "source": "CDSCO",
                        "source_url": "",
                        "release_date": "",
                        "local_file": str(pdf_path),
                        "page_number": page_number,
                        "page_start": page_number,
                        "page_end": page_number,
                        "chunk_type": "table_row",
                        "row_number": row_number,
                        "serial_number": serial,
                        "drug_name": drug,
                        "indication": indication,
                        "date_of_approval": approval,
                        "fdc_or_new_drug": "new_drug",
                        "sha256": digest,
                    }

                    chunks.append(
                        Chunk(
                            chunk_id=(
                                f"pv_{document_id}_row_"
                                f"{row_number:03d}"
                            ),
                            text=sentence,
                            metadata=metadata,
                        )
                    )

    return chunks


# ---------------------------------------------------------------------------
# Document processing
# ---------------------------------------------------------------------------

def process_pv_document(
    pdf_path: Path,
    document_id: Optional[str] = None,
) -> list[Chunk]:
    if document_id is None:
        document_id = pdf_path.stem

    document_type = detect_document_type(pdf_path.name)

    if document_type == "new_drug_approval_list":
        return process_new_drug_2025(
            pdf_path=pdf_path,
            document_id=document_id,
        )

    chunks = parse_sections(
        pdf_path=pdf_path,
        document_id=document_id,
        document_type=document_type,
    )

    if document_type == "recall_rapid_alert":
        chunks = split_restarted_documents(chunks)

    return chunks


# ---------------------------------------------------------------------------
# Duplicate handling
# ---------------------------------------------------------------------------

def find_duplicate_files(pdf_files: list[Path]) -> dict[str, list[Path]]:
    """
    Group files by SHA-256. Source files are not deleted.
    """
    groups: dict[str, list[Path]] = {}

    for path in pdf_files:
        digest = sha256_file(path)
        groups.setdefault(digest, []).append(path)

    return {
        digest: paths
        for digest, paths in groups.items()
        if len(paths) > 1
    }


# ---------------------------------------------------------------------------
# Main chunking pipeline
# ---------------------------------------------------------------------------

def _canonical_pdf_files(pdf_files: list[Path]) -> list[Path]:
    """
    For each SHA-256 duplicate group, select exactly one canonical file.

    The canonical file is the one with the shortest filename (fewest
    characters in the stem).  This deterministically prefers the
    un-suffixed original when a versioned copy exists alongside it.

    Example:
        "Pv Guidancedoc24.pdf"                 (20 chars) ← canonical
        "Pv Guidancedoc24 on vaccines 2.0.pdf" (37 chars) ← skipped

    All unique files (no SHA-256 match) are passed through unchanged.
    """
    # Group files by hash.
    hash_to_paths: dict[str, list[Path]] = {}
    for p in pdf_files:
        digest = sha256_file(p)
        hash_to_paths.setdefault(digest, []).append(p)

    canonical: list[Path] = []
    for digest, group in hash_to_paths.items():
        # Sort by (stem length ascending, then name alphabetically) so the
        # result is always deterministic even when two files are the same length.
        chosen = sorted(group, key=lambda p: (len(p.stem), p.name))[0]
        canonical.append(chosen)
        if len(group) > 1:
            skipped = [p.name for p in group if p != chosen]
            print(
                f"  [DEDUP] {chosen.name!r} selected as canonical; "
                f"skipping: {skipped}"
            )

    # Return in a stable, sorted order.
    return sorted(canonical)


def chunk_pv_documents() -> list[Chunk]:
    """
    Process all PV PDFs.

    Exact SHA-256 duplicate PDFs are skipped; the canonical (shortest-named)
    file in each duplicate group is processed.  Source files are never deleted
    or renamed.
    """
    if not PV_DIR.exists():
        raise FileNotFoundError(
            f"Pharmacovigilance directory not found: {PV_DIR}"
        )

    all_pdf_files = sorted(
        p for p in PV_DIR.iterdir()
        if p.is_file() and p.suffix.lower() == ".pdf"
    )

    if not all_pdf_files:
        return []

    # Resolve duplicates: one canonical file per SHA-256 group.
    pdf_files = _canonical_pdf_files(all_pdf_files)

    all_chunks: list[Chunk] = []

    for pdf_path in pdf_files:
        document_id = pdf_path.stem

        chunks = process_pv_document(
            pdf_path=pdf_path,
            document_id=document_id,
        )

        all_chunks.extend(chunks)

    save_chunks_to_json(all_chunks)

    return all_chunks


# ---------------------------------------------------------------------------
# JSON serialization
# ---------------------------------------------------------------------------

def save_chunks_to_json(chunks: list[Chunk]) -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    payload = [
        {
            "chunk_id": chunk.chunk_id,
            "text": chunk.text,
            "metadata": chunk.metadata,
        }
        for chunk in chunks
    ]

    with OUTPUT_FILE.open(
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            payload,
            f,
            ensure_ascii=False,
            indent=2,
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def chunking() -> list[Chunk]:
    """
    Standard public interface shared by all prescription RAG chunkers.
    """
    return chunk_pv_documents()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    chunks = chunking()

    print("=" * 70)
    print("CDSCO Pharmacovigilance Chunking Complete")
    print("=" * 70)
    print(f"PV directory : {PV_DIR}")
    print(f"Chunks       : {len(chunks)}")
    print(f"Output       : {OUTPUT_FILE}")

    by_type: dict[str, int] = {}

    for chunk in chunks:
        doc_type = chunk.metadata.get(
            "document_type",
            "unknown",
        )
        by_type[doc_type] = by_type.get(doc_type, 0) + 1

    print("\nChunk breakdown:")
    for doc_type, count in sorted(by_type.items()):
        print(f"  {doc_type}: {count}")

    print("\nDone.")
