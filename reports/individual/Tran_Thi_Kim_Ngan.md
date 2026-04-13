# Báo Cáo Cá Nhân — Lab Day 08: RAG Pipeline

**Họ và tên:** Trần Thị Kim Ngân 
**Vai trò trong nhóm:**  Retrieval Owner  
**Ngày nộp:** 4/13/2026
**Độ dài yêu cầu:** 500–800 từ
**Mã học viên**: 2A202600432

---

## 1. Tôi đã làm gì trong lab này? (100-150 từ)

> Mô tả cụ thể phần bạn đóng góp vào pipeline:
> - Sprint nào bạn chủ yếu làm?
> - Cụ thể bạn implement hoặc quyết định điều gì?
> - Công việc của bạn kết nối với phần của người khác như thế nào?


Em đảm nhận vai trò Retrieval Owner, chịu trách nhiệm Sprint 1 (chunking strategy, metadata, build index) và Sprint 3 (retrieval variants). Trong Sprint 1, em thiết kế chunking theo cấu trúc tự nhiên (heading → paragraph → câu + overlap 80 tokens), gắn 5 metadata fields có ý nghĩa (source, section, department, effective_date, access), và build pipeline hoàn chỉnh từ data/docs/ → ChromaDB với Sentence Transformers local. Sprint 3, em implement 3 variants: retrieve_hybrid (dense + BM25 + RRF), rerank (cross-encoder ms-marco), transform_query (expansion/decomposition/HyDE bằng LLM). Công việc tạo foundation vững cho Answer Owner pipeline và baseline + variants để so sánh đánh giá, đảm bảo hệ thống retrieval đủ mạnh, linh hoạt cho production RAG.
---

## 2. Điều tôi hiểu rõ hơn sau lab này (100-150 từ)

> Chọn 1-2 concept từ bài học mà bạn thực sự hiểu rõ hơn sau khi làm lab.
> Ví dụ: chunking, hybrid retrieval, grounded prompt, evaluation loop.
> Giải thích bằng ngôn ngữ của bạn — không copy từ slide.


Sau lab, em hiểu rõ hơn về hybrid retrieval.

Hybrid retrieval không phải chỉ "mix dense + sparse" mà là dùng Reciprocal Rank Fusion (RRF) để kết hợp thông minh: dense mạnh về semantic (nghĩa câu hỏi tự nhiên), sparse mạnh về keyword (mã lỗi, tên cũ). Thay vì chọn 1, em dùng cả 2 rồi cân bằng bằng công thức toán học (1/(60+rank)) để chunk nào thực sự relevant sẽ nổi lên top, dù nó rank thấp ở 1 trong 2 phương pháp.


_________________

---

## 3. Điều tôi ngạc nhiên hoặc gặp khó khăn (100-150 từ)

> Điều gì xảy ra không đúng kỳ vọng?
> Lỗi nào mất nhiều thời gian debug nhất?
> Giả thuyết ban đầu của bạn là gì và thực tế ra sao?

Điều ngạc nhiên nhất là q09, q10 điểm thấp dù prompt đã "ép abstain" rất chặt. Em tưởng chỉ cần viết "Evidence-only, không suy luận" là model sẽ ngoan ngoãn trả lời "không có dữ liệu", nhưng thực tế LLM vẫn tự suy diễn (q09 đoán ERR-403 là authentication error, q10 tự thêm quy trình VIP).

Debug khó nhất là chunk_key collision trong retrieve_hybrid: dùng chunk["text"][:200] làm key nhưng 2 chunk khác nhau có thể trùng 200 ký tự đầu → RRF score bị merge sai. Phải đổi sang hash(text + metadata) mới fix được.

Giả thuyết ban đầu: hybrid retrieval sẽ cải thiện tất cả câu hỏi, nhưng thực tế chỉ cải thiện q07 (alias "Approval Matrix"), còn q09/q10 vẫn kém vì vấn đề nằm ở prompt grounding, không phải retrieval.
_________________

---

## 4. Phân tích một câu hỏi trong scorecard (150-200 từ)

> Chọn 1 câu hỏi trong test_questions.json mà nhóm bạn thấy thú vị.
> Phân tích:
> - Baseline trả lời đúng hay sai? Điểm như thế nào?
> - Lỗi nằm ở đâu: indexing / retrieval / generation?
> - Variant có cải thiện không? Tại sao có/không?

**Câu hỏi:** q07 - "Approval Matrix để cấp quyền hệ thống là tài liệu nào?" (hard, Access Control)

**Phân tích:**
Baseline (dense): Điểm thấp (faithfulness=3, completeness=3). Dense chỉ tìm theo semantic nên miss hoàn toàn vì tài liệu đổi tên từ "Approval Matrix" → "Access Control SOP". Model trả lời chung chung về quy trình hoặc không tìm thấy tài liệu đúng → it/access-control-sop.md.

Lỗi nằm ở retrieval: Indexing đã chunk đúng (metadata source=it/access-control-sop.md, section=Section 1), nhưng dense embedding không bắt được alias/tên cũ. Docs có ghi chú "trước đây có tên Approval Matrix" nhưng semantic search không mạnh với keyword matching.

Variant cải thiện rõ rệt: variant_hybrid_rerank tăng lên faithfulness=5, completeness=3.

Hybrid: BM25 bắt được keyword "Approval Matrix" → đưa chunk đúng vào top candidates.

Rerank: Cross-encoder xác nhận chunk đó thực sự relevant với câu hỏi.

→ Hybrid + rerank giải quyết đúng vấn đề alias naming, cải thiện từ 60% → 90% accuracy cho câu hỏi kiểu này.

_________________

---

## 5. Nếu có thêm thời gian, tôi sẽ làm gì? (50-100 từ)

> 1-2 cải tiến cụ thể bạn muốn thử.
> Không phải "làm tốt hơn chung chung" mà phải là:
> "Tôi sẽ thử X vì kết quả eval cho thấy Y."

1. Fix prompt grounding cho q09/q10: Kết quả eval cho thấy faithfulness=1 dù đã có quy tắc abstain. Tôi sẽ thử few-shot prompting với 2 ví dụ cụ thể (ERR-403, VIP refund) để ép model không suy luận, chỉ nói "không có dữ liệu" khi context thiếu → tăng faithfulness lên 4-5.

2. MMR reranking: context_recall=5 nhưng nhiều chunk trùng lặp. Thêm Maximal Marginal Relevance sau hybrid retrieval để đa dạng hóa sources, tránh 3 chunk cùng 1 file → cải thiện completeness cho câu hỏi multi-document như q06.
_________________

---

*Lưu file này với tên: `reports/individual/[ten_ban].md`*
*Ví dụ: `reports/individual/nguyen_van_a.md`*
