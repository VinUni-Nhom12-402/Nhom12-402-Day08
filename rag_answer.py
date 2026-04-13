"""
rag_answer.py — Sprint 2 + Sprint 3: Retrieval & Grounded Answer
================================================================
Sprint 2 (60 phút): Baseline RAG
  - Dense retrieval từ ChromaDB
  - Grounded answer function với prompt ép citation
  - Trả lời được ít nhất 3 câu hỏi mẫu, output có source

Sprint 3 (60 phút): Tuning tối thiểu
  - Thêm hybrid retrieval (dense + sparse/BM25)
  - Hoặc thêm rerank (cross-encoder)
  - Hoặc thử query transformation (expansion, decomposition, HyDE)
  - Tạo bảng so sánh baseline vs variant

Definition of Done Sprint 2:
  ✓ rag_answer("SLA ticket P1?") trả về câu trả lời có citation
  ✓ rag_answer("Câu hỏi không có trong docs") trả về "Không đủ dữ liệu"

Definition of Done Sprint 3:
  ✓ Có ít nhất 1 variant (hybrid / rerank / query transform) chạy được
  ✓ Giải thích được tại sao chọn biến đó để tune
"""

from fsspec import json
import os
import re
from typing import List, Dict, Any, Optional, Tuple
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# CẤU HÌNH
# =============================================================================

TOP_K_SEARCH = 10    # Số chunk lấy từ vector store trước rerank (search rộng)
TOP_K_SELECT = 3     # Số chunk gửi vào prompt sau rerank/select (top-3 sweet spot)

LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")

# Lazy-loaded singletons
_bm25_index = None
_bm25_chunks = None
_cross_encoder = None


# =============================================================================
# RETRIEVAL — DENSE (Vector Search)
# =============================================================================

def retrieve_dense(query: str, top_k: int = TOP_K_SEARCH) -> List[Dict[str, Any]]:
    """
    Dense retrieval: tìm kiếm theo embedding similarity trong ChromaDB.

    Args:
        query: Câu hỏi của người dùng
        top_k: Số chunk tối đa trả về

    Returns:
        List các dict, mỗi dict là một chunk với:
          - "text": nội dung chunk
          - "metadata": metadata (source, section, effective_date, ...)
          - "score": cosine similarity score
    """
    import chromadb, json
    from index import get_embedding, CHROMA_DB_DIR

    client = chromadb.PersistentClient(path=str(CHROMA_DB_DIR))
    collection = client.get_collection("rag_lab")

    query_embedding = get_embedding(query)
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )

    chunks = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        # ChromaDB cosine distance = 1 - similarity → score = 1 - distance
        score = 1.0 - dist
        chunks.append({
            "text": doc,
            "metadata": meta,
            "score": round(score, 4),
        })
    return chunks
        # Lưu ý: distances trong ChromaDB cosine = 1 - similarity
        # Score = 1 - distance

    # raise NotImplementedError(
    #     "TODO Sprint 2: Implement retrieve_dense().\n"
    #     "Tham khảo comment trong hàm để biết cách query ChromaDB."
    # )


# =============================================================================
# RETRIEVAL — SPARSE / BM25 (Keyword Search)
# Dùng cho Sprint 3 Variant hoặc kết hợp Hybrid
# =============================================================================

def _load_bm25_index():
    """Lazy-load BM25 index từ ChromaDB chunks."""
    global _bm25_index, _bm25_chunks

    if _bm25_index is not None:
        return _bm25_index, _bm25_chunks

    from rank_bm25 import BM25Okapi
    import chromadb
    from index import CHROMA_DB_DIR

    client = chromadb.PersistentClient(path=str(CHROMA_DB_DIR))
    collection = client.get_collection("rag_lab")

    # Lấy tất cả chunks
    all_data = collection.get(include=["documents", "metadatas"])
    _bm25_chunks = []
    corpus = []

    for doc_text, meta in zip(all_data["documents"], all_data["metadatas"]):
        _bm25_chunks.append({
            "text": doc_text,
            "metadata": meta,
        })
        corpus.append(doc_text.lower().split())

    _bm25_index = BM25Okapi(corpus)
    return _bm25_index, _bm25_chunks


