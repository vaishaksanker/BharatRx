"""
BharatRx Normal RAG System
===========================

A standard RAG implementation with conversation history and RxNorm
drug normalization support.

Architecture:
    Conversation History
            ↓
    Context Resolution
            ↓
    RxNorm Drug Normalization   ← drug identity only, NOT medical evidence
            ↓
    Current Retrieval Query
            ↓
    Hybrid Retrieval (FAISS + BM25)
            ↓
    Reciprocal Rank Fusion
            ↓
    Deduplication
            ↓
    Top Evidence
            ↓
    Grounded Gemini LLM
            ↓
    Final Answer

Key Principles:
    - ONE retrieval pass per query (no agentic loop)
    - Conversation history helps understand context ONLY
    - RxNorm provides drug identity/normalization ONLY — NOT medical evidence
    - Retrieved documents are the SOLE source of medical evidence
    - Never hallucinate medical facts
    - Explicitly state when evidence is insufficient

RxNorm Attribution:
    BharatRx uses publicly available RxNorm data from the U.S. National
    Library of Medicine (NLM). NLM does not endorse BharatRx.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any, Optional
import pickle
import re
import requests


from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document
from langchain_google_genai import ChatGoogleGenerativeAI


# ============================================================
# CONFIGURATION
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent

INDEX_DIR = PROJECT_ROOT / "data" / "indexes"
FAISS_DIR = INDEX_DIR / "faiss"
BM25_FILE = INDEX_DIR / "bm25.pkl"

# Retrieval parameters
FAISS_K = 10  # Increased for better RRF coverage
BM25_K = 10   # Increased for better RRF coverage
FINAL_K = 8   # Final documents after fusion

# RRF parameter (k=60 is standard)
RRF_K = 60


# ============================================================
# RXNORM CONFIGURATION
# ============================================================
#
# BharatRx uses publicly available RxNorm data from the
# U.S. National Library of Medicine (NLM).
# NLM does not endorse BharatRx.
# RxNorm API: https://lhncbc.nlm.nih.gov/RxNav/APIs/RxNormAPIs.html
#
# RxNorm provides drug identity/normalization ONLY.
# It is NOT a source of medical evidence, safety data,
# drug interactions, contraindications, or clinical outcomes.

RXNORM_BASE_URL = "https://rxnav.nlm.nih.gov/REST"
RXNORM_TIMEOUT = 5        # seconds per HTTP request
RXNORM_MAX_CANDIDATES = 5 # max drug candidates to look up per query
RXNORM_APPROX_MAX_ENTRIES = 5  # max approximate match results to return

# Simple in-memory cache: maps normalized term -> rxnorm result dict
# Avoids repeated API calls for the same drug name within a session.
_rxnorm_cache: Dict[str, Dict[str, Any]] = {}


# ============================================================
# CONVERSATION STATE
# ============================================================

@dataclass
class ConversationState:
    """
    Maintains conversation history and current query state.
    
    Conversation history is used ONLY for understanding context.
    Previous assistant answers are NOT medical evidence.
    """
    history: List[Dict[str, str]] = field(default_factory=list)
    current_query: str = ""
    resolved_query: str = ""
    rxnorm_context: Dict[str, Any] = field(default_factory=dict)
    retrieved_documents: List[Document] = field(default_factory=list)
    final_answer: str = ""
    
    def add_user_message(self, message: str) -> None:
        """Add a user message to history."""
        self.history.append({"role": "user", "content": message})
    
    def add_assistant_message(self, message: str) -> None:
        """Add an assistant message to history."""
        self.history.append({"role": "assistant", "content": message})
    
    def get_last_n_turns(self, n: int = 3) -> List[Dict[str, str]]:
        """Get the last n conversation turns (user + assistant pairs)."""
        return self.history[-(n*2):]


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def get_text_from_response(response) -> str:
    """
    Extract text from a Gemini/LLM response.
    
    Handles the langchain-google-genai response format where
    response.content can be either a string or a list of content blocks.
    
    Args:
        response: The LLM response object with a .content attribute.
        
    Returns:
        str: The extracted text content.
    """
    content = response.content
    
    # If already a string, return as-is
    if isinstance(content, str):
        return content
    
    # If it's a list of content blocks, extract text from each
    if isinstance(content, list):
        text_parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text_parts.append(block.get("text", ""))
            elif isinstance(block, str):
                # Handle case where list contains plain strings
                text_parts.append(block)
        return "".join(text_parts)
    
    # Fallback: convert to string
    return str(content)


def format_context(documents: List[Document]) -> str:
    """
    Convert retrieved documents into a readable string for the LLM.
    
    Includes all available metadata for proper citation.
    """
    formatted = []
    
    for i, doc in enumerate(documents, start=1):
        metadata = doc.metadata
        
        # Build metadata string
        meta_parts = []
        
        chunk_id = metadata.get("chunk_id", "Unknown")
        meta_parts.append(f"Chunk ID: {chunk_id}")
        
        source = metadata.get("source", metadata.get("rag_source", "Unknown"))
        meta_parts.append(f"Source: {source}")
        
        if "drug_name" in metadata:
            meta_parts.append(f"Drug: {metadata['drug_name']}")
        
        page = metadata.get("page", metadata.get("page_number", "Unknown"))
        meta_parts.append(f"Page: {page}")
        
        if "document_title" in metadata:
            meta_parts.append(f"Document: {metadata['document_title']}")
        
        if "chunk_type" in metadata:
            meta_parts.append(f"Type: {metadata['chunk_type']}")
        
        formatted.append(
            f"--- DOCUMENT {i} ---\n"
            + "\n".join(meta_parts)
            + f"\n\nContent:\n{doc.page_content}\n"
        )
    
    return "\n".join(formatted)


def format_conversation_history(history: List[Dict[str, str]], max_turns: int = 3) -> str:
    """
    Format conversation history for context resolution.
    
    Only includes recent turns to avoid context explosion.
    """
    if not history:
        return "No previous conversation."
    
    recent = history[-(max_turns * 2):]
    
    formatted = []
    for turn in recent:
        role = turn["role"].capitalize()
        content = turn["content"]
        # Truncate long messages for context
        if len(content) > 500:
            content = content[:500] + "..."
        formatted.append(f"{role}: {content}")
    
    return "\n".join(formatted)


# ============================================================
# RECIPROCAL RANK FUSION
# ============================================================

def reciprocal_rank_fusion(
    faiss_results: List[Document],
    bm25_results: List[Document],
    k: int = RRF_K
) -> List[Document]:
    """
    Combine FAISS and BM25 results using Reciprocal Rank Fusion.
    
    RRF Formula: score(d) = Σ 1/(k + rank(d))
    
    This method handles incomparable scores between FAISS (cosine similarity)
    and BM25 (lexical score) by using rank positions only.
    
    Args:
        faiss_results: Documents from FAISS semantic search
        bm25_results: Documents from BM25 lexical search
        k: RRF parameter (default 60 is standard)
    
    Returns:
        Deduplicated documents sorted by fused score
    """
    # Track scores and documents by chunk_id
    fused_scores: Dict[str, float] = {}
    documents_by_id: Dict[str, Document] = {}
    
    # Process FAISS results
    for rank, doc in enumerate(faiss_results, start=1):
        chunk_id = doc.metadata.get("chunk_id", f"faiss_{rank}")
        
        # RRF score contribution
        rrf_score = 1.0 / (k + rank)
        
        if chunk_id in fused_scores:
            fused_scores[chunk_id] += rrf_score
        else:
            fused_scores[chunk_id] = rrf_score
            documents_by_id[chunk_id] = doc
    
    # Process BM25 results
    for rank, doc in enumerate(bm25_results, start=1):
        chunk_id = doc.metadata.get("chunk_id", f"bm25_{rank}")
        
        # RRF score contribution
        rrf_score = 1.0 / (k + rank)
        
        if chunk_id in fused_scores:
            fused_scores[chunk_id] += rrf_score
        else:
            fused_scores[chunk_id] = rrf_score
            documents_by_id[chunk_id] = doc
    
    # Sort by fused score (descending)
    sorted_ids = sorted(
        fused_scores.keys(),
        key=lambda x: fused_scores[x],
        reverse=True
    )
    
    # Build final list
    fused_documents = [documents_by_id[doc_id] for doc_id in sorted_ids]
    
    return fused_documents


# ============================================================
# RXNORM DRUG NORMALIZATION
# ============================================================
#
# PURPOSE: Drug identity and name normalization ONLY.
#
# RxNorm output is NOT medical evidence.
# It MUST NOT be used to conclude drug interactions,
# contraindications, adverse effects, or safety status.
# Medical evidence comes exclusively from FAISS/BM25 retrieval.

# ---------------------------------------------------------------------------
# Common stopwords that must never be treated as drug candidates.
# Keeps the heuristic from sending garbage queries to RxNorm.
# ---------------------------------------------------------------------------
_DRUG_STOPWORDS = frozenset({
    # Query intent words
    "what", "are", "the", "is", "does", "do", "how", "why", "when", "where",
    "which", "who", "can", "could", "should", "would", "will", "may", "might",
    # Common medical/query nouns that are NOT drug names
    "safety", "concern", "concerns", "monitoring", "requirement", "requirements",
    "interaction", "interactions", "contraindication", "contraindications",
    "effect", "effects", "adverse", "side", "drug", "drugs", "medicine",
    "medicines", "medication", "medications", "use", "uses", "dosage",
    "dose", "doses", "treatment", "prescription", "prescribing",
    "associated", "known", "particularly", "other", "risk", "risks",
    "patient", "patients", "doctor", "physician", "clinical", "medical",
    # Common conjunctions/prepositions
    "with", "and", "or", "for", "of", "in", "on", "at", "to", "from",
    "about", "between", "among", "against", "during", "after", "before",
    # Common adjectives
    "common", "major", "minor", "serious", "severe", "mild", "chronic",
    "acute", "significant", "important", "potential", "possible",
})


def extract_drug_candidates(query: str) -> List[str]:
    """
    Extract likely drug/medication name candidates from a query string.

    Uses a deterministic regex-and-heuristic approach.
    Does NOT call any LLM.
    Does NOT assume every word is a drug.

    Strategy:
    1. Tokenize into words/phrases.
    2. Remove stopwords and known non-drug terms.
    3. Keep tokens that look like medication names:
       - multi-character alpha/alphanumeric tokens
       - capitalized proper nouns
       - hyphenated compound names (e.g. "co-amoxiclav")
    4. Return up to RXNORM_MAX_CANDIDATES candidates.

    Args:
        query: The resolved user query string.

    Returns:
        List of candidate drug name strings (lowercased, deduplicated).
    """
    if not query or not query.strip():
        return []

    # Normalize whitespace
    query = query.strip()

    # Extract tokens: words including hyphens (for compound names)
    # Pattern: sequences of letters/digits/hyphens, at least 3 chars
    raw_tokens = re.findall(r"[A-Za-z][A-Za-z0-9\-]{2,}", query)

    candidates = []
    seen: set = set()

    for token in raw_tokens:
        lower = token.lower().strip("-")

        # Skip stopwords
        if lower in _DRUG_STOPWORDS:
            continue

        # Skip very short tokens
        if len(lower) < 3:
            continue

        # Skip purely numeric tokens
        if lower.replace("-", "").isdigit():
            continue

        # Deduplicate
        if lower in seen:
            continue

        seen.add(lower)
        candidates.append(lower)

    # Limit candidates
    return candidates[:RXNORM_MAX_CANDIDATES]


def get_rxnorm_context(query: str) -> Dict[str, Any]:
    """
    Look up drug normalization data from the NLM RxNorm REST API.

    Accepts the resolved retrieval query, extracts drug name candidates,
    and returns structured RxNorm concept information for matched drugs.

    IMPORTANT:
    - Returns drug identity/normalization data only.
    - Does NOT return medical evidence, interactions, or safety data.
    - Fails gracefully: any API error returns status='api_error'.
    - RxNorm failure does NOT block the RAG pipeline.
    - No API key required (NLM RxNorm is publicly available).

    Flow per candidate:
    1. Try exact string match via /rxcui.json?name=...&search=0
    2. If no exact match, try approximate match via /approximateTerm.json?term=...
    3. Accept only matches with a high approximation score (rank=1 + score>=95).
    4. Fetch concept properties (name, TTY, sources) for matched RxCUI.

    Args:
        query: Resolved query string (after conversation context resolution).

    Returns:
        dict with keys:
            status:         "matched" | "no_match" | "no_confident_match" | "api_error"
            matched_drugs:  List of matched drug dicts (empty if not matched)
            unresolved:     List of candidate terms that could not be matched
            error:          Error message if status == "api_error"
    """
    result: Dict[str, Any] = {
        "status": "no_match",
        "matched_drugs": [],
        "unresolved": [],
        "error": None,
    }

    candidates = extract_drug_candidates(query)

    if not candidates:
        print("\nRXNORM: No drug candidates found in query.")
        result["status"] = "no_match"
        return result

    print(f"\nRXNORM: Drug candidates identified: {candidates}")

    matched = []
    unresolved = []

    for term in candidates:
        # Check in-memory cache first
        if term in _rxnorm_cache:
            cached = _rxnorm_cache[term]
            print(f"RXNORM: Cache hit for '{term}'")
            if cached:
                matched.append(cached)
            else:
                unresolved.append(term)
            continue

        drug_entry = _rxnorm_lookup_term(term)

        if drug_entry is not None:
            _rxnorm_cache[term] = drug_entry
            matched.append(drug_entry)
            print(
                f"RXNORM: Matched '{term}' -> "
                f"{drug_entry['name']} (RxCUI: {drug_entry['rxcui']})"
            )
        else:
            # Cache the negative result to avoid repeated failed lookups
            _rxnorm_cache[term] = None
            unresolved.append(term)
            print(f"RXNORM: No confident match for '{term}'")

    result["unresolved"] = unresolved

    if matched:
        result["status"] = "matched"
        result["matched_drugs"] = matched
    elif candidates:
        result["status"] = "no_confident_match"

    return result


def _rxnorm_lookup_term(term: str) -> Optional[Dict[str, Any]]:
    """
    Attempt to match a single drug term via RxNorm REST API.

    Strategy:
    1. Exact string search (search=0 for normalized, search=1 for active).
    2. If no RxCUI found, try approximate match.
    3. Fetch properties for the resolved RxCUI.

    Returns a drug dict or None if no confident match.
    """
    # ── Step 1: Exact string lookup ──────────────────────────
    rxcui = _rxnorm_exact_lookup(term)

    # ── Step 2: Approximate lookup if exact failed ────────────
    if rxcui is None:
        rxcui = _rxnorm_approx_lookup(term)

    if rxcui is None:
        return None

    # ── Step 3: Fetch concept properties ──────────────────────
    return _rxnorm_get_properties(rxcui, term)


def _rxnorm_exact_lookup(term: str) -> Optional[str]:
    """
    Query RxNorm for an exact string match.
    Returns RxCUI string or None.
    """
    url = f"{RXNORM_BASE_URL}/rxcui.json"
    params = {"name": term, "search": "0"}  # search=0: normalized name

    try:
        resp = requests.get(url, params=params, timeout=RXNORM_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()

        rxcui_list = (
            data.get("idGroup", {})
                .get("rxnormId", [])
        )
        if rxcui_list:
            return str(rxcui_list[0])

    except requests.exceptions.Timeout:
        print(f"RXNORM: Timeout on exact lookup for '{term}'")
    except requests.exceptions.ConnectionError:
        print(f"RXNORM: Connection error on exact lookup for '{term}'")
    except requests.exceptions.HTTPError as e:
        print(f"RXNORM: HTTP error on exact lookup for '{term}': {e}")
    except (ValueError, KeyError):
        print(f"RXNORM: Invalid JSON or unexpected structure for '{term}'")

    return None


def _rxnorm_approx_lookup(term: str) -> Optional[str]:
    """
    Query RxNorm approximate term matching.
    Only accepts a match if rank=1 and score >= 95.
    Returns RxCUI string or None.
    """
    url = f"{RXNORM_BASE_URL}/approximateTerm.json"
    params = {
        "term": term,
        "maxEntries": RXNORM_APPROX_MAX_ENTRIES,
    }

    try:
        resp = requests.get(url, params=params, timeout=RXNORM_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()

        candidates = (
            data.get("approximateGroup", {})
                .get("candidate", [])
        )

        if not candidates:
            return None

        # Accept only the top candidate if it has high confidence
        top = candidates[0]
        rank  = int(top.get("rank",  999))
        score = int(top.get("score", 0))

        if rank == 1 and score >= 95:
            return str(top.get("rxcui", ""))

    except requests.exceptions.Timeout:
        print(f"RXNORM: Timeout on approximate lookup for '{term}'")
    except requests.exceptions.ConnectionError:
        print(f"RXNORM: Connection error on approximate lookup for '{term}'")
    except requests.exceptions.HTTPError as e:
        print(f"RXNORM: HTTP error on approximate lookup for '{term}': {e}")
    except (ValueError, KeyError):
        print(f"RXNORM: Invalid JSON or unexpected structure for '{term}'")

    return None


def _rxnorm_get_properties(rxcui: str, original_term: str) -> Optional[Dict[str, Any]]:
    """
    Fetch concept name and properties for a resolved RxCUI.
    Returns a compact drug dict or None on failure.
    """
    url = f"{RXNORM_BASE_URL}/rxcui/{rxcui}/properties.json"

    try:
        resp = requests.get(url, timeout=RXNORM_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()

        props = data.get("properties", {})

        if not props:
            return None

        return {
            "rxcui":    str(rxcui),
            "name":     props.get("name", original_term),
            "synonym":  props.get("synonym", ""),
            "tty":      props.get("tty", ""),
            "source":   "RXNORM",
            "language": props.get("language", "ENG"),
        }

    except requests.exceptions.Timeout:
        print(f"RXNORM: Timeout fetching properties for RxCUI {rxcui}")
    except requests.exceptions.ConnectionError:
        print(f"RXNORM: Connection error fetching properties for RxCUI {rxcui}")
    except requests.exceptions.HTTPError as e:
        print(f"RXNORM: HTTP error fetching properties for RxCUI {rxcui}: {e}")
    except (ValueError, KeyError):
        print(f"RXNORM: Invalid JSON or unexpected structure for RxCUI {rxcui}")

    return None


def format_rxnorm_context(rxnorm_result: Dict[str, Any]) -> str:
    """
    Format RxNorm lookup result into a compact string for the LLM prompt.

    This section is clearly labelled as drug normalization data,
    NOT as medical evidence.

    Args:
        rxnorm_result: Dict returned by get_rxnorm_context().

    Returns:
        Formatted string for inclusion in the LLM prompt, or empty string
        if RxNorm returned no useful data.
    """
    status = rxnorm_result.get("status", "no_match")

    if status == "api_error":
        return (
            "RxNorm Status: API unavailable\n"
            "Drug normalization could not be performed. "
            "Medical evidence will be retrieved and evaluated independently."
        )

    if status in ("no_match", "no_confident_match"):
        unresolved = rxnorm_result.get("unresolved", [])
        if unresolved:
            return (
                f"RxNorm Status: No confident match found for: {', '.join(unresolved)}\n"
                "Note: Unrecognized terms may be Indian brand names, FDC formulations, "
                "or non-US drug names not present in RxNorm."
            )
        return "RxNorm Status: No drug terms identified in query."

    # status == "matched"
    matched = rxnorm_result.get("matched_drugs", [])
    if not matched:
        return "RxNorm Status: Matched but no drug data returned."

    lines = ["RxNorm Status: Matched"]
    for drug in matched:
        lines.append(f"  Drug: {drug.get('name', 'Unknown')}")
        lines.append(f"    RxCUI: {drug.get('rxcui', 'N/A')}")
        if drug.get("synonym"):
            lines.append(f"    Synonym: {drug['synonym']}")
        if drug.get("tty"):
            lines.append(f"    Term Type: {drug['tty']}")
        lines.append(f"    Source: {drug.get('source', 'RXNORM')}")

    unresolved = rxnorm_result.get("unresolved", [])
    if unresolved:
        lines.append(
            f"  Not matched in RxNorm: {', '.join(unresolved)} "
            "(may be Indian brand names or FDC formulations)"
        )

    return "\n".join(lines)


# ============================================================
# MAIN RAG CLASS
# ============================================================

class BharatRxRAG:
    """
    BharatRx Normal RAG System.
    
    A grounded medical knowledge retrieval system with conversation history.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the RAG system.
        
        Args:
            api_key: Optional Google API key. If not provided, loads from apikey.txt
        """
        print("\n" + "=" * 70)
        print("BHARATRX NORMAL RAG")
        print("=" * 70)
        
        # Load API key
        if api_key is None:
            api_key_file = PROJECT_ROOT / "apikey.txt"
            with open(api_key_file, "r") as f:
                api_key = f.read().strip()
        
        # Load embedding model
        print("\nLoading embedding model...")
        self.embeddings = HuggingFaceEmbeddings(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        )
        
        # Load FAISS
        print("Loading FAISS index...")
        self.vectordb = FAISS.load_local(
            str(FAISS_DIR),
            self.embeddings,
            allow_dangerous_deserialization=True
        )
        print(f"  FAISS vectors: {self.vectordb.index.ntotal}")
        
        # Load BM25
        print("Loading BM25 index...")
        with open(BM25_FILE, "rb") as f:
            self.bm25_retriever = pickle.load(f)
        print(f"  BM25 documents: {len(self.bm25_retriever.docs)}")
        
        # Initialize LLM
        print("Initializing Gemini LLM...")
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-3.6-flash",
            temperature=0,
            api_key=api_key
        )
        
        # Initialize conversation state
        self.state = ConversationState()
        
        print("\nSystem ready.\n")
    
    def resolve_context(self, user_query: str) -> str:
        """
        Resolve conversational context to build an effective retrieval query.
        
        Uses LLM to identify referenced drugs/concepts from conversation history.
        
        IMPORTANT: Previous assistant answers are NOT medical evidence.
        They only help understand what the user is asking about.
        """
        history = self.state.history
        
        # If no history, return query as-is
        if not history:
            return user_query
        
        history_text = format_conversation_history(history, max_turns=3)
        
        resolution_prompt = f"""You are a context resolution component for a medical RAG system.

