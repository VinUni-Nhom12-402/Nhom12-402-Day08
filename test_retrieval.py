"""Quick Sprint 2 test: dense retrieval + Gemini LLM."""
import os
os.environ["PYTHONIOENCODING"] = "utf-8"

from rag_answer import rag_answer

queries = [
    "SLA xu ly ticket P1 la bao lau?",
    "Khach hang co the yeu cau hoan tien trong bao nhieu ngay?",
    "Ai phai phe duyet de cap quyen Level 3?",
    "ERR-403-AUTH la loi gi?",
]

for q in queries:
    print(f"\n{'='*60}")
    print(f"Q: {q}")
    try:
        result = rag_answer(q, retrieval_mode="dense", verbose=False)
        print(f"A: {result['answer']}")
        print(f"Sources: {result['sources']}")
    except Exception as e:
        print(f"Error: {e}")
