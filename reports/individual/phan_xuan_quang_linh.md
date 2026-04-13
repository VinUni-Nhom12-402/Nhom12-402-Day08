# Báo Cáo Cá Nhân — Lab Day 08: RAG Pipeline

- **Họ và tên:** Phan Xuân Quang Linh
- **Vai trò trong nhóm:** Retrieval + Answer owner
- **Ngày nộp:** 13/04/2026
- **Độ dài yêu cầu:** 500–800 từ (Bản tóm tắt)
- **Mã HV**: 2A202600492

---

## 1. Tôi đã làm gì trong lab này?

Trong lab này, tôi đảm nhận vai trò **Retrieval + Answer Owner**, chịu trách nhiệm chính trong việc xây dựng pipeline và truy vấn db 

### **Sprint 1 — Indexing (`index.py`)**

- Khởi tạo hệ thống lưu trữ vector bằng ChromaDB (Persistent Client)
- Tích hợp API embedding để chuyển đổi dữ liệu text thành vector
- Lưu trữ các chunk do Retrieval Owner cung cấp vào vector store
- Đảm bảo dữ liệu có metadata đầy đủ để phục vụ truy xuất sau này

Đây là nền tảng để hệ thống có thể tìm kiếm thông tin hiệu quả.

---

### **Sprint 2 — RAG Pipeline (`rag_answer.py`)**

- Xây dựng pipeline xử lý câu hỏi theo luồng:
  - Nhận query
  - Retrieve dữ liệu liên quan
  - Xây dựng context
  - Gọi LLM để sinh câu trả lời
- Triển khai retrieval ban đầu bằng phương pháp dense retrieval
- Thiết kế **Grounded Prompt** để kiểm soát hành vi của LLM:
  - Bắt buộc chỉ trả lời dựa trên context
  - Yêu cầu trích dẫn nguồn
  - Bắt buộc trả lời "không biết" nếu thiếu dữ liệu

Phần này đóng vai trò cực kỳ quan trọng vì:
- Là “xương sống” của hệ thống
- Cung cấp output ổn định để Eval Owner có thể đo lường chính xác

---

### **Sprint 3 — Chuẩn bị cho Evaluation**

- Đảm bảo pipeline có input/output rõ ràng
- Chuẩn hóa format trả về:
  - Answer
  - Sources
  - Chunks used
- Hỗ trợ so sánh các chiến lược retrieval (dense, hybrid, rerank)

Điều này giúp việc đánh giá và A/B testing trở nên dễ dàng và nhất quán.

---

## 2. Điều tôi hiểu rõ hơn sau lab này

### **Grounded Prompting quan trọng hơn tôi nghĩ**

Trước đây, tôi nghĩ RAG chỉ đơn giản là:
> Query → Retrieve → Generate

Tuy nhiên, thực tế cho thấy nếu không kiểm soát chặt phần prompt:
- Model sẽ dễ dàng sinh ra thông tin không có trong context
- Dẫn đến hiện tượng hallucination

Việc thiết kế prompt với các nguyên tắc như:
- Chỉ sử dụng thông tin từ context (Evidence-only)
- Bắt buộc từ chối nếu không đủ dữ liệu (Abstain)

giúp giảm gần như hoàn toàn lỗi này.

---

### **Baseline pipeline là nền tảng cho mọi cải tiến**

Một hệ thống muốn đánh giá được:
- Hybrid retrieval tốt hơn dense hay không
- Rerank có cải thiện chất lượng hay không

thì trước hết baseline phải:
- Ổn định
- Dễ hiểu
- Có input/output rõ ràng

Nếu baseline không tốt:
- Mọi kết quả so sánh phía sau đều không đáng tin

---

## 3. Điều tôi ngạc nhiên hoặc gặp khó khăn

### **Hiểu sai metric của ChromaDB**

Khó khăn lớn nhất là ở bước xử lý kết quả retrieval.

Ban đầu, tôi hiểu nhầm giá trị `distance` trả về là:
> độ tương đồng (similarity)

Nhưng thực tế:
- Đây là **cosine distance**
- Nghĩa là càng nhỏ thì càng giống

Do đó cần chuyển đổi:
> similarity = 1.0 - distance

Nếu không xử lý đúng:
- Ranking bị đảo ngược
- Các chunk kém liên quan lại đứng top

Tôi đã mất khá nhiều thời gian debug trước khi nhận ra vấn đề này.

---

### **LLM vẫn có thể “lách luật”**

Một điều khá bất ngờ là:

Ngay cả khi đã thiết kế prompt rất chặt chẽ, nếu để:
- temperature > 0

thì model vẫn có xu hướng:
- tự suy diễn thêm thông tin
- trả lời thay vì từ chối

Giải pháp hiệu quả nhất:
- Đặt temperature = 0

Điều này giúp output ổn định và tuân thủ luật tốt hơn.

---

## 4. Phân tích một câu hỏi scorecard: q07

### **Câu hỏi**
> Công ty sẽ phạt bao nhiêu nếu team IT vi phạm cam kết SLA P1?

---

### **Phân tích**

- Tài liệu gốc **không hề có thông tin về mức phạt**
- Đây là một câu hỏi dạng “bẫy hallucination”

---

### **Trước khi fix**

- Model cố gắng suy đoán mức phạt
- Sinh ra câu trả lời không có trong tài liệu
- Dẫn đến điểm Faithfulness rất thấp

---

### **Sau khi áp dụng Grounded Prompt**

- Model tuân thủ luật:
  - Không đủ dữ liệu → từ chối trả lời
- Output:
  > Không có đủ dữ liệu để trả lời câu hỏi

---

### **Insight rút ra**

- Vấn đề không nằm ở Retrieval
- Mà nằm ở bước Generation

Nếu không kiểm soát:
- Model sẽ luôn cố “trả lời cho bằng được”

Do đó:
> Grounded Prompt là tuyến phòng thủ quan trọng nhất chống hallucination

---

## 5. Nếu có thêm thời gian, tôi sẽ làm gì?

### **Phát triển Query Routing**

Hiện tại pipeline xử lý tất cả query theo cùng một cách, điều này chưa tối ưu.

Ý tưởng cải tiến:

- Phân loại query ngay từ đầu:
  - Query đơn giản → dùng sparse retrieval (keyword-based)
  - Query phức tạp → dùng dense hoặc hybrid retrieval

---

### **Lợi ích**

- Giảm độ nhiễu trong retrieval
- Tăng tốc độ phản hồi (giảm latency)
- Tránh việc sử dụng các phương pháp nặng khi không cần thiết

---

### **Định hướng**

Xây dựng một module:
- Nhận query
- Phân tích độ phức tạp
- Route sang pipeline phù hợp

---