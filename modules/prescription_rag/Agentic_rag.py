from typing import TypedDict, List
from pathlib import Path
import pickle
import json
import re


from langgraph.graph import StateGraph, START, END

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_community.retrievers import BM25Retriever
from langchain_google_genai import ChatGoogleGenerativeAI


# ============================================================
# 1. CONFIGURATION
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent

INDEX_DIR = PROJECT_ROOT / "data" / "indexes"
FAISS_DIR = INDEX_DIR / "faiss"
BM25_FILE = INDEX_DIR / "bm25.pkl"

MAX_RETRIEVAL_ATTEMPTS = 3
FAISS_K = 5
BM25_K = 5


# ============================================================
# 2. LOAD MODELS / INDEXES
# ============================================================

print("\nLoading saved FAISS and BM25 indexes...\n")


# Embedding model
embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)


# FAISS
vectordb = FAISS.load_local(
    str(FAISS_DIR),
    embeddings,
    allow_dangerous_deserialization=True
)


# BM25
with open(BM25_FILE, "rb") as f:
    bm25_db = pickle.load(f)


print(f"FAISS vectors loaded : {vectordb.index.ntotal}")
print(f"BM25 documents loaded: {len(bm25_db.docs)}")
print("Indexes loaded successfully.\n")


# ============================================================
# 3. LLM
# ============================================================
PROJECT_ROOT = Path(__file__).resolve().parent

API_KEY_FILE = PROJECT_ROOT / "apikey.txt"
with open(API_KEY_FILE, "r") as f:
    GOOGLE_API_KEY = f.read().strip()

llm = ChatGoogleGenerativeAI(
    model="gemini-3.6-flash",
    temperature=0,
     api_key=GOOGLE_API_KEY
)


# ============================================================
# 4. LANGGRAPH STATE
# ============================================================

class AgentState(TypedDict):

    # Conversation
    history: List[str]

    # Query
    original_query: str
    current_query: str

    # Retrieval
    context: list
    retrieval_attempts: int

    # Evaluation
    context_sufficient: bool
    missing_information: List[str]

    # Query rewriting
    rephrased_query: str

    # Control
    should_continue: bool

    # Final answer
    generated_answer: str


# ============================================================
# 5. HELPER FUNCTIONS
# ============================================================

def get_text_from_response(response):
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


def clean_llm_json(text: str):
    """
    Extract JSON from an LLM response.
    Handles responses wrapped in ```json ... ```.
    """

    text = text.strip()

    # Remove markdown code fences
    text = re.sub(r"```json", "", text, flags=re.IGNORECASE)
    text = re.sub(r"```", "", text)

    text = text.strip()

    return json.loads(text)


def format_context(context):
    """
    Convert retrieved LangChain documents into a readable
    string for the LLM.
    """

    formatted = []

    for i, chunk in enumerate(context, start=1):

        metadata = chunk.metadata

        formatted.append(
            f"""
--- DOCUMENT {i} ---

Chunk ID: {metadata.get("chunk_id", "Unknown")}
Source: {metadata.get("source", "Unknown")}
Page: {metadata.get("page", "Unknown")}

Content:
{chunk.page_content}
"""
        )

    return "\n".join(formatted)


# ============================================================
# 6. HYBRID RETRIEVAL
# ============================================================

def retrieve(state: AgentState) -> AgentState:

    query = state["current_query"]

    print("\n")
    print("=" * 70)
    print("RETRIEVAL")
    print("=" * 70)

    print(f"\nQuery: {query}")

    # --------------------------------------------------------
    # FAISS semantic search
    # --------------------------------------------------------

    vector_chunks = vectordb.similarity_search(
        query,
        k=FAISS_K
    )

    # --------------------------------------------------------
    # BM25 lexical search
    # --------------------------------------------------------

    bm25_chunks = bm25_db.invoke(query)

    # Limit BM25 results
    bm25_chunks = bm25_chunks[:BM25_K]

    # --------------------------------------------------------
    # Combine
    # --------------------------------------------------------

    combined_chunks = vector_chunks + bm25_chunks

    # --------------------------------------------------------
    # Remove duplicates
    # --------------------------------------------------------

    unique_chunks = {}

    for chunk in combined_chunks:

        chunk_id = chunk.metadata.get("chunk_id")

        if chunk_id:

            unique_chunks[chunk_id] = chunk

        else:

            # Fallback if chunk_id is unavailable
            content_key = chunk.page_content[:100]

            unique_chunks[content_key] = chunk

    context = list(unique_chunks.values())

    # --------------------------------------------------------
    # Update state
    # --------------------------------------------------------

    state["context"] = context
    state["retrieval_attempts"] += 1

    print(f"\nFAISS results : {len(vector_chunks)}")
    print(f"BM25 results  : {len(bm25_chunks)}")
    print(f"Unique results: {len(context)}")
    print(f"Attempt       : {state['retrieval_attempts']}")

    # --------------------------------------------------------
    # Display retrieved context
    # --------------------------------------------------------

    print("\n========== RETRIEVED CONTEXT ==========")

    for i, chunk in enumerate(context, start=1):

        print(f"\n--- RESULT {i} ---")

        print(
            "Chunk ID:",
            chunk.metadata.get("chunk_id")
        )

        print(
            "Source:",
            chunk.metadata.get("source")
        )

        print(
            "Page:",
            chunk.metadata.get("page")
        )

        print(
            chunk.page_content[:500]
        )

    return state


