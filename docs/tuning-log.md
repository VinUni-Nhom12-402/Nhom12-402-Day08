# Tuning Log — RAG Pipeline (Day 08 Lab)

**Ngày:** April 13, 2026  
**Nhóm:** Nhom12-402-Day08  
**Mục tiêu:** Tối ưu retrieval pipeline để cải thiện faithfulness và completeness.

---

## Baseline (Sprint 2)

**Ngày:** April 13, 2026  
**Config:**
```
retrieval_mode = "dense"
chunk_size = 400 tokens
overlap = 80 tokens
top_k_search = 10
top_k_select = 3
use_rerank = False
llm_model = gpt-4o-mini
embedding_model = paraphrase-multilingual-MiniLM-L12-v2
```

**Scorecard Baseline:**
| Metric | Average Score |
|--------|--------------|
| Faithfulness | 3.60/5 |
| Answer Relevance | 4.20/5 |
| Context Recall | 5.00/5 |
| Completeness | 3.90/5 |

**Câu hỏi yếu nhất (điểm thấp nhất):**
1. **q03 (Access Control)** - faithfulness = 1/5: Answer sai về department chịu trách nhiệm (nói IT Security thay vì đúng)
2. **q07 (Access Control)** - faithfulness = 3/5, completeness = 3/5: Đúng về previous name nhưng thiếu thông tin về approval process
3. **q10 (Refund)** - faithfulness = 1/5, relevance = 1/5, completeness = 1/5: Answer không address refund process
4. **q09 (Insufficient Context)** - faithfulness = 1/5, relevance = 1/5: Không trả lời được câu hỏi về topic không có trong docs

**Giả thuyết nguyên nhân (Error Tree):**
- [x] Retrieval: Dense bỏ lỡ exact keyword / alias (q03, q07 có tên riêng như "Level 3", "SOP")
- [x] Retrieval: Top-k quá ít → thiếu evidence (q10 có context recall = 5 nhưng answer vẫn sai)
- [x] Generation: Context có thể quá dài → lost in the middle (nhiều chunks nhưng không focus đúng)
- [ ] Indexing: Chunking cắt giữa điều khoản (không thấy evidence từ scorecard)
- [ ] Generation: Prompt không đủ grounding (có fallback "không đủ thông tin")

---

## Variant 1 (Sprint 3) - Hybrid Retrieval + Cross-Encoder Reranking

**Ngày:** April 13, 2026  
**Biến thay đổi:** Thêm hybrid retrieval (dense + BM25) + cross-encoder reranking  
**Lý do chọn biến này:**
> Baseline có vấn đề với retrieval: context recall cao (5.0) nhưng faithfulness và completeness thấp, cho thấy retrieved chunks có thông tin nhưng không phải chunks tốt nhất. Chọn hybrid + rerank vì:
> - Corpus có cả ngôn ngữ tự nhiên (policy descriptions) lẫn tên riêng/mã chuyên ngành (SLA P1, Level 3 access, ERR codes)
> - Dense search hiểu semantic nhưng miss exact matches; BM25 bắt keyword nhưng không hiểu paraphrase
> - Cross-encoder rerank cải thiện selection từ top-10 xuống top-3 bằng cách score từng (query, chunk) pair trực tiếp

**Config thay đổi:**
```
retrieval_mode = "hybrid_rerank"  # dense + BM25 + cross-encoder
use_rerank = True
cross_encoder_model = "cross-encoder/ms-marco-MiniLM-L-6-v2"
# Các tham số còn lại giữ nguyên như baseline
```

**Scorecard Variant 1:**
| Metric | Baseline | Variant 1 | Delta |
|--------|----------|-----------|-------|
| Faithfulness | 3.60/5 | 3.90/5 | +0.30 (+8.3%) |
| Answer Relevance | 4.20/5 | 4.20/5 | 0.00 (0%) |
| Context Recall | 5.00/5 | 5.00/5 | 0.00 (0%) |
| Completeness | 3.90/5 | 4.20/5 | +0.30 (+7.7%) |

