# Báo Cáo Cá Nhân — Lab Day 08: RAG Pipeline

**Họ và tên:** Nguyễn Đức Tiến
**Mã HV:** 2A202600393
**Vai trò trong nhóm:** Eval Owner
**Ngày nộp:** 2026-04-13
**Độ dài yêu cầu:** 500–800 từ

---

## 1. Tôi đã làm gì trong lab này? (100-150 từ)

Tôi phụ trách Sprint 3–4 với vai trò Eval Owner, tập trung vào đo lường chất lượng pipeline một cách khách quan.

Trong `eval.py`, tôi implement LLM-as-Judge cho 3 hàm scoring: `score_faithfulness()`, `score_answer_relevance()`, và `score_completeness()`. Mỗi hàm gửi prompt có cấu trúc tới LLM, parse JSON response, trả về điểm 1–5 kèm lý do. Metric `score_context_recall()` đã có sẵn logic partial-match nên tôi giữ nguyên.

Sau đó tôi kích hoạt phần chạy variant scorecard (`VARIANT_CONFIG`: hybrid + rerank) và `compare_ab()`, chạy end-to-end 10 câu hỏi cho cả baseline và variant, sinh ra `scorecard_baseline.md`, `scorecard_variant.md`, và `ab_comparison.csv`.

Ngoài ra tôi viết `run_grading.py` để tự động hóa grading run lúc 17:00 — khi `grading_questions.json` được public, chạy một lệnh là sinh ra `logs/grading_run.json` đủ 10 câu với timestamp hợp lệ, dùng cấu hình hybrid+rerank tốt nhất của nhóm.

---

## 2. Điều tôi hiểu rõ hơn sau lab này (100-150 từ)

Sau lab này tôi hiểu rõ hơn về **evaluation loop trong RAG** — cụ thể là sự tách biệt giữa retrieval quality và generation quality.

Trước đây tôi nghĩ nếu retriever lấy đúng document thì model sẽ trả lời tốt. Thực tế không phải vậy. Context Recall của nhóm đạt 5.00/5 cho cả baseline lẫn variant — retriever luôn lấy đúng source. Nhưng Faithfulness chỉ 3.60 (baseline) và 3.90 (variant). Lý do là retriever lấy đúng _document_ nhưng chunk cụ thể được đưa vào prompt chưa chắc chứa đúng đoạn cần thiết. Model phải tổng hợp từ nhiều chunk, và LLM-as-Judge coi đó là dấu hiệu không grounded.

Điều này cho thấy chunking strategy ảnh hưởng trực tiếp đến Faithfulness, không chỉ ảnh hưởng đến Recall.

---

## 3. Điều tôi ngạc nhiên hoặc gặp khó khăn (100-150 từ)

Điều ngạc nhiên nhất là LLM-as-Judge không nhất quán. Cùng một answer, chạy lại có thể cho điểm khác nhau 1–2 bậc. Ví dụ q03 ở baseline bị chấm Faithfulness 1/5 dù answer thực tế đúng nội dung — LLM judge đánh giá model "tổng hợp" thông tin từ nhiều chunk thay vì trích dẫn trực tiếp, nên trừ điểm nặng.

Khó khăn khi debug là phần parse JSON từ LLM response — đôi khi LLM trả về text có markdown code block bao quanh JSON, regex `\{.*?\}` với `re.DOTALL` xử lý được nhưng vẫn có edge case khi LLM trả về JSON lồng nhau.

Giải pháp là dùng `temperature=0` khi gọi LLM để chấm điểm, giúp output ổn định hơn đáng kể.

---

## 4. Phân tích một câu hỏi trong scorecard (150-200 từ)

**Câu hỏi:** q07 — "Approval Matrix để cấp quyền hệ thống là tài liệu nào?"

**Phân tích:**

Đây là câu dùng tên cũ ("Approval Matrix for System Access") để hỏi về tài liệu hiện tại (`access-control-sop.md`). Đây là bài test cho khả năng alias/tên cũ của retriever.

Baseline (dense) cho Faithfulness 3/5, Completeness 3/5. Answer trả lời được tên cũ nhưng không nêu rõ tên mới hiện tại là gì, chỉ cite source path. Lỗi nằm ở generation — model không tổng hợp đủ thông tin từ chunk để trả lời hoàn chỉnh.

Variant (hybrid+rerank) cải thiện rõ: Faithfulness lên 5/5. Lý do là BM25 trong hybrid retrieval match được keyword "Approval Matrix" chính xác hơn dense embedding — dense embedding có thể bị nhiễu bởi các chunk nói về "approval" trong ngữ cảnh khác. Rerank sau đó đưa chunk có tên cũ lên top, giúp model trích dẫn trực tiếp thay vì tổng hợp.

Completeness vẫn 3/5 ở cả hai vì answer không nêu rõ tên đầy đủ hiện tại của tài liệu.

---

## 5. Nếu có thêm thời gian, tôi sẽ làm gì? (50-100 từ)

Tôi sẽ thử **chunking theo cấu trúc bảng** vì scorecard cho thấy q03 và q07 — hai câu hỏi về thông tin dạng bảng phân cấp — có Faithfulness thấp nhất. Hiện tại chunking cắt theo số ký tự, làm vỡ bảng "Phân cấp quyền truy cập" thành nhiều chunk. Nếu giữ nguyên toàn bộ bảng trong một chunk, model có thể trích dẫn trực tiếp thay vì tổng hợp, Faithfulness sẽ tăng.
