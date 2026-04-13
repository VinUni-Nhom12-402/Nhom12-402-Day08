# Individual Report — 2A202600492 Phan Xuân Quang Linh

## 1. Đóng góp cụ thể

Tôi phụ trách Sprint 2, 3 với vai trò đánh giá và phát triển, tập trung vào việc đo lường chất lượng pipeline một cách khách quan.

# Sprint 4 — Evaluation (eval.py)

## 1. LLM-as-Judge Implementation

Trong sprint này, hệ thống được mở rộng với cơ chế đánh giá tự động bằng LLM (LLM-as-Judge). Ba tiêu chí chính được triển khai gồm:

- Faithfulness (độ trung thực với context)
- Answer Relevance (độ liên quan với câu hỏi)
- Completeness (độ đầy đủ của câu trả lời)

Mỗi tiêu chí được реализ hóa thông qua một hàm scoring riêng. Các hàm này nhận đầu vào là câu hỏi, context (các đoạn văn được retrieve) và câu trả lời do mô hình sinh ra. Sau đó, một prompt có cấu trúc rõ ràng được tạo ra và gửi tới LLM để đánh giá.

Kết quả trả về được parse dưới dạng JSON, bao gồm:
- Điểm số từ 1 đến 5
- Lý do ngắn gọn giải thích cho điểm số đó

Cách tiếp cận này giúp đánh giá chất lượng câu trả lời một cách tự động, thay vì phải kiểm tra thủ công.

---

## 2. Kích hoạt A/B Testing

Hệ thống được thiết kế để so sánh hai cấu hình pipeline:

- Baseline: sử dụng dense retrieval
- Variant: sử dụng hybrid retrieval kết hợp rerank

Trong quá trình chạy, chỉ thay đổi một yếu tố mỗi lần (theo nguyên tắc A/B testing), cụ thể là:
- Thay đổi retrieval mode từ dense sang hybrid
- Bật thêm bước rerank ở variant

Pipeline được chạy với cùng một tập câu hỏi để đảm bảo tính công bằng khi so sánh. Kết quả từ hai cấu hình sẽ được tổng hợp để đánh giá sự cải thiện.

---

## 3. End-to-End Evaluation

Hệ thống được chạy end-to-end với 10 câu hỏi.

Với mỗi câu hỏi:
- Pipeline RAG thực hiện retrieve → (rerank) → generate
- Thu thập các thông tin:
  - Câu trả lời
  - Danh sách nguồn (sources)
  - Các chunk được sử dụng

Sau đó, áp dụng LLM-as-Judge để chấm điểm theo 3 tiêu chí đã nêu.

Kết quả được lưu thành các file:
- scorecard_baseline.md
- scorecard_variant.md
- ab_comparison.csv

Các file này giúp so sánh trực quan giữa hai cấu hình pipeline.

---

## 4. Context Recall

Metric Context Recall được giữ nguyên do đã có logic phù hợp.

Cách tính:
- So sánh danh sách source mà hệ thống retrieve được với ground truth
- Dựa trên tên file trong metadata
- Hỗ trợ partial-match để linh hoạt hơn

Metric này phản ánh khả năng của hệ thống trong việc retrieve đúng tài liệu liên quan.

---

# Grading Run (17:00)

## 1. Tự động hóa pipeline

Một script riêng được xây dựng để tự động chạy pipeline khi có bộ câu hỏi grading.

Quy trình:
- Load dữ liệu từ file chứa câu hỏi
- Chạy pipeline với cấu hình tốt nhất (hybrid + rerank)
- Lặp qua toàn bộ câu hỏi

---

## 2. Kết quả đầu ra

Kết quả được lưu vào file log, bao gồm:
- Câu hỏi
- Câu trả lời
- Nguồn được sử dụng
- Cấu hình pipeline
- Timestamp

Việc lưu log giúp kiểm tra lại kết quả và phục vụ cho việc đánh giá sau này.