**Nhận xét:**
> Variant cải thiện faithfulness và completeness mà không làm giảm relevance hay recall. Cụ thể:
> - **q01 (SLA)**: completeness từ 4 lên 5 - đầy đủ hơn về SLA details
> - **q06 (SLA)**: completeness từ 4 lên 5 - tương tự
> - **q07 (Access Control)**: faithfulness từ 3 lên 5 - đúng hơn về approval process
> - **q09 (Insufficient Context)**: completeness từ 2 lên 3 - fallback message tốt hơn
> - **q03 (Access Control)**: faithfulness từ 1 xuống 2 - vẫn sai nhưng ít sai hơn (có lẽ rerank chọn chunk tốt hơn)
> 
> Không có câu nào kém hơn đáng kể. Trade-off: latency tăng ~2x (từ ~500ms lên ~1s) nhưng accuracy cải thiện.

**Kết luận:**
> Variant 1 tốt hơn baseline đáng kể. Bằng chứng: faithfulness +8.3%, completeness +7.7%, đặc biệt cải thiện ở access control questions (q03, q07) - những câu có tên riêng. Context recall giữ nguyên cho thấy hybrid + rerank chọn chunks tốt hơn mà không miss information.

---

## Variant 2 (nếu có thời gian)

**Biến thay đổi:** Query expansion với LLM  
**Config:**
```
retrieval_mode = "dense_expansion"
query_expansion = True
expansion_prompt = "Generate 2-3 paraphrases of this question:"
# TODO: implement và test
```

**Scorecard Variant 2:**
| Metric | Baseline | Variant 1 | Variant 2 | Best |
|--------|----------|-----------|-----------|------|
| Faithfulness | 3.60 | 3.90 | ? | ? |
| Answer Relevance | 4.20 | 4.20 | ? | ? |
| Context Recall | 5.00 | 5.00 | ? | ? |
| Completeness | 3.90 | 4.20 | ? | ? |

---

## Tóm tắt học được

1. **Lỗi phổ biến nhất trong pipeline này là gì?**
   > Retrieval selection: Context recall cao nhưng faithfulness thấp, cho thấy retrieved chunks có thông tin nhưng không phải chunks tốt nhất. Giải pháp: reranking hoặc hybrid search.

2. **Biến nào ảnh hưởng nhiều nhất đến quality?**
   > Retrieval strategy (dense vs hybrid + rerank) ảnh hưởng trực tiếp đến faithfulness và completeness. Chunking và metadata ít vấn đề hơn trong test set này.

3. **Trade-off quan trọng nhất?**
   > Accuracy vs latency: Hybrid + rerank cải thiện quality nhưng tăng response time từ 500ms lên 1s. Trong production, cần cân nhắc user experience.

4. **Nếu làm lại, sẽ thay đổi gì?**
   > Test query expansion sớm hơn, vì có thể cải thiện paraphrase handling mà không tăng latency nhiều như reranking.

---

## Appendix: Detailed Question Analysis

### Questions Improved by Variant
- **q01, q06 (SLA)**: Completeness +1 - Better SLA detail coverage
- **q07 (Access Control)**: Faithfulness +2 - Correct approval process
- **q09 (Insufficient Context)**: Completeness +1 - Better fallback message

### Questions Still Challenging
- **q03 (Access Control)**: Faithfulness vẫn thấp (2/5) - Có thể cần better chunking hoặc metadata filtering
- **q10 (Refund)**: Faithfulness = 1/5 - Context recall = 5 nhưng answer sai, có thể generation issue

### Category Performance
| Category | Baseline Faithfulness | Variant Faithfulness | Improvement |
|----------|----------------------|---------------------|-------------|
| SLA | 5.0 | 5.0 | 0% |
| Refund | 3.0 | 3.0 | 0% |
| Access Control | 2.0 | 3.5 | +75% |
| IT Helpdesk | 5.0 | 5.0 | 0% |
| HR Policy | 5.0 | 5.0 | 0% |
| Insufficient Context | 1.0 | 1.0 | 0% |

2. **Biến nào có tác động lớn nhất tới chất lượng?**
   > _____________

3. **Nếu có thêm 1 giờ, nhóm sẽ thử gì tiếp theo?**
   > _____________