def retrieve_sparse(query: str, top_k: int = TOP_K_SEARCH) -> List[Dict[str, Any]]:
    """
    Sparse retrieval: tìm kiếm theo keyword (BM25).

    Mạnh ở: exact term, mã lỗi, tên riêng (ví dụ: "ERR-403", "P1", "refund")
    Hay hụt: câu hỏi paraphrase, đồng nghĩa
    """
    bm25, chunks = _load_bm25_index()

    tokenized_query = query.lower().split()
    scores = bm25.get_scores(tokenized_query)

    # Lấy top_k indices
    top_indices = sorted(
        range(len(scores)),
        key=lambda i: scores[i],
        reverse=True,
    )[:top_k]

    results = []
    for idx in top_indices:
        if scores[idx] > 0:  # Chỉ lấy chunks có score > 0
            results.append({
                "text": chunks[idx]["text"],
                "metadata": chunks[idx]["metadata"],
                "score": round(float(scores[idx]), 4),
            })

    return results


# =============================================================================
# RETRIEVAL — HYBRID (Dense + Sparse với Reciprocal Rank Fusion)
# =============================================================================

def retrieve_hybrid(
    query: str,
    top_k: int = TOP_K_SEARCH,
    dense_weight: float = 0.6,
    sparse_weight: float = 0.4,
) -> List[Dict[str, Any]]:
    """
    Hybrid retrieval: kết hợp dense và sparse bằng Reciprocal Rank Fusion (RRF).

    Mạnh ở: giữ được cả nghĩa (dense) lẫn keyword chính xác (sparse)
    Phù hợp khi: corpus lẫn lộn ngôn ngữ tự nhiên và tên riêng/mã lỗi/điều khoản

    RRF_score(doc) = dense_weight * (1 / (60 + dense_rank)) +
                     sparse_weight * (1 / (60 + sparse_rank))
    """
    dense_results = retrieve_dense(query, top_k=top_k)
    sparse_results = retrieve_sparse(query, top_k=top_k)

    # Build RRF scores
    rrf_scores = {}   # key = chunk text hash → rrf score
    chunk_map = {}     # key = chunk text hash → chunk dict

    k = 60  # hằng số RRF tiêu chuẩn

    # Dense results: gán rank
    for rank, chunk in enumerate(dense_results):
        chunk_key = chunk["text"][:200]  # Dùng 200 ký tự đầu làm key
        rrf_scores[chunk_key] = rrf_scores.get(chunk_key, 0) + dense_weight * (1.0 / (k + rank))
        chunk_map[chunk_key] = chunk

    # Sparse results: gán rank
    for rank, chunk in enumerate(sparse_results):
        chunk_key = chunk["text"][:200]
        rrf_scores[chunk_key] = rrf_scores.get(chunk_key, 0) + sparse_weight * (1.0 / (k + rank))
        if chunk_key not in chunk_map:
            chunk_map[chunk_key] = chunk

    # Sort theo RRF score giảm dần
    sorted_keys = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)

    results = []
    for key in sorted_keys[:top_k]:
        chunk = chunk_map[key].copy()
        chunk["score"] = round(rrf_scores[key], 6)
        results.append(chunk)

    return results


# =============================================================================
# RERANK (Sprint 3 alternative)
# Cross-encoder để chấm lại relevance sau search rộng
# =============================================================================

def rerank(
    query: str,
    candidates: List[Dict[str, Any]],
    top_k: int = TOP_K_SELECT,
) -> List[Dict[str, Any]]:
    """
    Rerank các candidate chunks bằng cross-encoder.

    Cross-encoder: chấm lại "chunk nào thực sự trả lời câu hỏi này?"

    Funnel logic (từ slide):
      Search rộng (top-10) → Rerank → Select (top-3)
    """
    global _cross_encoder

    if not candidates:
        return []

    from sentence_transformers import CrossEncoder

    if _cross_encoder is None:
        print("  Loading CrossEncoder model...")
        _cross_encoder = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
        print("  CrossEncoder loaded!")

    pairs = [[query, chunk["text"]] for chunk in candidates]
    scores = _cross_encoder.predict(pairs)

    # Zip candidates và scores, sort giảm dần
    ranked = sorted(
        zip(candidates, scores),
        key=lambda x: float(x[1]),
        reverse=True,
    )

    results = []
    for chunk, score in ranked[:top_k]:
        new_chunk = chunk.copy()
        new_chunk["rerank_score"] = round(float(score), 4)
        results.append(new_chunk)

    return results


