# Báo Cáo Nhóm — Lab Day 08: RAG Pipeline

**Nhóm:** Nhom12-402-Day08  
**Thành viên:**
Dương Chí Thành - 2A202600047
Bùi Cao Chinh - 2A202600001
Phan Xuân Quang Linh - 2A202600492
Trần Thị Kim Ngân - 2A202600432
Nguyễn Đức Tiến - 2A202600393
Nguyễn Trọng Thiên Khôi - 2A202600227


---

## 1. Tổng quan dự án và kết quả (150-200 từ)

**Mục tiêu:** Xây dựng trợ lý nội bộ cho CS + IT Helpdesk trả lời câu hỏi về chính sách, SLA, và quy trình bằng chứng cứ được retrieve có kiểm soát.

**Pipeline hoàn thành:**
- **Indexing:** 5 tài liệu chính sách → chunking (400 tokens, 80 overlap) → embedding (Sentence-Transformers) → ChromaDB
- **Retrieval:** Baseline (dense search) + Variant (hybrid + cross-encoder rerank)
- **Generation:** LLM (GPT-4o-mini) với grounded prompt, citation enforcement
- **Evaluation:** Scorecard A/B comparison trên 10 test questions

**Kết quả chính:**
- **Baseline:** Faithfulness 3.60/5, Completeness 3.90/5, Context Recall 5.00/5
- **Variant:** Faithfulness 3.90/5 (+8.3%), Completeness 4.20/5 (+7.7%)
- **Cải thiện đáng kể** ở access control questions nhờ hybrid retrieval + reranking

**Thành công:** Pipeline hoạt động end-to-end, trả lời được 8/10 câu hỏi với citation đầy đủ. Variant cải thiện quality mà không làm giảm recall.

---

## 2. Kiến trúc và thiết kế kỹ thuật (200-250 từ)

### Pipeline Architecture
```
Raw Docs → Preprocess → Chunk → Embed → ChromaDB
                                      ↓
User Query → Dense Search → (Hybrid + Rerank) → LLM → Grounded Answer
                                      ↓
Test Questions → Evaluation → Scorecard → Analysis
```

### Key Design Decisions

**Chunking Strategy:**
- Size: 400 tokens (~1.6KB) - balance context completeness vs noise
- Overlap: 80 tokens (5%) - prevent information loss at boundaries  
- Strategy: Heading-based + paragraph - respect document structure
- Metadata: source, section, effective_date, department, access_level

**Retrieval Strategy:**
- **Baseline:** Dense similarity (cosine) - simple, fast (~500ms)
- **Variant:** Hybrid (dense + BM25) + Cross-Encoder rerank - catches both semantic and keyword matches
- Top-k: Search 20 (dense+sparse), rerank to 10, select 3 for LLM context

**Generation Strategy:**
- Model: GPT-4o-mini (cost-effective, good quality)
- Prompt: Grounded instruction + citation enforcement
- Output: JSON with answer, sources, confidence
- Fallback: "Không đủ thông tin" when no relevant chunks

**Evaluation Framework:**
- Metrics: Faithfulness, Relevance, Context Recall, Completeness
- Test set: 10 questions covering SLA, Refund, Access Control, IT Helpdesk, HR
- A/B comparison: Baseline vs Variant with detailed per-question analysis

### Technology Stack
- **Embeddings:** Sentence-Transformers (local, multilingual support)
- **Vector Store:** ChromaDB (persistent, fast retrieval)
- **Sparse Search:** BM25 (keyword matching)
- **Reranking:** Cross-Encoder (pairwise scoring)
- **LLM:** OpenAI GPT-4o-mini (generation with citations)
- **Evaluation:** Custom scorer with LLM judge

---

## 3. Thách thức và giải pháp (150-200 từ)

### Thách thức chính gặp phải:

1. **Retrieval Selection Problem:** 
   - **Vấn đề:** Context recall cao (5.0) nhưng faithfulness thấp (3.6), cho thấy retrieved chunks có thông tin nhưng không phải chunks tốt nhất
   - **Giải pháp:** Thêm hybrid search (dense + BM25) + cross-encoder rerank để chọn chunks chính xác hơn

