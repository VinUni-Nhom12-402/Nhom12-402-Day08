# Báo Cáo Nhóm — Lab Day 08: Full RAG Pipeline

**Tên nhóm:** Nhom12-402-Day08  
**Thành viên:**
| Tên | Vai trò | Email |
|-----|---------|-------|
| Bùi Cao Chính | Tech Lead | ___ |
| Phan Xuân Quang Linh | Retrieval Owner | ___ |
| Nguyễn Đức Tiến | Eval Owner | ___ |
| Nguyễn Trọng Thiên Khôi | Documentation Owner | ___ |
| Trần Thị Kim Ngân | Retrieval support | ___ |
| Dương Chí Thành | Embedding / LLM support | ___ |

**Ngày nộp:** 14/04/2026  
**Repo:** Nhom12-402-Day08  
**Độ dài khuyến nghị:** 600–900 từ

---

> **Hướng dẫn nộp group report:**
>
> - File này nộp tại: `reports/group_report.md`
> - Deadline: Được phép commit **sau 18:00** (xem SCORING.md)
> - Tập trung vào **quyết định kỹ thuật cấp nhóm** — không trùng lặp với individual reports
> - Phải có **bằng chứng từ code, scorecard, hoặc tuning log** — không mô tả chung chung

---

## 1. Pipeline nhóm đã xây dựng (150–200 từ)

> Mô tả ngắn gọn pipeline của nhóm:
> - Chunking strategy: size, overlap, phương pháp tách (by paragraph, by section, v.v.)
> - Embedding model đã dùng
> - Retrieval mode: dense / hybrid / rerank (Sprint 3 variant)

**Chunking decision:**
> Nhóm dùng chunk_size=400 tokens, overlap=80 tokens, tách theo heading-based + paragraph để giữ cấu trúc section và giảm khả năng cắt ngang câu quan trọng. Cách này phù hợp với corpus policy/SLA/access control có nhiều điều khoản dài.

**Embedding model:**
> `paraphrase-multilingual-MiniLM-L12-v2` từ Sentence-Transformers, vì model này hỗ trợ tốt tiếng Việt và duy trì semantic quality cho cả policy text lẫn FAQ.

**Retrieval variant (Sprint 3):**
> Chọn hybrid retrieval (dense + BM25) + cross-encoder rerank để kết hợp semantic matching và exact keyword matching, đặc biệt hữu ích với các câu hỏi có tên riêng như `P1 ticket`, `Level 3 access` và alias cũ như `Approval Matrix`.

Pipeline end-to-end gồm indexing 5 documents vào ChromaDB, retrieval hybrid+rerrank, generation GPT-4o-mini với grounded prompt và evaluation bằng scorecard A/B.

---

## 2. Quyết định kỹ thuật quan trọng nhất (200–250 từ)

> Chọn **1 quyết định thiết kế** mà nhóm thảo luận và đánh đổi nhiều nhất trong lab.
> Phải có: (a) vấn đề gặp phải, (b) các phương án cân nhắc, (c) lý do chọn.

**Quyết định:** Chọn hybrid retrieval (dense + BM25) kèm cross-encoder rerank.

**Bối cảnh vấn đề:**
Baseline dense retrieval đạt Context Recall 5.00/5 nhưng Faithfulness chỉ 3.60/5 và Completeness chỉ 3.90/5. Điều này cho thấy retriever đã thu về đúng nguồn nhưng chunk selection chưa đủ tốt, khiến generation bị thiếu evidence hoặc hallucinate.

**Các phương án đã cân nhắc:**

| Phương án | Ưu điểm | Nhược điểm |
|-----------|---------|-----------|
| Dense only | Triển khai nhanh, latency thấp | Miss alias và exact keywords, ranking kém với tên riêng |
| Hybrid + rerank | Kết hợp semantic và keyword, chọn chunk chính xác hơn | Phức tạp hơn, latency tăng |
| Query expansion | Hỗ trợ paraphrase | Tăng cost LLM, không đảm bảo cải thiện exact match |

**Phương án đã chọn và lý do:**
Chọn hybrid+rerrank vì corpus có cả ngôn ngữ policy dài và tên riêng/ký hiệu kỹ thuật. Dense hiểu semantic, BM25 bắt keyword, cross-encoder rerank đánh giá query–chunk trực tiếp để chọn 3 chunk phù hợp nhất cho LLM.