# =============================================================================
# QUERY TRANSFORMATION (Sprint 3 alternative)
# =============================================================================

def transform_query(query: str, strategy: str = "expansion") -> List[str]:
    """
    Biến đổi query để tăng recall.

    Strategies:
      - "expansion": Thêm từ đồng nghĩa, alias, tên cũ
      - "decomposition": Tách query phức tạp thành 2-3 sub-queries
      - "hyde": Sinh câu trả lời giả (hypothetical document) để embed thay query
    """

    # 1) Nếu chiến lược chưa được implement, trả về query gốc
    if strategy not in ("expansion", "decomposition", "hyde"):
        return [query]


    # 2) Gọi LLM để sinh biến thể query
    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        model = os.getenv("LLM_MODEL", "gpt-4o-mini")

        system_prompt = (
            "Bạn là hệ thống RAG. Nhiệm vụ của bạn là sinh ra "
            "2–3 phiên bản của câu hỏi sao cho:\n"
            "- Giữ nguyên nghĩa gốc.\n"
            "- Có thể dùng từ đồng nghĩa, alias, tên cũ, hoặc cách diễn đạt khác.\n"
            "- Chỉ trả về JSON object với key \"queries\" chứa danh sách các string.\n"
            "- Không giải thích gì thêm."
        )

        user_prompt = f"Query gốc: \"{query}\""

        if strategy == "expansion":
            user_prompt += (
                "\nHãy sinh ra 2–3 phiên bản paraphrase ngắn gọn, "
                "không dùng quá nhiều câu, ưu tiên các từ đồng nghĩa, alias hoặc tên cũ. "
                "Trả về JSON: {\"queries\": [\"...\", \"...\"]}"
            )

        elif strategy == "decomposition":
            user_prompt += (
                "\nNếu câu hỏi này phức tạp, hãy tách nó thành 2–3 câu hỏi đơn giản hơn. "
                "Trả về JSON: {\"queries\": [\"...\", \"...\"]}"
            )

        elif strategy == "hyde":
            user_prompt += (
                "\nHãy giả định một đoạn văn bản mà nếu có trong tài liệu, "
                "sẽ trả lời được câu hỏi này. "
                "Sau đó, dùng ý nghĩa của đoạn đó để sinh ra 2–3 câu hỏi tương tự "
                "nhưng diễn đạt khác đi. Trả về JSON: {\"queries\": [\"...\", \"...\"]}"
            )

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,
            max_tokens=200,
            response_format={"type": "json_object"},
        )

        raw_content = response.choices[0].message.content
        parsed = json.loads(raw_content)

        queries = parsed.get("queries", [])
        # Đảm bảo luôn có ít nhất query gốc
        if not queries:
            queries = [query]

        return queries

    except Exception as e:
        # Ưu tiên ít lỗi nhất → ít nhất là trả ra query gốc
        print(f"[transform_query] Lỗi khi sinh biến thể: {e}")
        return [query]


# =============================================================================
# GENERATION — GROUNDED ANSWER FUNCTION
# =============================================================================

def build_context_block(chunks: List[Dict[str, Any]]) -> str:
    """
    Đóng gói danh sách chunks thành context block để đưa vào prompt.

    Format: structured snippets với source, section, score (từ slide).
    Mỗi chunk có số thứ tự [1], [2], ... để model dễ trích dẫn.
    """
    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        meta = chunk.get("metadata", {})
        source = meta.get("source", "unknown")
        section = meta.get("section", "")
        score = chunk.get("score", 0)
        text = chunk.get("text", "")

        header = f"[{i}] {source}"
        if section:
            header += f" | {section}"
        if score > 0:
            header += f" | score={score:.2f}"

        context_parts.append(f"{header}\n{text}")

    return "\n\n".join(context_parts)