# ============================================================
# 7. CONTEXT EVALUATION
# ============================================================

def evaluate_context(state: AgentState) -> AgentState:

    # Always evaluate against the original user question, not the
    # rephrased retrieval query.  Query expansion changes what we search
    # for; it must never redefine what counts as a complete answer.
    original_query = state["original_query"]
    context = state["context"]

    print("\n")
    print("=" * 70)
    print("CONTEXT EVALUATION")
    print("=" * 70)

    context_text = format_context(context)

    evaluation_prompt = f"""
You are the evidence evaluation component of BharatRx,
an AI medication safety system.

Your job is NOT to answer the user's medical question.

Your job is only to determine whether the retrieved
documents contain enough reliable information to answer
the original user question.

ORIGINAL USER QUESTION (the goal that must be satisfied):
{original_query}

RETRIEVED CONTEXT:
{context_text}

Evaluate whether the retrieved context is sufficient.

The context is considered sufficient ONLY if it contains
information directly relevant to answering the original
user question above.

If important information is missing, identify exactly
what information is missing.

IMPORTANT:
- Do not use your own medical knowledge.
- Judge ONLY the retrieved context.
- Do not assume that missing information is true.
- If the evidence is insufficient, say so.
- Never invent evidence.

Return ONLY valid JSON in this format:

{{
    "sufficient": true,
    "missing_information": []
}}

OR

{{
    "sufficient": false,
    "missing_information": [
        "specific missing information 1",
        "specific missing information 2"
    ]
}}
"""

    response = llm.invoke(evaluation_prompt)

    response_text = get_text_from_response(response)

    try:

        result = clean_llm_json(response_text)

        state["context_sufficient"] = result.get(
            "sufficient",
            False
        )

        state["missing_information"] = result.get(
            "missing_information",
            []
        )

    except Exception as e:

        print("\nCould not parse evaluator response.")
        print("Error:", e)
        print("Raw response:", response_text)

        # Fail safely
        state["context_sufficient"] = False
        state["missing_information"] = [
            "Unable to reliably evaluate retrieved evidence."
        ]

    # --------------------------------------------------------
    # Display evaluation
    # --------------------------------------------------------

    print(
        "\nContext sufficient:",
        state["context_sufficient"]
    )

    print(
        "Missing information:",
        state["missing_information"]
    )

    return state


# ============================================================
# 8. DECISION NODE
# ============================================================

def decide_next_step(state: AgentState) -> AgentState:

    print("\n")
    print("=" * 70)
    print("DECISION")
    print("=" * 70)

    # --------------------------------------------------------
    # Evidence is sufficient
    # --------------------------------------------------------

    if state["context_sufficient"]:

        print("\nEvidence is sufficient.")
        print("Proceeding to answer generation.")

        state["should_continue"] = False

        return state

    # --------------------------------------------------------
    # Evidence insufficient but retries available
    # --------------------------------------------------------

    if state["retrieval_attempts"] < MAX_RETRIEVAL_ATTEMPTS:

        print(
            "\nEvidence is insufficient."
        )

        print(
            "Retrieval attempts remaining:",
            MAX_RETRIEVAL_ATTEMPTS
            - state["retrieval_attempts"]
        )

        state["should_continue"] = True

        return state

    # --------------------------------------------------------
    # Maximum attempts reached
    # --------------------------------------------------------

    print(
        "\nMaximum retrieval attempts reached."
    )

    print(
        "Proceeding with uncertainty."
    )

    state["should_continue"] = False

    return state


# ============================================================
# 9. QUERY REPHRASING / QUERY EXPANSION
# ============================================================

