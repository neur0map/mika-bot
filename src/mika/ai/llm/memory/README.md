# ai/llm/memory

Provider-facing memory adapters.

- `store.py` persists the ordered recent channel window through the primary database.
- `honcho.py` is optional semantic recall. Core conversation behavior never depends on it.

Local long-term social context lives behind `conversation/context`: explicit facts, bounded
same-user/same-channel candidates, and aggregate reaction feedback are retrieved from the primary
database. Deterministic lexical scoring is the embedded default; the retriever protocol leaves room
for embeddings later without coupling conversation behavior to a vector vendor.
