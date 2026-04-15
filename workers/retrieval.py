"""
workers/retrieval.py — Retrieval Worker
Sprint 2: Implement retrieval từ ChromaDB, trả về chunks + sources.

Input (từ AgentState):
    - task: câu hỏi cần retrieve
    - (optional) retrieved_chunks nếu đã có từ trước

Output (vào AgentState):
    - retrieved_chunks: list of {"text", "source", "score", "metadata"}
    - retrieved_sources: list of source filenames
    - worker_io_log: log input/output của worker này

Gọi độc lập để test:
    python workers/retrieval.py
"""

import os
import sys
from dotenv import load_dotenv
load_dotenv()

# ─────────────────────────────────────────────
# Worker Contract (xem contracts/worker_contracts.yaml)
# Input:  {"task": str, "top_k": int = 3}
# Output: {"retrieved_chunks": list, "retrieved_sources": list, "error": dict | None}
# ─────────────────────────────────────────────

WORKER_NAME = "retrieval_worker"
DEFAULT_TOP_K = 3


_cached_embed_fn = None

def _get_embedding_fn():
    """
    Trả về một 'hàm đóng' (closure) để thực hiện embedding.
    Cơ chế: Thử Local trước -> Thử API sau -> Cuối cùng là Random.
    """
    global _cached_embed_fn
    if _cached_embed_fn is not None:
        return _cached_embed_fn
        
    # 1. THỬ DÙNG LOCAL (Phù hợp với Lab 8 bạn đã làm)
    try:
        from sentence_transformers import SentenceTransformer
        # Lấy model name từ .env để linh hoạt, mặc định là BKAI của Lab 8
        model_name = os.getenv("LOCAL_EMBEDDING_MODEL", "bkai-foundation-models/vietnamese-bi-encoder")
        model = SentenceTransformer(model_name)
        
        def embed(text: str) -> list:
            # model.encode trả về numpy array, cần .tolist() để ChromaDB nhận
            return model.encode(text).tolist()
            
        _cached_embed_fn = embed
        return embed
    except (ImportError, Exception):
        # Nếu chưa cài thư viện hoặc không load được model, nhảy xuống Option B
        pass

    # 2. THỬ DÙNG OPENAI (Cần API Key trong .env)
    try:
        from openai import OpenAI
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            client = OpenAI(api_key=api_key)
            def embed(text: str) -> list:
                # model text-embedding-3-small rẻ và hiệu quả
                resp = client.embeddings.create(input=[text], model="text-embedding-3-small")
                return resp.data[0].embedding
                
            _cached_embed_fn = embed
            return embed
    except (ImportError, Exception):
        pass

    # 3. FALLBACK: RANDOM (Chỉ dùng để debug luồng code)
    import random
    def embed(text: str) -> list:
        # 768 là số chiều của model BKAI bạn dùng ở Lab 8
        return [random.random() for _ in range(768)]
        
    _cached_embed_fn = embed
    return embed


def _get_collection():
    """
    Kết nối ChromaDB collection '{CHROMA_COLLECTION}' trong folder 'chroma_db' ở thư mục gốc.
    Đảm bảo đường dẫn chính xác dù chạy từ thư mục workers/ hay thư mục gốc.
    """
    import chromadb
    from pathlib import Path
    import os

    # 1. Xử lý đường dẫn (Path)
    # Vì file retrieval.py nằm trong folder 'workers/', 
    # ta cần lùi lại 1 cấp để ra thư mục gốc chứa folder 'chroma_db'
    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent
    db_path = str(project_root / "chroma_db")

    # 2. Khởi tạo Client kết nối tới folder vật lý
    client = chromadb.PersistentClient(path=db_path)

    # 3. Tên collection phải khớp 100% với tên bạn đã đặt trong index.py ở Lab 8
    collection_name = os.getenv("CHROMA_COLLECTION", "")  # Lấy từ .env để linh hoạt

    try:
        # Thử lấy collection đã có dữ liệu
        collection = client.get_collection(name=collection_name)
        return collection
    except Exception:
        # Nếu không tìm thấy, báo lỗi yêu cầu chạy index.py
        print(f"⚠️  CẢNH BÁO: Không tìm thấy collection '{collection_name}' tại {db_path}")
        
        # Tạo mới collection trống để tránh crash code, nhưng sẽ cảnh báo người dùng
        collection = client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}
        )
        return collection