def rephrase_query(state: AgentState) -> AgentState:

    # FIX 2: Always anchor on original_query, never the already-expanded
    # current_query.  Expanding an already-expanded query causes the LLM to
    # accumulate unsupported assumptions across iterations.
    original_query = state["original_query"]
    missing = state["missing_information"]

    print("\n")
    print("=" * 70)
    print("QUERY EXPANSION")
    print("=" * 70)

    missing_text = "\n".join(
        f"- {item}"
        for item in missing
    )

    # FIX 1: Strict prompt that prohibits hallucination and medical inference.
    rephrase_prompt = f"""You are a retrieval query rewriter for a medical knowledge RAG system.

The original user query asks for medical information.
The retrieved context was judged insufficient.

Your task is NOT to answer the user's question.

Your task is ONLY to create a better search query that can retrieve the
missing evidence from the knowledge base.

ORIGINAL USER QUERY:
{original_query}

MISSING INFORMATION IDENTIFIED BY THE EVIDENCE EVALUATOR:
{missing_text}

STRICT RULES — you MUST follow all of them:
1. Do NOT provide the medical answer.
2. Do NOT infer that any drug interaction, contraindication, or safety
   concern exists.
3. Do NOT invent mechanisms, risks, adverse effects, contraindications,
   clinical outcomes, or treatment recommendations.
4. Do NOT add unsupported medical facts of any kind.
5. Do NOT introduce new specific drug names unless they already appear in
   the original user query above.
6. Preserve the original medical entities and intent from the original
   user query.
7. Focus only on retrieving evidence for the missing information listed
   above.
8. The query must remain evidence-seeking, not conclusion-stating.
9. Output ONLY the search query — no explanations, no reasoning, no
   markdown, no JSON, no bullet points, no preamble.

OUTPUT: a single plain-text search query."""

    response = llm.invoke(rephrase_prompt)

    new_query = get_text_from_response(response).strip()

    # Remove accidental surrounding quotes
    new_query = new_query.strip('"').strip("'")

    state["rephrased_query"] = new_query
    # FIX 2: current_query is updated to the rephrased query for retrieval,
    # but original_query is NEVER touched — it remains the semantic anchor.
    state["current_query"] = new_query

    print("\nOriginal query (anchor):")
    print(original_query)

    print("\nNew retrieval query:")
    print(new_query)

    return state


# ============================================================
# 10. FINAL ANSWER GENERATION
# ============================================================

def generate_answer(state: AgentState) -> AgentState:

    # FIX 3: Only original_query (the question) and context (retrieved docs)
    # are passed to the LLM.  current_query, rephrased_query, and
    # missing_information are NOT passed — they are retrieval artefacts,
    # not medical evidence.
    query = state["original_query"]
    context = state["context"]
    context_sufficient = state["context_sufficient"]

    print("\n")
    print("=" * 70)
    print("ANSWER GENERATION")
    print("=" * 70)

    context_text = format_context(context)

    # --------------------------------------------------------
    # FIX 5: Structured uncertainty branch
    # --------------------------------------------------------

    if not context_sufficient:

        # FIX 4+5: Uncertainty prompt — conservative, no general-knowledge
        # gap-filling, structured output mandated.
        answer_prompt = f"""You are BharatRx, an AI-powered medication safety decision-support system.
You are NOT a doctor and you do NOT prescribe medication.

The retrieval system performed multiple searches and was UNABLE to obtain
sufficient evidence to answer the user's question.

USER QUERY (the question only — NOT evidence):
{query}

RETRIEVED DOCUMENTS (the only permitted evidence source):
{context_text}

STRICT RULES:
- Do NOT use your general medical knowledge to fill gaps.
- Do NOT infer or guess drug interactions, contraindications, adverse
  effects, or clinical outcomes.
- Do NOT treat the user query or any query-rewriter output as evidence.
- Only facts directly supported by the retrieved documents above may
  appear in the "Available evidence" section.
- Do NOT state that a specific interaction or risk exists unless a
  retrieved document explicitly states it.

Respond using EXACTLY this structure:

Assessment:
Insufficient reliable evidence

Finding:
The retrieved knowledge base does not contain sufficient evidence to
establish the requested information.

Available evidence:
[Briefly summarise ONLY facts that are directly present in the retrieved
documents above.  If no relevant facts are present, write "None found."]

Missing evidence:
[List the specific information requested by the user that could NOT be
established from the retrieved documents.]

Recommendation:
For a real patient, consult an appropriate healthcare professional before
making any medication changes. Do not independently start, stop, or
modify medication."""

    else:

        # FIX 4: Sufficient-evidence prompt — grounded, no LLM gap-filling.
        answer_prompt = f"""You are BharatRx, an AI-powered medication safety decision-support system.
You are NOT a doctor and you do NOT prescribe medication.

USER QUERY (the question only — NOT evidence):
{query}

RETRIEVED DOCUMENTS (the only permitted evidence source):
{context_text}

STRICT RULES:
- Use ONLY information that is directly supported by the retrieved
  documents above.
- Do NOT use your general medical knowledge to fill missing information.
- Do NOT infer or guess drug interactions, contraindications, adverse
  effects, or clinical outcomes that are not stated in the documents.
- Do NOT treat the user query or any query-rewriter output as evidence.
- If the retrieved documents do not contain enough information to answer
  part of the question, explicitly state that for that part.
- Clearly distinguish between:
    1. Evidence-supported finding
    2. No significant concern identified from the available evidence
    3. Insufficient evidence for a specific aspect

Respond using EXACTLY this structure:

Risk / Finding:
[State the finding supported by retrieved evidence, or state
"No significant concern identified from the available evidence."]

Explanation:
[Explain using only retrieved document content.]

Relevant evidence:
[Cite specific retrieved documents or passages that support the finding.]

Recommendation:
[Recommend review by an appropriate healthcare professional where a
potential safety concern exists.  Never tell the patient to independently
start, stop, or change medication.]

Uncertainty:
[State explicitly what could NOT be established from the retrieved
documents, if anything.]"""

    response = llm.invoke(answer_prompt)

    state["generated_answer"] = get_text_from_response(response)

    return state