def build_grounded_prompt(
    query: str,
    context_block: str,
    output_format: str = "bullet points",
    language: str = "tiếng Việt",
    use_case: str = "CS helpdesk"
) -> str:
    """
    Xây dựng grounded prompt theo 4 quy tắc:
    1. Evidence-only: Chỉ trả lời từ retrieved context.
    2. Abstain: Thiếu context thì từ chối trả lời.
    3. Citation: Trích dẫn nguồn (nếu context có sẵn nhãn nguồn).
    4. Short, clear, stable: Phản hồi ngắn gọn.
    """

    # Xác định tone dựa trên use_case
    if use_case == "CS helpdesk":
        tone = "thân thiện, đồng cảm và lịch sự"
    else:
        tone = "chuyên nghiệp, kỹ thuật và súc tích"

    prompt = f"""
Bạn là một trợ lý ảo trợ giúp cho bộ phận {use_case}.
Hãy trả lời câu hỏi của người dùng dựa TRÊN DUY NHẤT thông tin trong phần [Context] dưới đây.

Tuân thủ nghiêm ngặt 4 quy tắc:
1. Evidence-only: Chỉ sử dụng thông tin từ [Context]. Không dùng kiến thức bên ngoài.
2. Abstain: Nếu [Context] không chứa câu trả lời, hãy phản hồi: "Rất tiếc, tôi không có đủ dữ liệu để trả lời vấn đề này."
3. Citation: Phải trích dẫn nguồn hoặc phần tương ứng (ví dụ: [Source 1], [Section A]) có sẵn trong [Context].
4. Short, clear, stable: Phản hồi ngắn gọn, đi thẳng vào vấn đề.

Yêu cầu cụ thể:
- Ngôn ngữ: {language}.
- Sắc thái (Tone): {tone}.
- Định dạng đầu ra: {output_format}.

[Context]:
{context_block}

[Câu hỏi]:
{query}

Trả lời:
""".strip()
    return prompt



def call_llm(prompt: str) -> str:
    """
    Gọi LLM để sinh câu trả lời.
    Hỗ trợ cả OpenAI và Google Gemini, tự động detect từ env.
    """
    provider = os.getenv("LLM_PROVIDER", "gemini").lower()

    if provider == "openai":
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=512,
        )
        return response.choices[0].message.content

    else:  # gemini (default)
        from google import genai

        client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
        response = client.models.generate_content(
            model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
            contents=prompt,
            config={
                "temperature": 0,
                "max_output_tokens": 512,
            },
        )
        return response.text

    # Lưu ý: Dùng temperature=0 hoặc thấp để output ổn định cho evaluation.

    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,     # temperature=0 để output ổn định, dễ đánh giá
        max_tokens=512,
    )
    return response.choices[0].message.content