def retrieve_dense(query: str, top_k: int = DEFAULT_TOP_K) -> list:
    # 1. Lấy hàm embed
    embed_fn = _get_embedding_fn()
    
    # 2. Tạo vector từ câu hỏi
    print("  [Debug] Đang biến câu hỏi thành vector...")
    query_embedding = embed_fn(query)
    print(f"  [Debug] Kích thước vector truy vấn: {len(query_embedding)}") # Phải là 768

    try:
        collection = _get_collection()
        if collection is None:
            return []

        print(f"  [Debug] Đang query collection '{collection.name}'...")
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "distances", "metadatas"]
        )

        # Kiểm tra kết quả trả về có rỗng không
        if not results["documents"] or len(results["documents"][0]) == 0:
            print("  [Debug] ⚠️ Database không tìm thấy đoạn văn nào phù hợp!")
            return []

        chunks = []
        for i in range(len(results["documents"][0])):
            meta = results["metadatas"][0][i]
            chunks.append({
                "text": results["documents"][0][i],
                "source": meta.get("source", "unknown"),
                "score": round(1 - results["distances"][0][i], 4),
                "metadata": meta, 
            })
        return chunks

    except Exception as e:
        print(f"❌ LỖI TẠI TRUY VẤN: {e}") # Đừng để 'pass' ở đây nhé Giang
        return []

def retrieve_sparse(query: str, top_k: int = 5):
    """Keyword search (BM25) - Chép từ Lab 8 sang"""
    from rank_bm25 import BM25Okapi
    collection = _get_collection()
    all_data = collection.get(include=["documents", "metadatas"])
    
    corpus = all_data["documents"]
    tokenized_corpus = [doc.lower().split() for doc in corpus]
    bm25 = BM25Okapi(tokenized_corpus)
    
    tokenized_query = query.lower().split()
    doc_scores = bm25.get_scores(tokenized_query)
    top_indices = sorted(range(len(doc_scores)), key=lambda i: doc_scores[i], reverse=True)[:top_k]
    
    return [{
        "text": corpus[i],
        "source": all_data["metadatas"][i].get("source", "unknown") if all_data["metadatas"][i] else "unknown",
        "metadata": all_data["metadatas"][i],
        "score": float(doc_scores[i])
    } for i in top_indices]

def retrieve_hybrid(query: str, top_k: int = 3):
    """Kết hợp Dense + Sparse (RRF) như Lab 8"""
    dense_res = retrieve_dense(query, top_k=top_k*2)
    sparse_res = retrieve_sparse(query, top_k=top_k*2)
    
    rrf_scores = {}
    for rank, doc in enumerate(dense_res):
        rrf_scores[doc["text"]] = rrf_scores.get(doc["text"], 0) + 1.0 / (60 + rank)
    for rank, doc in enumerate(sparse_res):
        rrf_scores[doc["text"]] = rrf_scores.get(doc["text"], 0) + 1.0 / (60 + rank)
        
    sorted_texts = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
    
    all_res = dense_res + sparse_res
    final = []
    for text, _ in sorted_texts:
        match = next(d for d in all_res if d["text"] == text)
        final.append(match)
    return final

def run(state: dict) -> dict:
    task = state.get("task", "")
    top_k = state.get("top_k", DEFAULT_TOP_K)
    mode = state.get("retrieval_mode", "dense") # Mặc định dense, có thể đổi sang hybrid
    
    if "worker_io_logs" not in state:
        state["worker_io_logs"] = []
        
    io_log = {
        "worker": WORKER_NAME,
        "input": {"task": task, "top_k": top_k, "mode": mode}
    }
    
    if not task:
        state["error"] = {"code": "RETRIEVAL_FAILED", "reason": "Missing 'task' in input"}
        io_log["error"] = state.get("error")
        state["worker_io_logs"].append(io_log)
        return state

    try:
        if mode == "hybrid":
            chunks = retrieve_hybrid(task, top_k=top_k)
        else:
            chunks = retrieve_dense(task, top_k=top_k)
            
        state["retrieved_chunks"] = chunks
        state["retrieved_sources"] = list({c.get("source", "unknown") for c in chunks})
        
        io_log["output"] = {
            "retrieved_chunks_count": len(chunks),
            "retrieved_sources": state["retrieved_sources"]
        }
    except Exception as e:
        state["error"] = {"code": "RETRIEVAL_FAILED", "reason": str(e)}
        state["retrieved_chunks"] = []
        state["retrieved_sources"] = []
        io_log["error"] = state["error"]

    state["worker_io_logs"].append(io_log)
    return state


# ─────────────────────────────────────────────
# Test độc lập
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("Retrieval Worker — Standalone Test")
    print("=" * 50)

    test_queries = [
        "SLA ticket P1 là bao lâu?",
        "Điều kiện được hoàn tiền là gì?",
        "Ai phê duyệt cấp quyền Level 3?",
    ]

    for query in test_queries:
        print(f"\n▶ Query: {query} (Hybrid Mode)")
        result = run({"task": query, "retrieval_mode": "hybrid"})
        chunks = result.get("retrieved_chunks", [])
        print(f"  Retrieved: {len(chunks)} chunks")
        for c in chunks[:2]:
            print(f"    [{c['score']:.3f}] {c['source']}: {c['text'][:80]}...")
        print(f"  Sources: {result.get('retrieved_sources', [])}")

    print("\n✅ retrieval_worker test done.")
