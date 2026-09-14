"""
BharatRx - Offline Index Builder
================================

This program is the OFFLINE part of the Prescription RAG pipeline.

It does NOT run any chunking program.

It:
    1. Loads the four already-created chunk JSON files.
    2. Combines every chunk into one list.
    3. Converts the custom Chunk JSON format into LangChain Documents.
    4. Creates a FAISS vector index using:
           sentence-transformers/all-MiniLM-L6-v2
    5. Creates a BM25 retriever over the same documents.
    6. Saves both indexes locally.
    7. Verifies that the number of vectors in FAISS exactly matches the
       number of documents supplied to it.

Expected structure:

modules/
└── prescription_rag/
    ├── Agentic_rag.py
    ├── create_indexes.py       <-- this file
    ├── data/
    │   └── processed/
    │       ├── adr_chunks.json
    │       ├── alerts_chunks.json
    │       ├── fdc_chunks.json
    │       └── pv_chunks.json
    └── ...

Output:

modules/
└── prescription_rag/
    └── data/
        └── indexes/
            ├── faiss/
            │   ├── index.faiss
            │   └── index.pkl
            ├── bm25.pkl
            └── index_manifest.json
"""

from __future__ import annotations

import json
import pickle
from pathlib import Path

from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_community.retrievers import BM25Retriever


# ============================================================================
# PATHS
# ============================================================================

# create_indexes.py is inside:
# BharatRx/modules/prescription_rag/
PROJECT_ROOT = Path(__file__).resolve().parent

PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

INDEX_DIR = PROJECT_ROOT / "data" / "indexes"
FAISS_DIR = INDEX_DIR / "faiss"
BM25_FILE = INDEX_DIR / "bm25.pkl"
MANIFEST_FILE = INDEX_DIR / "index_manifest.json"


# ============================================================================
# CHUNK FILES
# ============================================================================

# IMPORTANT:
# These are the ONLY four files that will be indexed.
#
# We intentionally do NOT use "*_chunks.json", because test/old chunk files
# should never accidentally enter the production RAG index.

# IMPORTANT:
# These filenames MUST match the actual output filenames from each chunker:
#   - addr.py outputs: adr_chunks.json
#   - alerts.py outputs: alert_chunks.json (singular, NOT "alerts")
#   - fdc.py outputs: fdc_chunks.json
#   - pharmacovigilance.py outputs: pv_chunks.json
#
# We intentionally do NOT use "*_chunks.json" wildcard, because test/old chunk
# files should never accidentally enter the production RAG index.

CHUNK_FILES = {
    "ADR": PROCESSED_DIR / "adr_chunks.json",
    "Alerts": PROCESSED_DIR / "alert_chunks.json",  # singular, as per alerts.py
    "FDC": PROCESSED_DIR / "fdc_chunks.json",
    "Pharmacovigilance": PROCESSED_DIR / "pv_chunks.json",
}


# ============================================================================
# EMBEDDING MODEL
# ============================================================================

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

# Number of BM25 results returned by the retriever.
BM25_K = 5


# ============================================================================
# LOAD ONE CHUNK FILE
# ============================================================================

def load_chunk_file(
    file_path: Path,
    source_name: str,
    require_exists: bool = True,
) -> tuple[list[Document], bool]:
    """
    Load one saved *_chunks.json file and convert every chunk into a
    LangChain Document.

    No chunking happens here.

    Args:
        file_path: Path to the chunk JSON file.
        source_name: Human-readable name for logging (e.g., "ADR", "Alerts").
        require_exists: If True, raise error when file missing.
                       If False, warn and return empty list.

    Returns:
        Tuple of (documents list, file_found boolean).
    """

    if not file_path.exists():
        if require_exists:
            raise FileNotFoundError(
                f"\nChunk file not found for {source_name}:\n"
                f"    {file_path}\n\n"
                "Make sure the corresponding chunker has already been run and "
                "the JSON output is inside data/processed/."
            )
        else:
            print(f"\nWARNING: Chunk file not found for {source_name}:")
            print(f"  Expected: {file_path}")
            print(f"  Skipping {source_name}. Run the corresponding chunker first.")
            return [], False

    print(f"\nLoading {source_name}:")
    print(f"  File: {file_path}")

    with file_path.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    if not isinstance(payload, list):
        raise ValueError(
            f"{file_path} does not contain a JSON list of chunks."
        )

    documents: list[Document] = []

    for item in payload:
        if not isinstance(item, dict):
            continue

        chunk_id = item.get("chunk_id")
        text = item.get("text", "")
        metadata = item.get("metadata", {}) or {}

        if not isinstance(text, str) or not text.strip():
            continue

        metadata = dict(metadata)

        # Preserve the original chunk ID.
        if chunk_id:
            metadata["chunk_id"] = chunk_id

        # Useful for debugging which dataset produced a result.
        metadata["rag_source"] = source_name

        # Keep the original JSON file location.
        metadata["chunk_json_file"] = str(file_path)

        documents.append(
            Document(
                page_content=text,
                metadata=metadata,
            )
        )

    print(f"  Loaded chunks: {len(documents)}")

    return documents, True


