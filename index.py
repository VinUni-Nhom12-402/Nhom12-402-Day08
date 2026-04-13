"""
index.py — Sprint 1: Build RAG Index
====================================
Mục tiêu Sprint 1 (60 phút):
  - Đọc và preprocess tài liệu từ data/docs/
  - Chunk tài liệu theo cấu trúc tự nhiên (heading/section)
  - Gắn metadata: source, section, department, effective_date, access
  - Embed và lưu vào vector store (ChromaDB)

Definition of Done Sprint 1:
  ✓ Script chạy được và index đủ docs
  ✓ Có ít nhất 3 metadata fields hữu ích cho retrieval
  ✓ Có thể kiểm tra chunk bằng list_chunks()
"""

import os
import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# CẤU HÌNH
# =============================================================================

DOCS_DIR = Path(__file__).parent / "data" / "docs"
CHROMA_DB_DIR = Path(__file__).parent / "chroma_db"

# Chunk size và overlap (tính theo tokens, ước lượng 1 token ≈ 4 ký tự)
CHUNK_SIZE = 400       # tokens (ước lượng bằng số ký tự / 4)
CHUNK_OVERLAP = 80     # tokens overlap giữa các chunk

# Sentence Transformer model (lazy-loaded singleton)
_st_model = None


# =============================================================================
# STEP 1: PREPROCESS
# Làm sạch text trước khi chunk và embed
# =============================================================================

def preprocess_document(raw_text: str, filepath: str) -> Dict[str, Any]:
    """
    Preprocess một tài liệu: extract metadata từ header và làm sạch nội dung.

    Args:
        raw_text: Toàn bộ nội dung file text
        filepath: Đường dẫn file để làm source mặc định

    Returns:
        Dict chứa:
          - "text": nội dung đã clean
          - "metadata": dict với source, department, effective_date, access
    """
    lines = raw_text.strip().splitlines()
    metadata = {
        "source": filepath,
        "section": "",
        "department": "unknown",
        "effective_date": "unknown",
        "access": "internal",
    }
    content_lines = []
    header_done = False

    for line in lines:
        if not header_done:
            # Parse metadata từ các dòng "Key: Value" ở header
            if line.startswith("Source:"):
                metadata["source"] = line.replace("Source:", "").strip()
            elif line.startswith("Department:"):
                metadata["department"] = line.replace("Department:", "").strip()
            elif line.startswith("Effective Date:"):
                metadata["effective_date"] = line.replace("Effective Date:", "").strip()
            elif line.startswith("Access:"):
                metadata["access"] = line.replace("Access:", "").strip()
            elif re.match(r"^===\s.*\s===$", line.strip()):
                # Gặp section heading đầu tiên → kết thúc header
                header_done = True
                content_lines.append(line)
            elif line.strip() == "" or line.strip().isupper():
                # Dòng trống hoặc dòng toàn chữ hoa (tên tài liệu) → bỏ qua
                continue
            else:
                # Dòng text khác trong header (vd: "Ghi chú: ...") → giữ lại
                content_lines.append(line)
        else:
            # Sau header: bỏ dòng toàn chữ hoa (không phải heading), giữ dòng trống
            stripped = line.strip()
            if stripped == "":
                content_lines.append("")  # giữ dòng trống để phân đoạn paragraph
            elif stripped.isupper() and not re.match(r"^===", stripped):
                # Dòng toàn chữ hoa nhưng KHÔNG phải heading → bỏ
                continue
            else:
                content_lines.append(line)

    cleaned_text = "\n".join(content_lines)

    # Chuẩn hóa khoảng trắng: loại bỏ nhiều dòng trống liên tiếp (tối đa 2)
    cleaned_text = re.sub(r"\n{3,}", "\n\n", cleaned_text)
    # Chuẩn hóa khoảng trắng thừa trong mỗi dòng (nhiều space → 1 space)
    cleaned_text = re.sub(r"[ \t]+", " ", cleaned_text)
    # Bỏ khoảng trắng đầu/cuối
    cleaned_text = cleaned_text.strip()

    return {
        "text": cleaned_text,
        "metadata": metadata,
    }


# =============================================================================
# STEP 2: CHUNK
# Chia tài liệu thành các đoạn nhỏ theo cấu trúc tự nhiên
# =============================================================================