def rag_answer(
    query: str,
    retrieval_mode: str = "dense",
    top_k_search: int = TOP_K_SEARCH,
    top_k_select: int = TOP_K_SELECT,
    use_rerank: bool = False,
    verbose: bool = False,
) -> Dict[str, Any]:
    """
    Pipeline RAG hoàn chỉnh: query → retrieve → (rerank) → generate.

    Args:
        query: Câu hỏi
        retrieval_mode: "dense" | "sparse" | "hybrid"
        top_k_search: Số chunk lấy từ vector store (search rộng)
        top_k_select: Số chunk đưa vào prompt (sau rerank/select)
        use_rerank: Có dùng cross-encoder rerank không
        verbose: In thêm thông tin debug

    Returns:
        Dict với:
          - "answer": câu trả lời grounded
          - "sources": list source names trích dẫn
          - "chunks_used": list chunks đã dùng
          - "query": query gốc
          - "config": cấu hình pipeline đã dùng
    """
    config = {
        "retrieval_mode": retrieval_mode,
        "top_k_search": top_k_search,
        "top_k_select": top_k_select,
        "use_rerank": use_rerank,
    }

    # --- Bước 1: Retrieve ---
    if retrieval_mode == "dense":
        candidates = retrieve_dense(query, top_k=top_k_search)
    elif retrieval_mode == "sparse":
        candidates = retrieve_sparse(query, top_k=top_k_search)
    elif retrieval_mode == "hybrid":
        candidates = retrieve_hybrid(query, top_k=top_k_search)
    else:
        raise ValueError(f"retrieval_mode không hợp lệ: {retrieval_mode}")

    if verbose:
        print(f"\n[RAG] Query: {query}")
        print(f"[RAG] Retrieved {len(candidates)} candidates (mode={retrieval_mode})")
        for i, c in enumerate(candidates[:3]):
            print(f"  [{i+1}] score={c.get('score', 0):.3f} | {c['metadata'].get('source', '?')}")

    # --- Bước 2: Rerank (optional) ---
    if use_rerank:
        candidates = rerank(query, candidates, top_k=top_k_select)
    else:
        candidates = candidates[:top_k_select]

    if verbose:
        print(f"[RAG] After select: {len(candidates)} chunks")

    # --- Bước 3: Build context và prompt ---
    context_block = build_context_block(candidates)
    prompt = build_grounded_prompt(query, context_block)

    if verbose:
        print(f"\n[RAG] Prompt:\n{prompt[:500]}...\n")

    # --- Bước 4: Generate ---
    answer = call_llm(prompt)

    # --- Bước 5: Extract sources ---
    sources = list({
        c["metadata"].get("source", "unknown")
        for c in candidates
    })

    return {
        "query": query,
        "answer": answer,
        "sources": sources,
        "chunks_used": candidates,
        "config": config,
    }


# =============================================================================
# SPRINT 3: SO SÁNH BASELINE VS VARIANT
# =============================================================================

def compare_retrieval_strategies(query: str) -> None:
    """
    So sánh các retrieval strategies với cùng một query.

    A/B Rule (từ slide): Chỉ đổi MỘT biến mỗi lần.
    """
    print(f"\n{'='*60}")
    print(f"Query: {query}")
    print('='*60)

    strategies = [
        {"label": "dense", "mode": "dense", "rerank": False},
        {"label": "hybrid", "mode": "hybrid", "rerank": False},
        {"label": "hybrid+rerank", "mode": "hybrid", "rerank": True},
    ]

    for strategy in strategies:
        print(f"\n--- Strategy: {strategy['label']} ---")
        try:
            result = rag_answer(
                query,
                retrieval_mode=strategy["mode"],
                use_rerank=strategy["rerank"],
                verbose=False,
            )
            print(f"Answer: {result['answer']}")
            print(f"Sources: {result['sources']}")
        except Exception as e:
            print(f"Lỗi: {e}")


# =============================================================================
# MAIN — Demo và Test
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Sprint 2 + 3: RAG Answer Pipeline")
    print("=" * 60)

    # Test queries từ data/test_questions.json
    test_queries = [
        "SLA xử lý ticket P1 là bao lâu?",
        "Khách hàng có thể yêu cầu hoàn tiền trong bao nhiêu ngày?",
        "Ai phải phê duyệt để cấp quyền Level 3?",
        "ERR-403-AUTH là lỗi gì?",  # Query không có trong docs → kiểm tra abstain
    ]

    print("\n--- Sprint 2: Test Baseline (Dense) ---")
    for query in test_queries:
        print(f"\nQuery: {query}")
        try:
            result = rag_answer(query, retrieval_mode="dense", verbose=True)
            print(f"Answer: {result['answer']}")
            print(f"Sources: {result['sources']}")
        except Exception as e:
            print(f"Lỗi: {e}")

    # Sprint 3: So sánh strategies
    print("\n--- Sprint 3: So sánh strategies ---")
    compare_retrieval_strategies("Approval Matrix để cấp quyền là tài liệu nào?")
    compare_retrieval_strategies("SLA xử lý ticket P1 là bao lâu?")

    print("\n\nSprint 2 + 3 hoàn thành!")