# ============================================================================
# LOAD ALL FOUR DATASETS
# ============================================================================

def load_all_documents() -> tuple[list[Document], dict[str, int], dict[str, bool]]:
    """
    Load ADR + Alerts + FDC + Pharmacovigilance chunks.

    Returns:
        documents:
            One flat list containing every chunk.

        counts:
            Number of chunks loaded from each dataset.

        found:
            Dict indicating which chunk files were found.
    """

    print("=" * 80)
    print("BHARATRX OFFLINE INDEX BUILDER")
    print("=" * 80)

    print("\nLoading SAVED chunks only.")
    print("No chunking programs will be executed.\n")

    all_documents: list[Document] = []
    counts: dict[str, int] = {}
    found: dict[str, bool] = {}

    for source_name, file_path in CHUNK_FILES.items():
        documents, file_found = load_chunk_file(
            file_path=file_path,
            source_name=source_name,
            require_exists=False,  # Don't fail on missing files
        )

        counts[source_name] = len(documents)
        found[source_name] = file_found
        all_documents.extend(documents)

    print("\n" + "-" * 80)
    print("CHUNK SUMMARY")
    print("-" * 80)

    for source_name, count in counts.items():
        status = "" if found[source_name] else " (MISSING)"
        print(f"{source_name:25} {count:>6}{status}")

    print("-" * 80)
    print(f"{'TOTAL':25} {len(all_documents):>6}")
    print("-" * 80)

    # Report missing files
    missing = [name for name, f in found.items() if not f]
    if missing:
        print(f"\nWARNING: {len(missing)} chunk file(s) not found: {', '.join(missing)}")
        print("Run the corresponding chunker(s) to generate them.")
        print("Proceeding with available data...\n")

    if not all_documents:
        raise ValueError(
            "No usable chunks were loaded. "
            "At least one chunk file must exist to create indexes."
        )

    return all_documents, counts, found


# ============================================================================
# VALIDATE CHUNKS
# ============================================================================