2. **Exact Keyword Matching:**
   - **Vấn đề:** Dense search miss tên riêng như "P1 ticket", "Level 3 access", "SLA" 
   - **Giải pháp:** BM25 sparse search bắt keyword, kết hợp với dense semantic search

3. **Citation Quality:**
   - **Vấn đề:** LLM hallucinate hoặc cite sai source
   - **Giải pháp:** Prompt engineering với "trích dẫn nguồn khi khẳng định sự kiện" + structured output format

4. **Evaluation Consistency:**
   - **Vấn đề:** Manual scoring không consistent across team members
   - **Giải pháp:** Define clear rubrics cho từng metric, use LLM judge cho faithfulness

### Học được từ debugging:
- **Error Tree approach:** Systematically check indexing → retrieval → generation
- **A/B testing:** Chỉ thay đổi 1 biến mỗi lần để isolate effects
- **Trade-off awareness:** Accuracy vs latency (variant 2x slower nhưng 8% better quality)

---

## 4. Phân tích kết quả và insights (150-200 từ)

### A/B Comparison Results

| Metric | Baseline | Variant | Delta | Interpretation |
|--------|----------|---------|-------|----------------|
| Faithfulness | 3.60/5 | 3.90/5 | +8.3% | Answers grounded better in retrieved chunks |
| Relevance | 4.20/5 | 4.20/5 | 0% | Question understanding unchanged |
| Context Recall | 5.00/5 | 5.00/5 | 0% | Retrieval breadth maintained |
| Completeness | 3.90/5 | 4.20/5 | +7.7% | More comprehensive answers |

### Category Performance

| Category | Baseline Faithfulness | Variant Faithfulness | Improvement |
|----------|----------------------|---------------------|-------------|
| SLA | 5.0 | 5.0 | 0% |
| Refund | 3.0 | 3.0 | 0% |
| Access Control | 2.0 | 3.5 | +75% ⭐ |
| IT Helpdesk | 5.0 | 5.0 | 0% |
| HR Policy | 5.0 | 5.0 | 0% |

### Key Insights

1. **Retrieval Strategy Matters Most:** Hybrid + rerank cải thiện faithfulness/completeness mà không ảnh hưởng recall
2. **Domain-Specific Challenges:** Access control questions (với tên riêng) được cải thiện nhiều nhất
3. **Quality vs Speed Trade-off:** Variant 2x latency nhưng đáng giá cho production use
4. **Citation Enforcement Works:** Structured prompts force better source attribution

### Questions That Improved
- **q07 (Access Control):** Faithfulness 3→5 - Correct approval process identification
- **q01, q06 (SLA):** Completeness 4→5 - Better SLA detail coverage
- **q03 (Access Control):** Faithfulness 1→2 - Reduced hallucination about departments

### Remaining Challenges
- **q03 (Access Control):** Still low faithfulness - may need better chunking or metadata filtering
- **q10 (Refund):** Faithfulness 1/5 despite perfect recall - generation issue, not retrieval

### Chi tiết kết quả 10 câu hỏi

| ID | Câu hỏi | Category | Baseline (F/R/C) | Variant (F/R/C) | Cải thiện chính |
|----|---------|----------|------------------|-----------------|---------------|
| q01 | SLA xử lý ticket P1 là bao lâu? | SLA | 5/5/4 | 5/5/5 | Completeness +1 (thêm chi tiết SLA) |
| q02 | Khách hàng có thể yêu cầu hoàn tiền trong bao nhiêu ngày? | Refund | 5/5/5 | 5/5/5 | Không thay đổi |
| q03 | Ai phải phê duyệt để cấp quyền Level 3? | Access Control | 1/5/5 | 2/5/5 | Faithfulness +1 (giảm hallucination về department) |
| q04 | Sản phẩm kỹ thuật số có được hoàn tiền không? | Refund | 5/5/5 | 5/5/5 | Không thay đổi |
| q05 | Tài khoản bị khóa sau bao nhiêu lần đăng nhập sai? | IT Helpdesk | 5/5/5 | 5/5/5 | Không thay đổi |
| q06 | Escalation trong sự cố P1 diễn ra như thế nào? | SLA | 5/5/4 | 5/5/5 | Completeness +1 (thêm chi tiết escalation) |
| q07 | Quy trình cấp quyền tạm thời cho engineer xử lý incident? | Access Control | 3/5/3 | 5/5/3 | Faithfulness +2 (đúng approval process) |
| q08 | Nhân viên phải báo trước bao nhiêu ngày để xin nghỉ phép? | HR Policy | 5/5/5 | 5/5/5 | Không thay đổi |
| q09 | Mật khẩu tài khoản công ty cần đổi định kỳ không? | Insufficient Context | 1/1/2 | 1/1/3 | Completeness +1 (fallback message tốt hơn) |
| q10 | Chính sách hoàn tiền hiện tại áp dụng cho đơn hàng cũ không? | Refund | 1/1/1 | 1/1/1 | Không cải thiện (generation issue) |