---

# 2. Phân tích câu grading: q03

## Câu hỏi
"Ai phải phê duyệt để cấp quyền Level 3?"

---

## Kết quả

- Faithfulness: thấp (baseline: 1/5, variant: 2/5)
- Relevance: 5/5
- Recall: 5/5

---

## Pipeline xử lý

Hệ thống retrieve đúng tài liệu liên quan đến access control. Câu trả lời được sinh ra hoàn toàn chính xác về mặt nội dung, liệt kê đầy đủ các bên phê duyệt.

Tuy nhiên, điểm Faithfulness lại thấp.

---

## Nguyên nhân

Thông tin về Level 3 không nằm trong một đoạn duy nhất mà bị phân tán ở nhiều chunk khác nhau. Khi xây dựng context, các chunk này được ghép lại nhưng không tạo thành một đoạn liên tục.

Do đó, mô hình phải tổng hợp thông tin từ nhiều nguồn để đưa ra câu trả lời hoàn chỉnh.

LLM-as-Judge đánh giá hành vi này là "suy luận tổng hợp" thay vì "trích xuất trực tiếp từ context", và vì vậy trừ điểm Faithfulness.

---

## Root Cause

Nguyên nhân chính nằm ở bước chunking:

- Nội dung bị cắt theo độ dài ký tự
- Các bảng hoặc danh sách bị chia nhỏ
- Không đảm bảo một chunk chứa trọn vẹn thông tin logic

Dẫn đến:
- Retrieval đúng document nhưng sai granularity
- Context không đủ mạnh để support trực tiếp câu trả lời

---

## Đề xuất cải tiến

- Tăng kích thước chunk để giữ nguyên nội dung quan trọng
- Giảm overlap để tránh phân mảnh thông tin
- Áp dụng filter theo metadata (ví dụ section) để ưu tiên đúng vùng nội dung

---

# 3. Rút kinh nghiệm

Một điểm quan trọng rút ra:

Retrieval tốt không đồng nghĩa với việc generation tốt.

---

## Quan sát

- Context Recall đạt tối đa
- Nhưng Faithfulness vẫn thấp

---

## Phân tích

Retriever có thể lấy đúng tài liệu, nhưng nếu chunk không chứa đúng thông tin cần thiết thì mô hình vẫn phải suy luận.

Trong một số trường hợp, câu trả lời đúng nhờ:
- kiến thức có sẵn của mô hình
- hoặc suy luận từ nhiều đoạn context

Tuy nhiên, điều này không được coi là grounded, nên bị giảm điểm Faithfulness.

---

## Khó khăn thực tế

LLM-as-Judge không hoàn toàn ổn định:
- Cùng một câu trả lời có thể cho điểm khác nhau giữa các lần chạy

Giải pháp:
- Sử dụng temperature = 0 để giảm randomness

---

# 4. Đề xuất cải tiến

## Cải tiến 1 — Chunking theo cấu trúc

Các câu có điểm thấp thường liên quan đến:
- bảng
- danh sách
- ma trận phân quyền

Do đó, cần:
- thiết kế chunking theo cấu trúc thay vì theo ký tự
- giữ nguyên toàn bộ bảng trong một chunk

---

## Cải tiến 2 — Metadata filtering

So với baseline, cấu hình hybrid + rerank đã cải thiện điểm Faithfulness và Completeness.

Bước tiếp theo:
- sử dụng metadata như section hoặc department để filter khi retrieve
- loại bỏ các chunk không liên quan

Ví dụ:
- câu hỏi về Access Control nhưng vẫn retrieve nhầm tài liệu HR

---

## Kết luận

Pipeline hiện tại đã đúng về mặt quy trình, nhưng vấn đề nằm ở:

- cách chia chunk
- cách chọn context

Đây là hai yếu tố ảnh hưởng trực tiếp đến Faithfulness, không chỉ riêng retrieval strategy.