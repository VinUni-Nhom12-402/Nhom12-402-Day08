# Báo Cáo Cá Nhân — Lab Day 08: RAG Pipeline

- **Họ và tên:** Bùi Cao Chinh
- **Vai trò trong nhóm:** Tech Lead
- **Ngày nộp:** 13/04/2026
- **Độ dài yêu cầu:** 500–800 từ (Bản tóm tắt)
- **Mã HV**: 2A202600001

---

## 1. Tôi đã làm gì trong lab này?

Với vai trò Tech Lead, tôi phụ trách kiến trúc và nối luồng end-to-end hệ thống (Sprint 1, 2):
- **Sprint 1 (`index.py`):** Khởi tạo ChromaDB Persistent Client, tích hợp API OpenAI (`text-embedding-3-small`) để nhúng và lưu trữ các chunk data từ Retrieval Owner.
- **Sprint 2 (`rag_answer.py`):** Xây dựng luồng hệ thống gọi truy vấn `retrieve_dense()`. Đặc biệt, thiết kế "Grounded Prompt" ép LLM trích dẫn nguồn, kết nối pipeline tới bước Generation cuối cùng. Công việc này đóng vai trò móng để Eval Owner đo lường scorecard mượt mà.

---

## 2. Điều tôi hiểu rõ hơn sau lab này

- **Grounded Prompting:** RAG không đơn thuần là query -> trả lời. Nếu không ép luật gắt gao trên System Prompt ("Evidence-only" và "Abstain"), model sẽ sinh ảo giác (hallucination). Thiết kế chuẩn cấu trúc citation giúp chặn hoàn toàn lỗi này.
- **Vai trò của Baseline Pipeline:** Để đo được hiệu quả thuật toán của Retrieval Owner (Rerank/Hybrid), thì cái khung baseline của Tech Lead phải hoạt động ổn định và có input/output rành mạch.

---

## 3. Điều tôi ngạc nhiên hoặc gặp khó khăn

Khó khăn nhất là xử lý metric của **ChromaDB**. Ban đầu, tôi lầm hiểu output `distances` là độ tương đồng (Similarity score). Mất khá nhiều thời gian debug ranking đến khi nhận ra phải áp dụng công thức đảo `score = 1.0 - distance` thì các chunk liên quan nhất mới xếp lên top đúng logic.

Điều ngạc nhiên là dù ép luật kỹ, LLM với tham số `temperature > 0` thi thoảng vẫn "lách" luật tự chắp vá kiến thức để trả lời thay vì Abstain. Thiết lập `temperature=0` là biện pháp mạnh duy nhất trị dứt điểm tình trạng này.

---

## 4. Phân tích một câu hỏi scorecard: q07

**Câu hỏi:** *gq07 - "Công ty sẽ phạt bao nhiêu nếu team IT vi phạm cam kết SLA P1?"*

**Phân tích:**
Tài liệu gốc hoàn toàn không nhắc quy định phạt penalty.
Ở bản nháp chưa có luật Abstain, luồng Generation nội suy bậy bạ mức phạt do bị dính bẫy hallucination bait, đẩy điểm Faithfulness về thấp.
Sau khi Baseline của tôi chốt cứng Grounded Prompt, hệ thống đã ngoan ngoãn trả ra "Không có đủ dữ liệu". Câu hỏi này chứng minh mấu chốt chống ảo giác với câu hỏi nhiễu không nằm ở khâu Retrieval, mà nằm ở luật Generation.

---

## 5. Nếu có thêm thời gian, tôi sẽ làm gì?

Tôi sẽ phát triển cỗ máy **Query Routing** nằm ở ngay đầu pipeline nhận câu hỏi. Các query ngắn lấy thông tin cơ bản dễ dàng định tuyến cho luồng tra Keyword thuần (Sparse/BM25) giảm nhiễu. Các query phức tạp hơn mới đưa vào Dense. Khung này giúp hệ thống tiết kiệm thời gian phản hồi (Latency) thay vì lúc nào cũng bắt model cõng luồng tính toán nặng nề.

---
