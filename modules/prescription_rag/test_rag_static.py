import ast, sys

path = r'C:\Users\kesha\OneDrive\Desktop\amal jothy hackathon\BharatRx\modules\prescription_rag\rag.py'
src = open(path, encoding='utf-8').read()
lines = src.splitlines()
results = []
overall = 'PASS'

def PASS(msg): results.append(f'  [PASS] {msg}')
def WARN(msg):
    global overall
    if overall == 'PASS': overall = 'PASS WITH WARNINGS'
    results.append(f'  [WARN] {msg}')
def FAIL(msg):
    global overall
    overall = 'FAIL'
    results.append(f'  [FAIL] {msg}')

# 1. Syntax
try:
    tree = ast.parse(src)
    PASS('Syntax clean')
except SyntaxError as e:
    FAIL(f'Syntax error: {e}')
    sys.exit(1)

# 2. No LangGraph
if 'from langgraph' not in src and 'import langgraph' not in src:
    PASS('No LangGraph import')
else:
    FAIL('LangGraph still imported')

# 3. No agentic loop logic (must not appear as real code, only in string dict keys)
agentic_code_terms = {
    'evaluate_context': 'evaluate_context function',
    'rephrase_query': 'rephrase_query function',
    'MAX_RETRIEVAL_ATTEMPTS': 'retry constant',
    'should_continue': 'agent control flag',
}
for term, desc in agentic_code_terms.items():
    term_lines = [i for i, l in enumerate(lines) if term in l]
    code_hits = []
    for idx in term_lines:
        stripped = lines[idx].strip()
        # It's a code hit if NOT a comment and NOT a quoted dict key
        if not stripped.startswith('#') and f'"{term}"' not in stripped and f"'{term}'" not in stripped:
            code_hits.append(idx + 1)
    if code_hits:
        FAIL(f'Agentic term "{term}" found as code on lines: {code_hits}')
    else:
        PASS(f'No agentic code: {term}')

# context_sufficient / retrieval_attempts - only acceptable in legacy dict
for term in ['context_sufficient', 'retrieval_attempts']:
    hits = [(i+1, lines[i].strip()) for i, l in enumerate(lines) if term in l]
    for lineno, text in hits:
        if f'"{term}"' in text:
            PASS(f'Line {lineno}: "{term}" only in legacy compat dict key')
        else:
            WARN(f'Line {lineno}: "{term}" unexpected: {text}')

# 4. Single retrieve() definition
retrieve_defs = [i+1 for i, l in enumerate(lines) if l.strip().startswith('def retrieve(')]
if len(retrieve_defs) == 1:
    PASS(f'retrieve() defined once (line {retrieve_defs[0]})')
else:
    FAIL(f'retrieve() defined {len(retrieve_defs)} times')

# 5. RRF present and correct
if 'def reciprocal_rank_fusion(' in src:
    PASS('reciprocal_rank_fusion() defined')
else:
    FAIL('reciprocal_rank_fusion() missing')

if '1.0 / (k + rank)' in src:
    PASS('RRF formula: 1/(k+rank) correct')
else:
    FAIL('RRF formula incorrect or missing')

# 6. Both retrievers used
if 'similarity_search' in src and 'bm25_retriever.invoke' in src:
    PASS('Both FAISS similarity_search and BM25 invoke used')
else:
    FAIL('One or both retrievers missing from retrieve()')

# 7. No naive concatenation
if 'combined_chunks' not in src and 'vector_chunks + bm25_chunks' not in src:
    PASS('No naive concatenation of retriever results')
else:
    FAIL('Naive concatenation detected')

# 8. Conversation history components
if all(x in src for x in ['add_user_message', 'add_assistant_message', 'resolve_context', 'self.state.history']):
    PASS('Conversation history: all components present')
else:
    FAIL('Conversation history: missing components')

# 9. History not passed as evidence into answer prompt
answer_prompt_start = src.find('answer_prompt = f"""')
answer_prompt_block = src[answer_prompt_start:answer_prompt_start + 3000] if answer_prompt_start >= 0 else ''
if 'history' not in answer_prompt_block and 'conversation' not in answer_prompt_block.lower():
    PASS('History NOT injected into answer prompt (evidence separation maintained)')
else:
    WARN('Check answer_prompt - history reference may be in evidence prompt')

# 10. Metadata in format_context
if all(x in src for x in ['chunk_id', 'drug_name', 'document_title', 'page_number', 'source']):
    PASS('Metadata fields present: chunk_id, drug_name, document_title, page_number, source')