def chunk_document(doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Chunk một tài liệu đã preprocess thành danh sách các chunk nhỏ.

    Args:
        doc: Dict với "text" và "metadata" (output của preprocess_document)

    Returns:
        List các Dict, mỗi dict là một chunk với:
          - "text": nội dung chunk
          - "metadata": metadata gốc + "section" của chunk đó

    Chiến lược:
    1. Split theo heading "=== Section ... ===" trước
    2. Nếu section quá dài (> CHUNK_SIZE * 4 ký tự), split tiếp theo paragraph
    3. Thêm overlap: lấy đoạn cuối của chunk trước vào đầu chunk tiếp theo
    4. Mỗi chunk giữ metadata đầy đủ từ tài liệu gốc
    """
    text = doc["text"]
    base_metadata = doc["metadata"].copy()
    chunks = []

    # Split theo heading pattern "=== ... ==="
    sections = re.split(r"(===.*?===)", text)

    current_section = "General"
    current_section_text = ""

    for part in sections:
        if re.match(r"===.*?===", part):
            # Lưu section trước (nếu có nội dung)
            if current_section_text.strip():
                section_chunks = _split_by_size(
                    current_section_text.strip(),
                    base_metadata=base_metadata,
                    section=current_section,
                )
                chunks.extend(section_chunks)
            # Bắt đầu section mới
            current_section = part.strip("= ").strip()
            current_section_text = ""
        else:
            current_section_text += part

    # Lưu section cuối cùng
    if current_section_text.strip():
        section_chunks = _split_by_size(
            current_section_text.strip(),
            base_metadata=base_metadata,
            section=current_section,
        )
        chunks.extend(section_chunks)

    return chunks


def _split_by_size(
    text: str,
    base_metadata: Dict,
    section: str,
    chunk_chars: int = CHUNK_SIZE * 4,
    overlap_chars: int = CHUNK_OVERLAP * 4,
) -> List[Dict[str, Any]]:
    """
    Helper: Split text dài thành chunks với overlap.

    Chiến lược cải tiến:
    - Split theo paragraph (\\n\\n) trước, rồi ghép đến khi gần đủ size
    - Overlap lấy n ký tự cuối chunk trước vào đầu chunk sau
    - Ưu tiên cắt tại ranh giới tự nhiên (cuối đoạn, cuối câu)
    """
    if len(text) <= chunk_chars:
        # Toàn bộ section vừa một chunk
        return [{
            "text": text,
            "metadata": {**base_metadata, "section": section},
        }]

    # Split theo paragraph
    paragraphs = text.split("\n\n")
    chunks = []
    current_chunk_parts = []
    current_len = 0

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        para_len = len(para)

        # Nếu thêm paragraph này sẽ vượt quá chunk_chars
        if current_len + para_len + 2 > chunk_chars and current_chunk_parts:
            # Lưu chunk hiện tại
            chunk_text = "\n\n".join(current_chunk_parts)
            chunks.append({
                "text": chunk_text,
                "metadata": {**base_metadata, "section": section},
            })

            # Tạo overlap: lấy phần cuối chunk trước làm đầu chunk sau
            overlap_text = _get_overlap(chunk_text, overlap_chars)
            current_chunk_parts = []
            current_len = 0
            if overlap_text:
                current_chunk_parts.append(overlap_text)
                current_len = len(overlap_text)

        # Nếu 1 paragraph đơn lẻ đã dài hơn chunk_chars → cắt theo câu
        if para_len > chunk_chars:
            # Lưu phần đang tích lũy trước
            if current_chunk_parts:
                chunk_text = "\n\n".join(current_chunk_parts)
                chunks.append({
                    "text": chunk_text,
                    "metadata": {**base_metadata, "section": section},
                })
                current_chunk_parts = []
                current_len = 0

            # Cắt paragraph dài theo câu
            sentence_chunks = _split_long_paragraph(para, chunk_chars, overlap_chars)
            for sc in sentence_chunks:
                chunks.append({
                    "text": sc,
                    "metadata": {**base_metadata, "section": section},
                })
            continue

        current_chunk_parts.append(para)
        current_len += para_len + 2  # +2 cho "\n\n"

    # Lưu chunk cuối
    if current_chunk_parts:
        chunk_text = "\n\n".join(current_chunk_parts)
        chunks.append({
            "text": chunk_text,
            "metadata": {**base_metadata, "section": section},
        })

    return chunks


def _get_overlap(text: str, overlap_chars: int) -> str:
    """
    Lấy phần overlap từ cuối đoạn text, ưu tiên cắt tại ranh giới câu.
    """
    if len(text) <= overlap_chars:
        return text

    overlap_region = text[-overlap_chars:]

    # Tìm ranh giới câu gần nhất trong vùng overlap (dấu . ! ? kết thúc câu)
    sentence_break = -1
    for pattern in [". ", ".\n", "? ", "?\n", "! ", "!\n"]:
        idx = overlap_region.find(pattern)
        if idx != -1 and idx > sentence_break:
            sentence_break = idx

    if sentence_break != -1:
        # Bắt đầu overlap từ sau câu kết thúc
        return overlap_region[sentence_break + 2:].strip()

    return overlap_region.strip()


def _split_long_paragraph(text: str, chunk_chars: int, overlap_chars: int) -> List[str]:
    """
    Cắt 1 paragraph rất dài thành các chunk, ưu tiên cắt tại cuối câu.
    """
    # Tách theo câu (giữ dấu câu)
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks = []
    current = ""

    for sentence in sentences:
        if len(current) + len(sentence) + 1 > chunk_chars and current:
            chunks.append(current.strip())
            # Overlap: lấy phần cuối
            overlap = _get_overlap(current, overlap_chars)
            current = overlap + " " + sentence if overlap else sentence
        else:
            current = (current + " " + sentence).strip() if current else sentence

    if current.strip():
        chunks.append(current.strip())

    return chunks


# =============================================================================
# STEP 3: EMBED + STORE
# Embed các chunk và lưu vào ChromaDB
# =============================================================================

def get_embedding(text: str) -> List[float]:
    """
    Tạo embedding vector cho một đoạn text.

    TODO Sprint 1:
    Chọn một trong hai:

    Option A — OpenAI Embeddings (cần OPENAI_API_KEY):
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.embeddings.create(
            input=text,
            model="text-embedding-3-small"
        )
        return response.data[0].embedding

    Option B — Sentence Transformers (chạy local, không cần API key):
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
        return model.encode(text).tolist()
    """
    raise NotImplementedError(
        "TODO: Implement get_embedding().\n"
        "Chọn Option A (OpenAI) hoặc Option B (Sentence Transformers) trong TODO comment."
    )


def build_index(docs_dir: Path = DOCS_DIR, db_dir: Path = CHROMA_DB_DIR) -> None:
    """
    Pipeline hoàn chỉnh: đọc docs → preprocess → chunk → embed → store.

    TODO Sprint 1:
    1. Cài thư viện: pip install chromadb
    2. Khởi tạo ChromaDB client và collection
    3. Với mỗi file trong docs_dir:
       a. Đọc nội dung
       b. Gọi preprocess_document()
       c. Gọi chunk_document()
       d. Với mỗi chunk: gọi get_embedding() và upsert vào ChromaDB
    4. In số lượng chunk đã index

    Gợi ý khởi tạo ChromaDB:
        import chromadb
        client = chromadb.PersistentClient(path=str(db_dir))
        collection = client.get_or_create_collection(
            name="rag_lab",
            metadata={"hnsw:space": "cosine"}
        )
    """
    import chromadb

    print(f"Đang build index từ: {docs_dir}")
    db_dir.mkdir(parents=True, exist_ok=True)

    # Khởi tạo ChromaDB persistent client
    client = chromadb.PersistentClient(path=str(db_dir))
    collection = client.get_or_create_collection(
        name="rag_lab",
        metadata={"hnsw:space": "cosine"}
    )

    total_chunks = 0
    doc_files = list(docs_dir.glob("*.txt"))

    if not doc_files:
        print(f"Không tìm thấy file .txt trong {docs_dir}")
        return

    for filepath in doc_files:
        print(f"  Processing: {filepath.name}")

        # Đọc nội dung file UTF-8
        raw_text = filepath.read_text(encoding="utf-8")

        # Preprocess: extract metadata + clean text
        doc = preprocess_document(raw_text, str(filepath))

        # Chunk theo section + paragraph
        chunks = chunk_document(doc)

        # Embed và lưu từng chunk vào ChromaDB
        for i, chunk in enumerate(chunks):
            chunk_id = f"{filepath.stem}_{i}"
            embedding = get_embedding(chunk["text"])
            collection.upsert(
                ids=[chunk_id],
                embeddings=[embedding],
                documents=[chunk["text"]],
                metadatas=[chunk["metadata"]],
            )

        total_chunks += len(chunks)
        print(f"    → {len(chunks)} chunks indexed")

    print(f"\nHoàn thành! Tổng số chunks: {total_chunks}")


# =============================================================================
# STEP 4: INSPECT / KIỂM TRA
# Dùng để debug và kiểm tra chất lượng index
# =============================================================================

def list_chunks(db_dir: Path = CHROMA_DB_DIR, n: int = 5) -> None:
    """
    In ra n chunk đầu tiên trong ChromaDB để kiểm tra chất lượng index.

    Kiểm tra:
    - Chunk có giữ đủ metadata không? (source, section, effective_date)
    - Chunk có bị cắt giữa điều khoản không?
    - Metadata effective_date có đúng không?
    """
    try:
        import chromadb
        client = chromadb.PersistentClient(path=str(db_dir))
        collection = client.get_collection("rag_lab")
        results = collection.get(limit=n, include=["documents", "metadatas"])

        print(f"\n=== Top {n} chunks trong index ===\n")
        for i, (doc, meta) in enumerate(zip(results["documents"], results["metadatas"])):
            print(f"[Chunk {i+1}]")
            print(f"  Source: {meta.get('source', 'N/A')}")
            print(f"  Section: {meta.get('section', 'N/A')}")
            print(f"  Department: {meta.get('department', 'N/A')}")
            print(f"  Effective Date: {meta.get('effective_date', 'N/A')}")
            print(f"  Access: {meta.get('access', 'N/A')}")
            print(f"  Text preview: {doc[:200]}...")
            print()
    except Exception as e:
        print(f"Lỗi khi đọc index: {e}")
        print("Hãy chạy build_index() trước.")


def inspect_metadata_coverage(db_dir: Path = CHROMA_DB_DIR) -> None:
    """
    Kiểm tra phân phối metadata trong toàn bộ index.

    Checklist Sprint 1:
    - Mọi chunk đều có source?
    - Có bao nhiêu chunk từ mỗi department?
    - Chunk nào thiếu effective_date?
    """
    try:
        import chromadb
        client = chromadb.PersistentClient(path=str(db_dir))
        collection = client.get_collection("rag_lab")
        results = collection.get(include=["metadatas"])

        total = len(results["metadatas"])
        print(f"\n{'='*50}")
        print(f"METADATA COVERAGE REPORT")
        print(f"{'='*50}")
        print(f"Tổng chunks: {total}")

        # Phân tích metadata
        departments = {}
        missing_date = 0
        access_types = {}
        sources = {}

        for meta in results["metadatas"]:
            # Department distribution
            dept = meta.get("department", "unknown")
            departments[dept] = departments.get(dept, 0) + 1

            # Check missing effective_date
            if meta.get("effective_date") in ("unknown", "", None):
                missing_date += 1

            # Access type distribution
            acc = meta.get("access", "N/A")
            access_types[acc] = access_types.get(acc, 0) + 1

            # Source distribution
            src = meta.get("source", "N/A")
            sources[src] = sources.get(src, 0) + 1

        print(f"\n--- Phân bố theo Department ---")
        for dept, count in sorted(departments.items()):
            print(f"  {dept}: {count} chunks")

        print(f"\n--- Phân bố theo Source ---")
        for src, count in sorted(sources.items()):
            print(f"  {src}: {count} chunks")

        print(f"\n--- Phân bố theo Access ---")
        for acc, count in sorted(access_types.items()):
            print(f"  {acc}: {count} chunks")

        print(f"\n--- Chất lượng metadata ---")
        print(f"  Chunks thiếu effective_date: {missing_date}/{total}")
        print(f"  Metadata fields hữu ích: source, section, department, effective_date, access (5 fields)")
        print(f"{'='*50}")

    except Exception as e:
        print(f"Lỗi: {e}. Hãy chạy build_index() trước.")


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Sprint 1: Build RAG Index")
    print("=" * 60)

    # Bước 1: Kiểm tra docs
    doc_files = list(DOCS_DIR.glob("*.txt"))
    print(f"\nTìm thấy {len(doc_files)} tài liệu:")
    for f in doc_files:
        print(f"  - {f.name}")

    # Bước 2: Test preprocess và chunking (không cần API key)
    print("\n--- Test preprocess + chunking ---")
    for filepath in doc_files[:1]:  # Test với 1 file đầu
        raw = filepath.read_text(encoding="utf-8")
        doc = preprocess_document(raw, str(filepath))
        chunks = chunk_document(doc)
        print(f"\nFile: {filepath.name}")
        print(f"  Metadata: {doc['metadata']}")
        print(f"  Số chunks: {len(chunks)}")
        for i, chunk in enumerate(chunks[:3]):
            print(f"\n  [Chunk {i+1}] Section: {chunk['metadata']['section']}")
            print(f"  Text: {chunk['text'][:150]}...")

    # Bước 3: Build full index (embed + store vào ChromaDB)
    print("\n--- Build Full Index ---")
    build_index()

    # Bước 4: Kiểm tra index
    print("\n--- Kiểm tra Index ---")
    list_chunks(n=10)
    inspect_metadata_coverage()

    print("\nSprint 1 hoàn thành!")
    print("Việc cần làm:")
    print("  1. Implement get_embedding() - chọn OpenAI hoặc Sentence Transformers")
    print("  2. Implement phần TODO trong build_index()")
    print("  3. Chạy build_index() và kiểm tra với list_chunks()")
    print("  4. Nếu chunking chưa tốt: cải thiện _split_by_size() để split theo paragraph")
