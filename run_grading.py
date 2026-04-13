"""
run_grading.py — Chạy pipeline với grading_questions.json lúc 17:00
====================================================================
Chạy lệnh: python run_grading.py
Output: logs/grading_run.json
"""

import json
from pathlib import Path
from datetime import datetime
from rag_answer import rag_answer

GRADING_QUESTIONS_PATH = Path(__file__).parent / "data" / "grading_questions.json"
LOG_PATH = Path(__file__).parent / "logs" / "grading_run.json"

def main():
    print("=" * 60)
    print("Grading Run — RAG Pipeline")
    print("=" * 60)

    if not GRADING_QUESTIONS_PATH.exists():
        print(f"Chưa có file: {GRADING_QUESTIONS_PATH}")
        print("Chờ grading_questions.json được public lúc 17:00 rồi chạy lại.")
        return

    with open(GRADING_QUESTIONS_PATH, "r", encoding="utf-8") as f:
        questions = json.load(f)

    print(f"Tìm thấy {len(questions)} câu hỏi grading\n")

    log = []
    for q in questions:
        print(f"[{q['id']}] {q['question']}")
        try:
            result = rag_answer(
                query=q["question"],
                retrieval_mode="hybrid",
                use_rerank=True,
                verbose=False,
            )
            entry = {
                "id": q["id"],
                "question": q["question"],
                "answer": result["answer"],
                "sources": result["sources"],
                "chunks_retrieved": len(result["chunks_used"]),
                "retrieval_mode": result["config"]["retrieval_mode"],
                "timestamp": datetime.now().isoformat(),
            }
            print(f"  → {result['answer'][:80]}...")
        except Exception as e:
            entry = {
                "id": q["id"],
                "question": q["question"],
                "answer": f"PIPELINE_ERROR: {e}",
                "sources": [],
                "chunks_retrieved": 0,
                "retrieval_mode": "hybrid",
                "timestamp": datetime.now().isoformat(),
            }
            print(f"  → ERROR: {e}")

        log.append(entry)

    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)

    print(f"\nDone! Log lưu tại: {LOG_PATH}")
    print(f"Tổng: {len(log)} câu")

if __name__ == "__main__":
    main()