def validate_documents(documents: list[Document]) -> None:
    """
    Validate the combined document list before building indexes.
    """

    print("\n" + "=" * 80)
    print("VALIDATING DOCUMENTS")
    print("=" * 80)

    print(f"Total documents: {len(documents)}")

    empty_documents = [
        i for i, doc in enumerate(documents)
        if not doc.page_content.strip()
    ]

    if empty_documents:
        raise ValueError(
            f"Found {len(empty_documents)} empty documents."
        )

    # ------------------------------------------------------------------
    # Check duplicate chunk IDs.
    # ------------------------------------------------------------------
    chunk_ids = [
        doc.metadata.get("chunk_id")
        for doc in documents
        if doc.metadata.get("chunk_id")
    ]

    from collections import Counter
    id_counts = Counter(chunk_ids)
    duplicated = {cid: count for cid, count in id_counts.items() if count > 1}

    duplicate_ids = len(chunk_ids) - len(set(chunk_ids))

    if duplicate_ids:
        # ----------------------------------------------------------------
        # DIAGNOSTIC: print every duplicated ID with full context.
        # ----------------------------------------------------------------
        print("\n" + "!" * 80)
        print(f"DUPLICATE CHUNK ID DIAGNOSTIC  ({duplicate_ids} duplicate occurrences across {len(duplicated)} IDs)")
        print("!" * 80)

        # Group all documents by their chunk_id for easy lookup.
        from collections import defaultdict
        id_to_docs: dict[str, list[Document]] = defaultdict(list)
        for doc in documents:
            cid = doc.metadata.get("chunk_id")
            if cid and cid in duplicated:
                id_to_docs[cid].append(doc)

        # Per-dataset counters for the summary.
        DATASETS = ["ADR", "Alerts", "FDC", "Pharmacovigilance"]
        dataset_dup_counts: dict[str, int] = {ds: 0 for ds in DATASETS}

        for cid in sorted(duplicated.keys()):
            docs_with_id = id_to_docs[cid]
            print(f"\n{'─' * 70}")
            print(f"  chunk_id  : {cid}   (appears {duplicated[cid]}x)")
            print(f"{'─' * 70}")

            for occurrence_idx, doc in enumerate(docs_with_id, start=1):
                meta = doc.metadata
                rag_source = meta.get("rag_source", "UNKNOWN")
                chunk_json = meta.get("chunk_json_file", "UNKNOWN")
                page        = meta.get("page", meta.get("page_number", "N/A"))
                content_key = meta.get("content_type", meta.get("section", "N/A"))

                # Short preview: first 120 non-whitespace-collapsed characters.
                preview = " ".join(doc.page_content.split())[:120]
                if len(doc.page_content.split()) > 120:
                    preview += " …"

                print(f"\n  Occurrence #{occurrence_idx}:")
                print(f"    rag_source      : {rag_source}")
                print(f"    chunk_json_file : {chunk_json}")
                print(f"    page/page_number: {page}")
                print(f"    content_type    : {content_key}")
                print(f"    preview         : {preview!r}")

                # Count per dataset.
                if rag_source in dataset_dup_counts:
                    dataset_dup_counts[rag_source] += 1

        # ----------------------------------------------------------------
        # Summary grouped by dataset.
        # ----------------------------------------------------------------
        print("\n" + "=" * 80)
        print("Duplicate IDs by dataset:")
        print("=" * 80)
        for ds in DATASETS:
            print(f"  {ds:<20}: {dataset_dup_counts[ds]}")
        print(f"\n  Total duplicate occurrences : {duplicate_ids}")
        print(f"  Distinct duplicated IDs     : {len(duplicated)}")
        print("=" * 80)

        raise ValueError(
            f"Found {duplicate_ids} duplicate chunk IDs. "
            "Fix duplicate IDs before indexing."
        )

    print("Empty documents : 0")
    print(f"Unique chunk IDs: {len(chunk_ids)}")
    print("Validation      : PASS")


# ============================================================================
# BUILD FAISS
# ============================================================================

def build_faiss(documents: list[Document]) -> int:
    """
    Create FAISS from ALL documents and save it locally.

    Returns:
        Number of vectors actually stored in FAISS.
    """

    print("\n" + "=" * 80)
    print("BUILDING FAISS")
    print("=" * 80)

    print(f"Documents going into FAISS: {len(documents)}")
    print(f"Embedding model: {EMBEDDING_MODEL}")
    print("\nCreating embeddings...")
    print("This is the slow part of the OFFLINE process and only needs to happen")
    print("again when your chunk data changes.\n")

    embeddings = HuggingFaceEmbeddings(
        model_name=EMBEDDING_MODEL
    )

    vector_db = FAISS.from_documents(
        documents,
        embeddings,
    )

    # This is the important verification.
    vectors_stored = vector_db.index.ntotal

    print("\nFAISS verification:")
    print(f"  Documents supplied : {len(documents)}")
    print(f"  Vectors stored     : {vectors_stored}")

    if vectors_stored != len(documents):
        raise RuntimeError(
            "FAISS verification FAILED: "
            f"{len(documents)} documents were supplied, but "
            f"{vectors_stored} vectors were stored."
        )

    FAISS_DIR.mkdir(parents=True, exist_ok=True)

    vector_db.save_local(str(FAISS_DIR))

    print(f"\nFAISS saved to:")
    print(f"  {FAISS_DIR}")

    return vectors_stored