**Ghi chú chi tiết:**
- **q01 (SLA):** Baseline thiếu chi tiết về "resolution time 4 hours", variant thêm đầy đủ
- **q03 (Access Control):** Baseline sai hoàn toàn về department (nói IT Security thay vì Line Manager + IT Admin + IT Security), variant giảm sai sót
- **q06 (SLA):** Baseline thiếu chi tiết về "auto-escalate after 10 minutes", variant thêm đầy đủ
- **q07 (Access Control):** Baseline đúng về previous name nhưng thiếu approval process, variant capture đầy đủ quy trình
- **q09 (Insufficient Context):** Variant có fallback message tốt hơn ("không đủ thông tin" rõ ràng hơn)
- **q10 (Refund):** Cả hai đều sai hoàn toàn mặc dù recall = 5/5, cho thấy vấn đề ở generation không phải retrieval

### Kết quả thực tế của 10 Grading Questions

Dưới đây là kết quả chạy pipeline trên 10 câu hỏi grading (gq01-gq10) từ grading_run.json:

**gq01: SLA xử lý ticket P1 đã thay đổi như thế nào so với phiên bản trước?**  
*Answer:* SLA xử lý ticket P1 đã được cập nhật từ 6 giờ xuống 4 giờ cho thời gian khắc phục (resolution) trong phiên bản v2026.1 (2026-01-15) [Source 2, Phần 5].  
*Sources:* support/sla-p1-2026.pdf, policy/refund-v4.pdf  
*Retrieval:* hybrid, 3 chunks

**gq02: Khi làm việc remote, tôi phải dùng VPN và được kết nối trên tối đa bao nhiêu thiết bị?**  
*Answer:* Khi làm việc remote, bạn phải sử dụng VPN. Mỗi tài khoản được kết nối VPN trên tối đa 2 thiết bị cùng lúc [2, Section 2].  
*Sources:* hr/leave-policy-2026.pdf, support/helpdesk-faq.md  
*Retrieval:* hybrid, 3 chunks

**gq03: Đơn hàng mua trong chương trình Flash Sale và đã kích hoạt sản phẩm có được hoàn tiền không?**  
*Answer:* Rất tiếc, tôi không có đủ dữ liệu để trả lời vấn đề này.  
*Sources:* policy/refund-v4.pdf  
*Retrieval:* hybrid, 3 chunks

**gq04: Nếu chọn nhận store credit thay vì hoàn tiền, tôi được bao nhiêu phần trăm so với số tiền gốc?**  
*Answer:* Nếu bạn chọn nhận store credit thay vì hoàn tiền, bạn sẽ nhận được giá trị 110% so với số tiền hoàn gốc. [Source 1, Điều 5]  
*Sources:* policy/refund-v4.pdf  
*Retrieval:* hybrid, 3 chunks

**gq05: Contractor từ bên ngoài công ty có thể được cấp quyền Admin Access không? Nếu có, cần bao nhiêu ngày và có yêu cầu đặc biệt gì?**  
*Answer:* Rất tiếc, tôi không có đủ dữ liệu để trả lời vấn đề này.  
*Sources:* support/helpdesk-faq.md, it/access-control-sop.md  
*Retrieval:* hybrid, 3 chunks

