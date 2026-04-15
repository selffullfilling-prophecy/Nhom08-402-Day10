import os
from typing import List, Dict, Any
from dotenv import load_dotenv
import json
load_dotenv()

WORKER_NAME = "synthesis_worker"

# System Prompt ép Agent phải trung thực (Grounded Answer)
SYSTEM_PROMPT = """Bạn là trợ lý hỗ trợ nội bộ thông minh.
Nhiệm vụ: Tổng hợp câu trả lời từ Context và Policy.

QUY TẮC:
1. CHỈ dùng thông tin được cung cấp. Không tự bịa.
2. Nếu thiếu context -> nói "Không đủ thông tin trong tài liệu nội bộ".
3. Trích dẫn nguồn cuối mỗi đoạn: [tên_file].
4. Nêu rõ Ngoại lệ (Policy Exceptions) ngay đầu câu trả lời nếu có.
"""

def _call_llm(messages: list) -> str:
    """Gọi OpenAI GPT - Giữ nguyên như Lab 8 của Giang"""
    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
            messages=messages,
            temperature=0.1,
            max_tokens=500,
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"[SYNTHESIS ERROR] Lỗi API: {str(e)}"

def _build_context(chunks: list, policy_result: dict) -> str:
    """Xây dựng context string từ chunks và policy result"""
    parts = []
    
    # Thêm phần Policy trước để AI ưu tiên
    if policy_result and policy_result.get("exceptions_found"):
        parts.append("=== POLICY EXCEPTIONS (QUAN TRỌNG) ===")
        for ex in policy_result["exceptions_found"]:
            parts.append(f"- {ex.get('rule', '')} (Nguồn: {ex.get('source', '')})")

    # Thêm các đoạn văn bản tìm được
    if chunks:
        parts.append("\n=== TÀI LIỆU THAM KHẢO ===")
        for i, chunk in enumerate(chunks, 1):
            source = chunk.get("source", "unknown")
            text = chunk.get("text", "")
            parts.append(f"[{i}] Nguồn: {source}\n{text}")

    return "\n\n".join(parts) if parts else "(Không có context)"
def _estimate_confidence(task: str, chunks: list, answer: str, policy_result: dict) -> float:
    """
    Sử dụng LLM-as-a-Judge để tự động chấm điểm độ tin cậy (Confidence Score).
    """
    # 1. Bắt các trường hợp rỗng hoặc từ chối trả lời
    if not chunks or "không đủ thông tin" in answer.lower():
        return 0.1

    # 2. Chuẩn bị dữ liệu cho Giám khảo LLM
    context_text = "\n".join([c.get("text", "") for c in chunks])
    if policy_result and policy_result.get("exceptions_found"):
        context_text += "\n[NGOẠI LỆ CHÍNH SÁCH]: " + str(policy_result.get("exceptions_found"))

    judge_prompt = f"""Bạn là một giám khảo độc lập (LLM-as-a-Judge).
    Nhiệm vụ: Đánh giá độ tin cậy (confidence score) của Câu trả lời so với Ngữ cảnh được cung cấp.

    Câu hỏi từ người dùng: {task}
    Ngữ cảnh có sẵn: {context_text}
    Câu trả lời cần chấm: {answer}

    Tiêu chí chấm điểm (0.0 đến 1.0):
    - 0.9 - 1.0: Câu trả lời chính xác, giải quyết trọn vẹn câu hỏi, được trích xuất hoàn toàn từ ngữ cảnh.
    - 0.7 - 0.89: Trả lời đúng phần lớn nhưng ngữ cảnh hỗ trợ hơi yếu hoặc thiếu một chút chi tiết.
    - 0.4 - 0.69: Trả lời chung chung, hoặc ngữ cảnh không thực sự sát với câu hỏi.
    - 0.1 - 0.39: Lạc đề, bịa đặt (hallucination), hoặc câu trả lời nói rằng không đủ thông tin.

    Trả về ĐÚNG định dạng JSON:
    {{
        "confidence": <float>,
        "reasoning": "<giải thích ngắn gọn 1 câu tại sao cho điểm này>"
    }}
    """

    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
            messages=[{"role": "user", "content": judge_prompt}],
            temperature=0.0, # Nhiệt độ 0 để AI chấm điểm khách quan và ổn định nhất
            response_format={"type": "json_object"}
        )
        
        result = json.loads(response.choices[0].message.content)
        conf = float(result.get("confidence", 0.5))
        reasoning = result.get("reasoning", "")
        
        # In log ra màn hình để bạn dễ theo dõi AI đang "nghĩ" gì
        print(f"  [LLM Judge] Chấm: {conf} | Lý do: {reasoning}")

        # Vẫn phạt nhẹ nếu dính ngoại lệ chính sách (do tính chất phức tạp)
        penalty = 0.05 * len(policy_result.get("exceptions_found", []))
        final_conf = max(0.1, min(0.98, conf - penalty))
        
        return round(final_conf, 2)
        
    except Exception as e:
        print(f"  [LLM Judge] Lỗi khi chấm điểm: {e}. Fallback về mức 0.5")
        return 0.5