# ============================================================================
# BUILD BM25
# ============================================================================

def build_bm25(documents: list[Document]) -> int:
    """
    Create BM25 from the exact same documents used by FAISS.

    BM25Retriever is an in-memory retriever, so we persist it with pickle.
    Only load this pickle from a trusted local source.
    """

    print("\n" + "=" * 80)
    print("BUILDING BM25")
    print("=" * 80)

    print(f"Documents going into BM25: {len(documents)}")

    bm25_retriever = BM25Retriever.from_documents(
        documents
    )

    bm25_retriever.k = BM25_K

    # Verify BM25 contains the same number of documents.
    bm25_count = len(bm25_retriever.docs)

    print("\nBM25 verification:")
    print(f"  Documents supplied : {len(documents)}")
    print(f"  Documents indexed  : {bm25_count}")
    print(f"  Retrieval k        : {bm25_retriever.k}")

    if bm25_count != len(documents):
        raise RuntimeError(
            "BM25 verification FAILED: "
            f"{len(documents)} documents were supplied, but "
            f"{bm25_count} documents are in the retriever."
        )

    INDEX_DIR.mkdir(parents=True, exist_ok=True)

    with BM25_FILE.open("wb") as f:
        pickle.dump(bm25_retriever, f)

    print(f"\nBM25 saved to:")
    print(f"  {BM25_FILE}")

    return bm25_count


# ============================================================================
# SAVE MANIFEST
# ============================================================================

def save_manifest(
    counts: dict[str, int],
    found: dict[str, bool],
    total_documents: int,
    faiss_count: int,
    bm25_count: int,
) -> None:
    """
    Save a small manifest so we know exactly what went into the indexes.
    """

    manifest = {
        "embedding_model": EMBEDDING_MODEL,
        "bm25_k": BM25_K,
        "datasets": counts,
        "files_found": found,
        "total_documents": total_documents,
        "faiss_vectors": faiss_count,
        "bm25_documents": bm25_count,
        "verification": {
            "faiss_matches_documents": faiss_count == total_documents,
            "bm25_matches_documents": bm25_count == total_documents,
        },
    }

    INDEX_DIR.mkdir(parents=True, exist_ok=True)

    with MANIFEST_FILE.open("w", encoding="utf-8") as f:
        json.dump(
            manifest,
            f,
            indent=2,
            ensure_ascii=False,
        )

    print(f"\nIndex manifest saved to:")
    print(f"  {MANIFEST_FILE}")


# ============================================================================
# MAIN OFFLINE PIPELINE
# ============================================================================

def create_indexes() -> None:
    """
    Complete offline pipeline.

    This function should be run manually whenever the chunk JSON files
    change.
    """

    documents, counts, found = load_all_documents()

    validate_documents(documents)

    faiss_count = build_faiss(documents)

    bm25_count = build_bm25(documents)

    save_manifest(
        counts=counts,
        found=found,
        total_documents=len(documents),
        faiss_count=faiss_count,
        bm25_count=bm25_count,
    )

    print("\n" + "=" * 80)
    print("INDEX CREATION COMPLETE")
    print("=" * 80)

    print(f"Total documents indexed : {len(documents)}")
    print(f"FAISS vectors           : {faiss_count}")
    print(f"BM25 documents          : {bm25_count}")

    # Check if any files were missing
    missing = [name for name, f in found.items() if not f]
    if missing:
        print(f"\nNOTE: Indexes created with partial data.")
        print(f"Missing chunk files: {', '.join(missing)}")
        print("Run the corresponding chunker(s) and re-run create_indexes.py for complete indexes.")

    if (
        faiss_count == len(documents)
        and bm25_count == len(documents)
    ):
        print("\nFINAL VERIFICATION: PASS")
        print("Every loaded chunk is represented in both indexes.")
    else:
        raise RuntimeError(
            "FINAL VERIFICATION FAILED."
        )

    print("\nOutput:")
    print(f"  FAISS : {FAISS_DIR}")
    print(f"  BM25  : {BM25_FILE}")
    print(f"  Info  : {MANIFEST_FILE}")


# ============================================================================
# RUN
# ============================================================================

if __name__ == "__main__":
    create_indexes()
