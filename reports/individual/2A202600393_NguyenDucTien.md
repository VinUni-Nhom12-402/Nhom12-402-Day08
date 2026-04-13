# Individual Report — 2A202600393 Nguyễn Đức Tiến

## 1. Đóng góp cụ thể

Tôi phụ trách Sprint 3–4 với vai trò Eval Owner, tập trung vào việc đo lường chất lượng pipeline một cách khách quan.

**Sprint 4 — eval.py:**

- Implement LLM-as-Judge cho 3 hàm scoring: `score_faithfulness()`, `score_answer_relevance()`, `score_completeness()`. Mỗi hàm gửi prompt có cấu trúc tới LLM, parse JSON response, trả về điểm 1–5 kèm lý do.
- Uncomment và kích hoạt phần chạy variant scorecard (`VARIANT_CONFIG`: hybrid + rerank) và `compare_ab()` trong main block.
- Chạy end-to-end 10 câu hỏi cho cả baseline (dense) và variant (hybrid+rerank), sinh ra `scorecard_baseline.md`, `scorecard_variant.md`, và `ab_comparison.csv`.

**Metric `score_context_recall()`** đã có sẵn logic partial-match, tôi giữ nguyên vì logic đúng — kiểm tra tên file trong retrieved sources.

---

## 2. Phân tích câu grading: q03 — "Ai phải phê duyệt để cấp quyền Level 3?"

Đây là câu pipeline trả lời đúng nội dung nhưng bị LLM-as-Judge chấm **Faithfulness thấp** (baseline: 1/5, variant: 2/5), trong khi Relevance và Recall đều 5/5.

**Pipeline xử lý như thế nào:**

- Retrieval lấy đúng source `it/access-control-sop.md` (Recall = 5/5).
- Answer đúng: "Line Manager + IT Admin + IT Security".
- Nhưng Faithfulness thấp vì trong retrieved chunks, thông tin về Level 3 nằm rải rác ở nhiều đoạn, model tổng hợp lại thành một câu gọn — LLM-as-Judge đánh giá đây là "synthesis" chứ không phải trích dẫn trực tiếp, nên trừ điểm.

**Root cause:** Chunking cắt section "Phân cấp quyền truy cập" thành nhiều chunk nhỏ. Chunk nào được retrieve chưa chắc chứa đủ cả 3 approver trong một đoạn liên tục. Model phải tổng hợp từ nhiều chunk → LLM-as-Judge coi đó là hallucination tiềm năng.

**Đề xuất fix:** Tăng chunk size hoặc giảm overlap để giữ nguyên cả bảng phân cấp trong một chunk. Hoặc dùng metadata filter theo `section` để ưu tiên chunk từ "Section 2: Phân cấp quyền".

---

## 3. Rút kinh nghiệm

Điều ngạc nhiên nhất là **Context Recall đạt 5.00/5 cho cả baseline lẫn variant**, nhưng Faithfulness chỉ 3.60 và 3.90. Tôi ban đầu nghĩ retrieval tốt thì generation sẽ tốt theo — thực tế không phải vậy.

Retriever lấy đúng document, nhưng chunk được lấy không phải lúc nào cũng chứa đúng đoạn cần thiết. Model vẫn có thể trả lời đúng nhờ "may mắn" hoặc nhờ prior knowledge, nhưng điều đó lại bị Faithfulness penalize vì không grounded rõ ràng trong context.

Một khó khăn thực tế: LLM-as-Judge không hoàn toàn nhất quán — cùng một answer, chạy lại có thể cho điểm khác. Đây là lý do cần `temperature=0` khi gọi LLM để chấm điểm.

---

## 4. Đề xuất cải tiến

**Cải tiến 1 — Chunking theo bảng/danh sách:**
Từ scorecard thấy q03 và q07 có Faithfulness thấp nhất (1–3/5). Cả hai câu đều hỏi về thông tin dạng bảng (approval matrix, access levels). Nên implement chunking đặc biệt cho cấu trúc bảng — giữ nguyên toàn bộ bảng trong một chunk thay vì cắt theo số ký tự.

**Cải tiến 2 — Metadata filter khi retrieve:**
Variant hybrid+rerank cải thiện Faithfulness (+0.30) và Completeness (+0.30) so với baseline. Bước tiếp theo có thể thêm metadata filter theo `department` hoặc `section` để loại bỏ noise từ các document không liên quan — ví dụ q03 về Access Control nhưng chunk từ `hr/leave-policy-2026.pdf` vẫn lọt vào top-3 của baseline.