Your ONLY job is to understand what the user is asking about, using the conversation history.

CONVERSATION HISTORY:
{history_text}

CURRENT USER QUESTION:
{user_query}

TASK:
If the current question refers to a drug, condition, or concept mentioned in previous conversation,
build a search query that makes this reference explicit.

RULES:
1. Do NOT answer the question.
2. Do NOT add medical facts, conclusions, or assumptions.
3. Do NOT expand the query with clinical details not mentioned by the user.
4. ONLY make implicit references explicit (e.g., "it" → "ibuprofen", "that drug" → "metformin").
5. If the question is complete and self-contained, return it unchanged.
6. Output ONLY the search query, nothing else.

OUTPUT: A single search query string."""

        response = self.llm.invoke(resolution_prompt)
        resolved = get_text_from_response(response).strip()
        
        # Clean up any quotes
        resolved = resolved.strip('"\'')
        
        # Log the resolution
        if resolved != user_query:
            print(f"\nContext Resolution:")
            print(f"  Original: {user_query}")
            print(f"  Resolved: {resolved}")
        
        return resolved
    
    def retrieve(self, query: str) -> List[Document]:
        """
        Perform hybrid retrieval using FAISS + BM25 with RRF.
        
        This is a SINGLE retrieval pass - no agentic loop.
        """
        print("\n" + "-" * 70)
        print("RETRIEVAL")
        print("-" * 70)
        print(f"\nQuery: {query}")
        
        # FAISS semantic search
        print("\nFAISS search...")
        faiss_results = self.vectordb.similarity_search(
            query,
            k=FAISS_K
        )
        print(f"  Results: {len(faiss_results)}")
        
        # BM25 lexical search
        print("\nBM25 search...")
        bm25_results = self.bm25_retriever.invoke(query)[:BM25_K]
        print(f"  Results: {len(bm25_results)}")
        
        # Reciprocal Rank Fusion
        print("\nReciprocal Rank Fusion...")
        fused_results = reciprocal_rank_fusion(faiss_results, bm25_results)
        
        # Limit to final k
        final_results = fused_results[:FINAL_K]
        
        print(f"  Unique documents: {len(fused_results)}")
        print(f"  Final selection: {len(final_results)}")
        
        # Log retrieval results
        print("\nRetrieved Documents:")
        for i, doc in enumerate(final_results, start=1):
            chunk_id = doc.metadata.get("chunk_id", "Unknown")
            source = doc.metadata.get("source", doc.metadata.get("rag_source", "Unknown"))
            drug = doc.metadata.get("drug_name", "N/A")
            preview = " ".join(doc.page_content.split())[:100]
            
            print(f"\n  [{i}] {chunk_id}")
            print(f"      Source: {source}")
            print(f"      Drug: {drug}")
            print(f"      Preview: {preview}...")
        
        return final_results
    
    def generate_answer(
        self,
        query: str,
        documents: List[Document],
        rxnorm_result: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Generate a grounded answer based on retrieved evidence.

        The prompt receives three clearly separated sections:
          1. RXNORM DRUG CONTEXT  — drug identity/normalization only, NOT evidence.
          2. RETRIEVED MEDICAL EVIDENCE — the sole source of medical claims.
          3. USER QUESTION.

        CRITICAL: The LLM must NOT invent medical facts.
        All clinical claims must be supported by the retrieved documents.
        RxNorm data must NOT be used as medical evidence.
        """
        print("\n" + "-" * 70)
        print("ANSWER GENERATION")
        print("-" * 70)

        context_text = format_context(documents)

        # Format RxNorm section — labelled as normalization, NOT evidence
        if rxnorm_result:
            rxnorm_section = format_rxnorm_context(rxnorm_result)
        else:
            rxnorm_section = "RxNorm Status: Not performed."

        answer_prompt = f"""You are BharatRx, an AI-powered medication safety decision-support system.

IMPORTANT: You are NOT a doctor and you do NOT prescribe medication.

============================================================
RXNORM DRUG CONTEXT (drug identity/normalization only)
============================================================
{rxnorm_section}

IMPORTANT ABOUT THE RXNORM SECTION ABOVE:
- This section provides drug identity and normalization information ONLY.
- It is NOT medical evidence.
- It MUST NOT be used to conclude interactions, contraindications,
  adverse effects, monitoring requirements, or safety status.
- Do NOT invent medical facts based on a drug's RxNorm identity.

============================================================
RETRIEVED MEDICAL EVIDENCE (sole source for medical claims)
============================================================
{context_text}

============================================================
USER QUESTION
============================================================
{query}

CRITICAL RULES - YOU MUST FOLLOW ALL OF THEM:

1. GROUNDING: Use ONLY information directly supported by the RETRIEVED
   MEDICAL EVIDENCE section above.
   - If a claim is not in the retrieved documents, do NOT make it.
   - If the documents are insufficient, say so explicitly.
   - The RxNorm section is NOT medical evidence.

2. NO HALLUCINATION:
   - Do NOT invent drug interactions.
   - Do NOT invent contraindications.
   - Do NOT invent adverse effects.
   - Do NOT invent monitoring requirements.
   - Do NOT infer risks or mechanisms not stated in the retrieved documents.
   - Do NOT use general medical knowledge to fill gaps.

3. EVIDENCE HIERARCHY:
   - State what is SUPPORTED by the retrieved documents.
   - State what is NOT MENTIONED in the retrieved documents.
   - State what is UNCLEAR from the retrieved documents.

4. SAFETY FRAMEWORK:
   - KNOWN CONCERN: When retrieved documents clearly indicate a safety issue.
   - NO SIGNIFICANT CONCERN IDENTIFIED: When documents exist but show no concern.
   - INSUFFICIENT EVIDENCE: When documents don't contain relevant information.

5. ADVISORY ROLE:
   - You provide information, not treatment decisions.
   - Never tell a patient to independently start, stop, or change medication.
   - Recommend professional healthcare consultation when appropriate.

RESPONSE FORMAT:

**Assessment:**
[One of: Known Concern / No Significant Concern Identified / Insufficient Evidence]

**Finding:**
[State the finding supported by retrieved documents, or "No relevant evidence found"]

**Explanation:**
[Explain using ONLY retrieved document content. Cite specific documents.]

**Evidence Sources:**
[List the specific documents that support the finding, with their IDs and sources]

**Missing Information:**
[State explicitly what could NOT be determined from the retrieved documents]

**Recommendation:**
[Recommend professional healthcare consultation if appropriate. Never make autonomous treatment decisions.]"""

        response = self.llm.invoke(answer_prompt)
        answer = get_text_from_response(response)

        return answer
    
    def query(self, user_query: str) -> str:
        """
        Main query interface.

        Full pipeline:
        1. Store query in conversation history.
        2. Resolve conversational context (LLM, uses history only).
        3. RxNorm drug normalization (deterministic + REST API, no LLM).
        4. Retrieve relevant documents — single FAISS+BM25+RRF pass.
        5. Generate grounded answer (Gemini, evidence only).
        6. Store answer in history.
        7. Return answer.

        Args:
            user_query: The user's question.

        Returns:
            The grounded advisory answer.
        """
        # Step 1 — store user query in history
        self.state.add_user_message(user_query)
        self.state.current_query = user_query

        # Step 2 — resolve conversational context
        resolved_query = self.resolve_context(user_query)
        self.state.resolved_query = resolved_query

        # Step 3 — RxNorm drug normalization
        # Runs against the resolved query so follow-up questions
        # ("What about monitoring?") also benefit from normalization
        # after context resolution has made the drug reference explicit.
        print("\n" + "-" * 70)
        print("RXNORM DRUG NORMALIZATION")
        print("-" * 70)
        rxnorm_result = get_rxnorm_context(resolved_query)
        self.state.rxnorm_context = rxnorm_result
        print(f"RxNorm status: {rxnorm_result['status']}")

        # Step 4 — retrieve documents (single pass, no retry loop)
        documents = self.retrieve(resolved_query)
        self.state.retrieved_documents = documents

        # Step 5 — generate grounded answer
        answer = self.generate_answer(user_query, documents, rxnorm_result)
        self.state.final_answer = answer

        # Step 6 — store answer in history
        self.state.add_assistant_message(answer)

        return answer
    
    def clear_history(self) -> None:
        """Clear conversation history for a new conversation."""
        self.state = ConversationState()
        print("\nConversation history cleared.\n")
    
    def get_retrieval_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the last retrieval for debugging.

        Returns information about what was retrieved and what RxNorm matched,
        without exposing sensitive content or API keys.
        """
        docs = self.state.retrieved_documents
        rxnorm = self.state.rxnorm_context

        summary: Dict[str, Any] = {
            "query": self.state.current_query,
            "resolved_query": self.state.resolved_query,
            "rxnorm_status": rxnorm.get("status", "not_run"),
            "rxnorm_matched_drugs": [
                {"rxcui": d.get("rxcui"), "name": d.get("name")}
                for d in rxnorm.get("matched_drugs", [])
            ],
            "rxnorm_unresolved": rxnorm.get("unresolved", []),
            "num_documents": len(docs),
            "document_ids": [d.metadata.get("chunk_id", "Unknown") for d in docs],
            "sources": list(set(
                d.metadata.get("source", d.metadata.get("rag_source", "Unknown"))
                for d in docs
            )),
            "drugs_mentioned": list(set(
                d.metadata.get("drug_name")
                for d in docs
                if d.metadata.get("drug_name")
            )),
        }
        return summary


# ============================================================
# LEGACY COMPATIBILITY INTERFACE
# ============================================================

def run_agent(query: str) -> Dict[str, Any]:
    """
    Legacy compatibility function.
    
    Provides the same interface as the old run_agent() function
    but uses the new Normal RAG implementation.
    
    This function creates a fresh RAG instance for each query.
    For multi-turn conversations, use BharatRxRAG.query() directly.
    """
    rag = BharatRxRAG()
    answer = rag.query(query)
    
    # Return in legacy format
    return {
        "original_query": rag.state.current_query,
        "current_query": rag.state.resolved_query,
        "context": rag.state.retrieved_documents,
        "generated_answer": answer,
        "retrieval_attempts": 1,  # Always 1 for normal RAG
        "context_sufficient": True,  # No longer applicable
        "missing_information": [],  # No longer applicable
    }


# ============================================================
# MAIN ENTRY POINT
# ============================================================

if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("                 BHARATRX NORMAL RAG")
    print("=" * 70)
    
    # Create RAG instance
    rag = BharatRxRAG()
    
    # Interactive query loop
    print("\nEnter your medical knowledge queries.")
    print("Type 'clear' to clear conversation history.")
    print("Type 'quit' to exit.\n")
    
    while True:
        try:
            query = input("Query: ").strip()
            
            if not query:
                continue
            
            if query.lower() == "quit":
                print("\nGoodbye.\n")
                break
            
            if query.lower() == "clear":
                rag.clear_history()
                continue
            
            # Process query
            answer = rag.query(query)
            
            # Display answer
            print("\n" + "=" * 70)
            print("ANSWER")
            print("=" * 70)
            print(f"\n{answer}\n")
            
            # Display retrieval summary
            summary = rag.get_retrieval_summary()
            print("\n" + "-" * 70)
            print("RETRIEVAL SUMMARY")
            print("-" * 70)
            print(f"Documents retrieved: {summary['num_documents']}")
            print(f"Sources: {', '.join(summary['sources'])}")
            if summary['drugs_mentioned']:
                print(f"Drugs found: {', '.join(summary['drugs_mentioned'])}")
            print()
            
        except KeyboardInterrupt:
            print("\n\nInterrupted. Goodbye.\n")
            break
        except Exception as e:
            print(f"\nError: {e}\n")
            import traceback
            traceback.print_exc()