# ============================================================
# 11. LANGGRAPH ROUTING
# ============================================================

def route_after_decision(state: AgentState):

    if state["should_continue"]:

        return "rephrase_query"

    return "generate_answer"


# ============================================================
# 12. BUILD GRAPH
# ============================================================

graph = StateGraph(AgentState)


# Add nodes
graph.add_node(
    "retrieve",
    retrieve
)

graph.add_node(
    "evaluate_context",
    evaluate_context
)

graph.add_node(
    "decide",
    decide_next_step
)

graph.add_node(
    "rephrase_query",
    rephrase_query
)

graph.add_node(
    "generate_answer",
    generate_answer
)


# ------------------------------------------------------------
# Graph flow
# ------------------------------------------------------------

graph.add_edge(
    START,
    "retrieve"
)

graph.add_edge(
    "retrieve",
    "evaluate_context"
)

graph.add_edge(
    "evaluate_context",
    "decide"
)


graph.add_conditional_edges(
    "decide",
    route_after_decision,
    {
        "rephrase_query": "rephrase_query",
        "generate_answer": "generate_answer"
    }
)


# Rephrased query goes back into retrieval
graph.add_edge(
    "rephrase_query",
    "retrieve"
)


graph.add_edge(
    "generate_answer",
    END
)


# Compile
app = graph.compile()


# ============================================================
# 13. RUN AGENT
# ============================================================

def run_agent(query: str):

    initial_state: AgentState = {

        "history": [],

        "original_query": query,

        "current_query": query,

        "context": [],

        "retrieval_attempts": 0,

        "context_sufficient": False,

        "missing_information": [],

        "rephrased_query": "",

        "should_continue": False,

        "generated_answer": ""
    }

    result = app.invoke(initial_state)

    return result


# ============================================================
# 14. MAIN
# ============================================================

if __name__ == "__main__":

    print("\n")
    print("=" * 70)
    print("                 BHARATRX AGENTIC RAG")
    print("=" * 70)

    query = input(
        "\nEnter your medical knowledge query: "
    )

    result = run_agent(query)

    print("\n")
    print("=" * 70)
    print("                    FINAL ANSWER")
    print("=" * 70)

    print(
        "\n",
        result["generated_answer"]
    )

    print("\n")
    print("=" * 70)
    print("                    AGENT SUMMARY")
    print("=" * 70)

    print(
        "\nOriginal query:",
        result["original_query"]
    )

    print(
        "\nFinal retrieval query:",
        result["current_query"]
    )

    print(
        "\nRetrieval attempts:",
        result["retrieval_attempts"]
    )

    print(
        "\nContext sufficient:",
        result["context_sufficient"]
    )

    if result["missing_information"]:

        print(
            "\nMissing information:"
        )

        for item in result["missing_information"]:

            print(
                " -",
                item
            )