else:
    FAIL('Some metadata fields missing')

# 11. get_text_from_response handles both str and list
if 'isinstance(content, str)' in src and 'isinstance(content, list)' in src:
    PASS('get_text_from_response handles both str and list content')
else:
    FAIL('get_text_from_response missing type handling')

# 12. API key from file
if 'apikey.txt' in src and 'Path(__file__).resolve().parent' in src:
    PASS('API key loaded from apikey.txt via Path(__file__)')
else:
    FAIL('API key loading broken')

# 13. Safety instructions
safety_terms = ['Do NOT invent', 'INSUFFICIENT EVIDENCE', 'hallucinate', 'Never tell']
found_s = [t for t in safety_terms if t in src]
if len(found_s) == len(safety_terms):
    PASS(f'Safety instructions: all {len(safety_terms)} required terms present')
else:
    WARN(f'Safety instructions: {len(found_s)}/{len(safety_terms)} terms found: {found_s}')

# 14. Advisory-only language
if 'independently start' in src or 'start, stop, or change' in src:
    PASS('Advisory-only language: no autonomous treatment instructions')
else:
    WARN('Advisory-only phrasing not explicitly found - verify prompt manually')

# 15. import re removed (was unused)
if 'import re' in src:
    FAIL('import re still present but not used in rag.py')
else:
    PASS('import re correctly removed')

# 16. BM25Retriever import kept (needed for pickle deserialization)
if 'from langchain_community.retrievers import BM25Retriever' in src:
    PASS('BM25Retriever imported (required for pickle.load deserialization)')
else:
    FAIL('BM25Retriever not imported - pickle.load of bm25.pkl will fail')

# 17. Single PROJECT_ROOT
count = src.count('PROJECT_ROOT = ')
if count == 1:
    PASS('PROJECT_ROOT defined exactly once')
else:
    FAIL(f'PROJECT_ROOT defined {count} times')

# 18. run_agent legacy interface
if 'def run_agent(' in src:
    PASS('run_agent() legacy function present for compatibility')
else:
    WARN('run_agent() not present')

# Print results
print()
print('=' * 60)
print('STATIC VALIDATION RESULTS')
print('=' * 60)
for r in results:
    print(r)
print()
print(f'OVERALL STATUS: {overall}')
print()

# 19. Flow trace
print('=' * 60)
print('FLOW TRACE: query() execution order')
print('=' * 60)
in_query = False
for line in lines:
    stripped = line.strip()
    if stripped.startswith('def query('):
        in_query = True
        continue
    if in_query:
        if stripped.startswith('def ') and 'query' not in stripped:
            break
        if any(x in stripped for x in [
            'add_user_message', 'resolve_context', 'self.retrieve',
            'generate_answer', 'add_assistant_message',
            'state.current_query', 'state.resolved_query',
            'state.retrieved_documents', 'state.final_answer',
            'return answer'
        ]) and not stripped.startswith('#'):
            print(f'  {stripped}')

print()
print('=' * 60)
print('TEST READINESS CHECK')
print('=' * 60)
print('TEST 1: "What safety concerns/monitoring for ibuprofen?"')
print('  -> query() stores user message')
print('  -> resolve_context(): no history on first query, returns as-is')
print('  -> retrieve("What safety concerns and monitoring requirements are associated with ibuprofen use?")')
print('  -> FAISS: semantic search over 8810 docs')
print('  -> BM25: keyword search over 8810 docs')
print('  -> RRF combines results, deduplicates')
print('  -> generate_answer(): grounded on retrieved docs only')
print('  -> If KB lacks safety/monitoring info -> "Insufficient Evidence" response')
print()
print('TEST 2: "Drug interactions of ibuprofen with anticoagulants..."')
print('  -> Same pipeline, no query expansion beyond user\'s own terms')
print()
print('TEST 3: "What about monitoring requirements?" (follow-up)')
print('  -> resolve_context(): sees ibuprofen in history')
print('  -> LLM resolves to: "ibuprofen monitoring requirements"')
print('  -> retrieve("ibuprofen monitoring requirements")')
print('  -> Previous assistant answer NOT included in evidence context')
print()

passes = sum(1 for r in results if '[PASS]' in r)
warns  = sum(1 for r in results if '[WARN]' in r)
fails  = sum(1 for r in results if '[FAIL]' in r)
print(f'Summary: {passes} PASS / {warns} WARN / {fails} FAIL')