def synthesize(task: str, chunks: list, policy_result: dict) -> dict:
    """
    Hàm tổng hợp chính (Internal Pipeline)
    """
    context = _build_context(chunks, policy_result)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Câu hỏi: {task}\n\nNgữ cảnh:\n{context}\n\nHãy trả lời dựa trên tài liệu."}
    ]

    answer = _call_llm(messages)
    sources = list({c.get("source", "unknown") for c in chunks})
    
    # TRUYỀN THÊM `task` (câu hỏi) VÀO HÀM CHẤM ĐIỂM
    confidence = _estimate_confidence(task, chunks, answer, policy_result)

    return {
        "answer": answer,
        "sources": sources,
        "confidence": confidence,
    }

def run(state: dict) -> dict:
    """
    Worker entry point - Điểm tiếp nhận chính từ Graph
    """
    task = state.get("task", "")
    chunks = state.get("retrieved_chunks", [])
    policy_result = state.get("policy_result", {})

    state.setdefault("worker_io_logs", [])
    io_log = {
        "worker": WORKER_NAME,
        "input": {"task": task, "chunks_count": len(chunks)}
    }

    # Ghi log lịch sử gọi worker
    state.setdefault("workers_called", []).append(WORKER_NAME)
    state.setdefault("history", [])

    try:
        # Gọi hàm xử lý logic
        result = synthesize(task, chunks, policy_result)
        
        # Cập nhật kết quả vào State chung
        state["final_answer"] = result["answer"]
        state["sources"] = result["sources"] # Sửa thành keys "sources" theo contract
        state["confidence"] = result["confidence"]
        
        io_log["output"] = {
            "final_answer": result["answer"][:50] + "...",
            "sources": result["sources"],
            "confidence": result["confidence"]
        }
        state["history"].append(f"[{WORKER_NAME}] Đã tạo câu trả lời. Confidence: {result['confidence']}")

    except Exception as e:
        state["error"] = {"code": "SYNTHESIS_FAILED", "reason": str(e)}
        state["final_answer"] = f"Lỗi tổng hợp: {str(e)}"
        state["sources"] = []
        state["confidence"] = 0.0
        io_log["error"] = state["error"]
        state["history"].append(f"[{WORKER_NAME}] ERROR: {e}")

    state["worker_io_logs"].append(io_log)
    return state

# --- Test độc lập ---
if __name__ == "__main__":
    print("--- Testing Synthesis Worker ---")
    test_state = {
        "task": "SLA P1 là bao lâu?",
        "retrieved_chunks": [{"text": "SLA cho P1 là 4 giờ làm việc.", "source": "sla_2026.txt", "score": 0.9}],
        "policy_result": {}
    }
    res = run(test_state)
    print(f"Answer: {res['final_answer']}")
    print(f"Confidence: {res['confidence']}")