**Bằng chứng từ scorecard/tuning-log:**
`docs/tuning-log.md` ghi variant tăng Faithfulness từ 3.60→3.90 và Completeness từ 3.90→4.20. `results/scorecard_variant.md` cũng xác nhận cải thiện nhất ở access control questions.

---

## 3. Kết quả grading questions (100–150 từ)

> Sau khi chạy pipeline với grading_questions.json (public lúc 17:00):
> - Câu nào pipeline xử lý tốt nhất? Tại sao?
> - Câu nào pipeline fail? Root cause ở đâu (indexing / retrieval / generation)?
> - Câu gq07 (abstain) — pipeline xử lý thế nào?

**Ước tính điểm raw:** 88 / 98

**Câu tốt nhất:** ID: gq07 — Lý do: Pipeline correctly abstained khi không có penalty information trong tài liệu, nên tránh hallucination và giữ grounded.

**Câu fail:** ID: gq03 — Root cause: retrieval/chunk selection. Pipeline lấy source đúng nhưng không đủ chunk cho hai ngoại lệ Flash Sale và sản phẩm kích hoạt, nên generation trả lời abstain sai.

**Câu gq07 (abstain):**
Pipeline trả lời “Rất tiếc, tôi không có đủ dữ liệu để trả lời vấn đề này.”, phù hợp với expected behavior và chứng tỏ prompt grounding hoạt động.

---

## 4. A/B Comparison — Baseline vs Variant (150–200 từ)

> Dựa vào `docs/tuning-log.md`. Tóm tắt kết quả A/B thực tế của nhóm.

**Biến đã thay đổi (chỉ 1 biến):** Retrieval mode từ `dense` sang `hybrid_rerank`.

| Metric | Baseline | Variant | Delta |
|--------|---------|---------|-------|
| Faithfulness | 3.60/5 | 3.90/5 | +0.30 |
| Answer Relevance | 4.20/5 | 4.20/5 | 0.00 |
| Context Recall | 5.00/5 | 5.00/5 | 0.00 |
| Completeness | 3.90/5 | 4.20/5 | +0.30 |

**Kết luận:**
Variant tốt hơn baseline ở faithfulness và completeness trong khi giữ nguyên recall và relevance. Điều này cho thấy hybrid+rerrank chọn chunks chính xác hơn cho LLM, đặc biệt cải thiện các câu access control có alias và keyword chính xác.

---

## 5. Phân công và đánh giá nhóm (100–150 từ)

> Đánh giá trung thực về quá trình làm việc nhóm.

**Phân công thực tế:**

| Thành viên | Phần đã làm | Sprint |
|------------|-------------|--------|
| Bùi Cao Chính | Tech Lead: architecture và grounded generation pipeline | 1-2 |
| Phan Xuân Quang Linh | Retrieval Owner: chunking, hybrid retrieval, rerank | 1-3 |
| Nguyễn Đức Tiến | Eval Owner: scorecard, grading run, A/B analysis | 3-4 |
| Nguyễn Trọng Thiên Khôi | Documentation Owner: tuning-log, architecture.md, report | 4 |
| Trần Thị Kim Ngân | Retrieval support: metadata, index building, hybrid variant testing | 1-3 |
| Dương Chí Thành | Embedding & LLM support: get_embedding, call_llm, prompt grounding | 1-3 |

**Điều nhóm làm tốt:**
Phân công rõ ràng, tài liệu và scorecard có evidence, giúp các quyết định kỹ thuật dễ review.

**Điều nhóm làm chưa tốt:**
Coordination giữa retrieval và generation còn thiếu chặt chẽ, nên một số lỗi q03/q05 chỉ được phát hiện muộn.

---

## 6. Nếu có thêm 1 ngày, nhóm sẽ làm gì? (50–100 từ)

> 1–2 cải tiến cụ thể với lý do có bằng chứng từ scorecard.

Nhóm sẽ thêm query routing để định tuyến query đơn giản sang sparse retrieval và query phức tạp sang hybrid+rerrank. Scorecard cho thấy q09/q10 vẫn yếu ở grounded generation, nên giảm noise trước khi vào LLM sẽ giúp nâng faithfulness mà vẫn giữ latency hợp lý.

---

*File này lưu tại: `reports/group_report.md`*  
*Commit sau 18:00 được phép theo SCORING.md*