**gq06: Lúc 2 giờ sáng xảy ra sự cố P1, on-call engineer cần cấp quyền tạm thời cho một engineer xử lý incident. Quy trình cụ thể như thế nào và quyền này tồn tại bao lâu?**  
*Answer:* On-call IT Admin có thể cấp quyền tạm thời cho engineer sau khi được Tech Lead phê duyệt bằng lời. Quyền tạm thời này có hiệu lực tối đa trong 24 giờ. Sau 24 giờ, phải có ticket chính thức hoặc quyền sẽ bị thu hồi tự động. Mọi quyền tạm thời phải được ghi log vào hệ thống Security Audit. [Source 1, Section 4]  
*Sources:* support/sla-p1-2026.pdf, it/access-control-sop.md  
*Retrieval:* hybrid, 3 chunks

**gq07: Công ty sẽ phạt bao nhiêu nếu team IT vi phạm cam kết SLA P1?**  
*Answer:* Rất tiếc, tôi không có đủ dữ liệu để trả lời vấn đề này.  
*Sources:* support/helpdesk-faq.md  
*Retrieval:* hybrid, 3 chunks

**gq08: Nhân viên phải báo trước bao nhiêu ngày để xin nghỉ phép năm? Con số này có giống với số ngày cần giấy tờ khi nghỉ ốm không?**  
*Answer:* Nhân viên phải gửi yêu cầu nghỉ phép năm qua hệ thống HR Portal ít nhất 3 ngày làm việc trước ngày nghỉ ([Source 2], [Section 2]). Số ngày cần giấy tờ khi nghỉ ốm là nếu nghỉ trên 3 ngày liên tiếp ([Source 1], [Section 1.2]). Con số này không giống nhau, vì yêu cầu báo trước để xin nghỉ phép năm là 3 ngày, trong khi giấy tờ chỉ cần khi nghỉ ốm trên 3 ngày liên tiếp.  
*Sources:* hr/leave-policy-2026.pdf, it/access-control-sop.md  
*Retrieval:* hybrid, 3 chunks

**gq09: Mật khẩu tài khoản công ty cần đổi định kỳ không? Nếu có, hệ thống sẽ nhắc nhở trước bao nhiêu ngày và đổi qua đâu?**  
*Answer:* Có, mật khẩu tài khoản công ty cần được thay đổi mỗi 90 ngày. Hệ thống sẽ nhắc nhở 7 ngày trước khi hết hạn. Bạn có thể đổi mật khẩu qua portal SSO. [Source 1, Section 1]  
*Sources:* support/helpdesk-faq.md, it/access-control-sop.md  
*Retrieval:* hybrid, 3 chunks

**gq10: Chính sách hoàn tiền hiện tại áp dụng cho đơn hàng đặt trước ngày 01/02/2026 không?**  
*Answer:* Chính sách hoàn tiền hiện tại không áp dụng cho các đơn hàng đặt trước ngày 01/02/2026. Các đơn hàng này sẽ áp dụng theo chính sách hoàn tiền phiên bản 3 [Source 1, Điều 1].  
*Sources:* policy/refund-v4.pdf  
*Retrieval:* hybrid, 3 chunks

---

## 5. Kết luận và hướng phát triển (100-150 từ)

**Thành công của nhóm:**
- Hoàn thành pipeline end-to-end với quality metrics tốt
- A/B testing cho thấy cải thiện rõ rệt từ variant tuning
- Code modular và maintainable

**Học được:**
1. **Retrieval selection** quan trọng hơn retrieval breadth
2. **Hybrid approaches** tốt hơn single-strategy cho domain với mixed content types
3. **Prompt engineering** crucial cho grounded generation
4. **Systematic evaluation** bắt buộc để measure và improve

**Nếu có thêm thời gian:**
1. **Query Expansion:** Thử LLM-generated paraphrases để handle question variations
2. **Fine-tuned Reranker:** Train domain-specific cross-encoder trên policy QA pairs  
3. **Multi-hop Retrieval:** Chain multiple retrievals cho complex questions
4. **Production Hardening:** Add caching, rate limiting, monitoring

**Production Readiness:** Pipeline sẵn sàng cho internal deployment với monitoring và A/B testing framework.



