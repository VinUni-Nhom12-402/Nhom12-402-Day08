# Báo Cáo Cá Nhân — Lab Day 08: RAG Pipeline

**Họ và tên:** Nguyễn Trọng Thiên Khôi  
**Vai trò trong nhóm:** Documentation Owner  


---

## 1. Tôi đã làm gì trong lab này?

Tôi là Documentation Owner, chịu trách nhiệm viết và duy trì toàn bộ tài liệu kiến trúc hệ thống và quá trình tối ưu (tuning). Cụ thể:

**Sprint 4:** Hoàn thiện file `architecture.md` với 4 section chi tiết:
- Section 1: Tổng quan kiến trúc (pipeline diagram, mục tiêu hệ thống)
- Section 2: Indexing pipeline + quyết định chunking (chunk size, overlap, metadata fields)
- Section 3: Retrieval strategy (baseline vs variant A/B comparison)
- Section 4: Generation pipeline (LLM prompts, citation enforcement)

**Tuning log:** Viết `tuning-log.md` ghi lại baseline configuration, hypothesis của variant, thay đổi config cụ thể, kết quả scorecard, và nhận xét chi tiết từng câu hỏi. Điều này giúp team tracking được tại sao variant tốt hơn baseline (faithfulness +8.3%, completeness +7.7%).

**Group report:** Viết phần tổng quan dự án, kiến trúc kỹ thuật, thách thức gặp phải, giải pháp đưa ra. Đây là tài liệu tổng hợp toàn bộ insight từ các sprint.

**Definition of Done:** Tôi cũng giám sát DoD checklist của từng sprint (4 sprint total), nhắc nhở team về deliverables, quality standards, review schedule. Trong sprint 4, đảm bảo tất cả tài liệu pass review trước khi nộp.

Công việc của tôi kết nối trực tiếp với các thành viên khác: nhận feedback từ Tech Lead về pipeline decisions, hỏi Retrieval Owner về các thử nghiệm hybrid search, hỏi Eval Owner về metric definitions—để documentation chính xác và đầy đủ.

---

## 2. Điều tôi hiểu rõ hơn sau lab này

**Hybrid Retrieval Strategy:** Trước lab này, tôi nghĩ dense search (vector similarity) là đủ cho hầu hết trường hợp. Nhưng sau khi viết về variant hybrid + cross-encoder rerank, tôi thấu hiểu rằng:
- Corpus có 2 loại thông tin: **semantic** (policy descriptions toàn văn) và **keyword exact** (tên riêng như "P1 ticket", "Level 3 access")
- Dense embedding hiểu paraphrase nhưng miss tên riêng; BM25 bắt keyword nhưng không hiểu semantic
- Cross-encoder rerank không tìm kiếm mà score từng (query, chunk) pair—nó "hiểu" được sự phù hợp cụ thể hơn
- Kết quả: variant tăng faithfulness từ 3.60→3.90 (8.3%), đặc biệt ở access control questions với tên riêng

Điều này dạy tôi rằng **không có retrieval strategy nào là "tốt nhất" cho mọi corpus**—cần hiểu dữ liệu để chọn đúng.

**Documentation as System Thinking:** Viết architecture.md không phải chỉ mô tả code mà buộc tôi phải suy nghĩ về **tại sao** mỗi quyết định lại được chọn. Ví dụ: tại sao chunk size 400 tokens chứ không 300 hoặc 500? Tại sao overlap 80 tokens? Những câu hỏi này buộc phải tìm evidence (eval metrics, trade-offs) để justify.

---

## 3. Điều tôi ngạc nhiên hoặc gặp khó khăn

**Khó khăn lớn nhất:** Giữ documentation **sync với code thay đổi**. Team thường refactor code hoặc thay config giữa sprint, nhưng lại quên update docs. Ví dụ:
- Sprint 2: Dense search top-k = 10 → Sprint 3: Hybrid search top-k = 20 (merge dense+sparse results)
- Nếu docs không update kịp, tài liệu trở nên sai lệch, confuse người đọc

**Giải pháp tôi áp dụng:** Sau mỗi sprint, tôi yêu cầu code owner gửi change log (thay đổi config, parameters), rồi tôi update docs ngay. Tôi cũng thêm "Last Updated" timestamp để track freshness.

**Ngạc nhiên:** Giải thích kết quả A/B testing chính xác lại khó hơn tôi tưởng. Ví dụ, variant cải thiện faithfulness +8.3% nhưng tôi phải trả lời: "Cải thiện ở câu nào? Tại sao?" Trả lời không phải chỉ "faithfulness tăng" mà phải trace được q01 (SLA) completeness 4→5, q07 (Access Control) faithfulness 3→5—tức là hybrid + rerank pick chunks đúng hơn.

---

## 4. Phân tích một câu hỏi trong scorecard

**Câu hỏi:** `gq06` — "Lúc 2 giờ sáng xảy ra sự cố P1, on-call engineer cần cấp quyền tạm thời cho một engineer xử lý incident. Quy trình cụ thể như thế nào và quyền này tồn tại bao lâu?"

**Phân tích:**

Baseline trả lời đúng (~4/5 completeness), nhưng thiếu chi tiết về **approval by Tech Lead**. Câu hỏi này test kiến thức về **emergency access procedures** (Section 4 của access_control_sop.txt) kết hợp với **P1 SLA urgency** (sla_p1_2026.txt).

**Lỗi baseline:** Dense search tìm được chunks từ access_control_sop nhưng chunks này nó pick có thể là về "standard approval" chứ không phải "emergency approval with verbal authorization". Vì overlap giữa 2 sections này là subtle (cùng document nhưng khác semantic—standard vs emergency), dense embedding dễ nhầm.

**Variant cải thiện:** Hybrid model:
- **Dense:** Tìm chunks language-wise similar (keyword "P1", "on-call", "temporary access")
- **BM25:** Bắt exact keyword "24 hours", "verbal authorization", "Tech Lead approval"
- **Cross-encoder rerank:** Score từng (query, chunk) pair như "emergency + 24 hours limit + Tech Lead" → pick chunk chứa đầy đủ 3 info này

**Kết quả:** Variant trả lời đầy đủ: quy trình (on-call IT Admin cấp sau phê duyệt lời từ Tech Lead), thời hạn (max 24h), log requirement (Security Audit log). Score từ 4/5 → 5/5.

**Học được:** Những câu hỏi "procedure-heavy" (bước 1→2→3→4) cần retrieval chính xác hơn vì ngay 1 bước sai là answer sai. Hybrid + rerank là strategy tốt cho dạng docs này.

---

## 5. Nếu có thêm thời gian, tôi sẽ làm gì?

1. **Thêm Architecture Diagram Mermaid.js** vào architecture.md với:
   - Indexing flow (documents → chunks → embeddings → ChromaDB)
   - Retrieval flow (query → dense + sparse → rerank → select)
   - Generation flow (LLM + context → answer + citation)
   
   Diagram sẽ giúp người đọc visualize nhanh hơn text mô tả.

2. **Viết Decision Records (ADR)** cho mỗi major design choice:
   - ADR-001: Tại sao chọn chunk size 400 tokens (vs 300 hoặc 800)?
   - ADR-002: Tại sao chọn cross-encoder rerank (vs query expansion)?
   
   Mỗi ADR ghi status (accepted/rejected), context, trade-offs—giúp team future cải thiện mà không lặp lại sai lầm.

