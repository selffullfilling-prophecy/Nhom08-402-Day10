"""
workers/policy_tool.py — Policy & Tool Worker
Sprint 2+3: Kiểm tra policy qua LLM và gọi MCP tools qua HTTP (FastAPI Server).
"""

import os
import json
import httpx
from datetime import datetime
from typing import Optional
from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()
WORKER_NAME = "policy_tool_worker"

# ─────────────────────────────────────────────
# REAL MCP Client — Giao tiếp qua HTTP tới FastAPI Server
# ─────────────────────────────────────────────

def _call_mcp_tool(tool_name: str, tool_input: dict) -> dict:
    """
    Gọi MCP tool thông qua HTTP POST request tới MCP Server.
    Yêu cầu MCP Server (mcp_server.py) đang chạy ở cổng 8000.
    """
    try:
        url = f"http://127.0.0.1:8000/tools/{tool_name}"
        
        # Gửi POST request kèm JSON body
        # Dùng with httpx.Client() để đảm bảo đóng kết nối an toàn
        with httpx.Client() as client:
            response = client.post(url, json=tool_input, timeout=10.0)
            response.raise_for_status() # Bắn lỗi nếu status code là 4xx, 5xx
            result = response.json()
        
        return {
            "tool": tool_name,
            "input": tool_input,
            "output": result,
            "error": None,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        print(f"⚠️ [MCP Client Error] Gọi tool {tool_name} thất bại: {e}")
        return {
            "tool": tool_name,
            "input": tool_input,
            "output": None,
            "error": {"code": "MCP_CALL_FAILED", "reason": str(e)},
            "timestamp": datetime.now().isoformat(),
        }


# ─────────────────────────────────────────────
# LLM-Based Policy Analysis Logic
# ─────────────────────────────────────────────

def analyze_policy(task: str, chunks: list) -> dict:
    """
    Phân tích policy bằng LLM dựa trên context chunks thay vì rule-based.
    """
    if not chunks:
        return {
            "policy_applies": True, 
            "exceptions_found": [], 
            "policy_name": "unknown", 
            "explanation": "Không có ngữ cảnh (context) để kiểm tra chính sách."
        }

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    context_text = "\n---\n".join([c.get("text", "") for c in chunks])
    
    prompt = f"""Bạn là một chuyên gia phân tích chính sách công ty.
    Dựa vào ngữ cảnh (Context) bên dưới, hãy đánh giá yêu cầu (Task) của người dùng.
    Xác định xem có chính sách nào áp dụng không, và có ngoại lệ (exception/từ chối) nào bị vi phạm không.

    Task: {task}
    Context: 
    {context_text}

    Trả về đúng định dạng JSON:
    {{
        "policy_applies": boolean,  // True nếu ĐƯỢC PHÉP/HỢP LỆ (không vi phạm ngoại lệ)
        "policy_name": "Tên chính sách (vd: Policy v4)",
        "exceptions_found": [
            {{"type": "tên ngoại lệ", "rule": "Trích dẫn luật", "source": "Nguồn luật"}}
        ],
        "explanation": "Giải thích ngắn gọn lý do"
    }}
    """

    try:
        response = client.chat.completions.create(
            model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            response_format={"type": "json_object"}
        )
        result = json.loads(response.choices[0].message.content)
        result["source"] = list({c.get("source", "unknown") for c in chunks})
        return result
    except Exception as e:
        print(f"⚠️ [Policy LLM Error]: {e}")
        return {
            "policy_applies": True, 
            "exceptions_found": [],
            "source": list({c.get("source", "unknown") for c in chunks}),
            "error": str(e)
        }


# ─────────────────────────────────────────────
# Worker Entry Point
# ─────────────────────────────────────────────

def run(state: dict) -> dict:
    """Worker entry point — gọi từ graph.py."""
    task = state.get("task", "")
    chunks = state.get("retrieved_chunks", [])
    needs_tool = state.get("needs_tool", False)

    state.setdefault("workers_called", [])
    state.setdefault("history", [])
    state.setdefault("mcp_tools_used", [])

    state["workers_called"].append(WORKER_NAME)

    worker_io = {
        "worker": WORKER_NAME,
        "input": {
            "task": task,
            "chunks_count": len(chunks),
            "needs_tool": needs_tool,
        },
        "output": None,
        "error": None,
    }

    try:
        # Step 1: Nếu chưa có chunks nhưng được phép dùng tool, gọi MCP search_kb
        if not chunks and needs_tool:
            mcp_result = _call_mcp_tool("search_kb", {"query": task, "top_k": 3})
            state["mcp_tools_used"].append(mcp_result)
            state["history"].append(f"[{WORKER_NAME}] called MCP search_kb")

            if mcp_result.get("output") and mcp_result["output"].get("chunks"):
                chunks = mcp_result["output"]["chunks"]
                state["retrieved_chunks"] = chunks

        # Step 2: Phân tích policy qua LLM
        policy_result = analyze_policy(task, chunks)
        state["policy_result"] = policy_result

        # Step 3: Nếu cần thêm info từ MCP (e.g., ticket status)
        if needs_tool and any(kw in task.lower() for kw in ["ticket", "p1", "jira"]):
            mcp_result = _call_mcp_tool("get_ticket_info", {"ticket_id": "P1-LATEST"})
            state["mcp_tools_used"].append(mcp_result)
            state["history"].append(f"[{WORKER_NAME}] called MCP get_ticket_info")

        # Step 4: Nếu nhắc tới quyền hạn (access/quyền)
        if needs_tool and any(kw in task.lower() for kw in ["cấp quyền", "level 3", "access"]):
            mcp_result = _call_mcp_tool("check_access_permission", {
                "access_level": 3, 
                "requester_role": "user",
                "is_emergency": "khẩn cấp" in task.lower()
            })
            state["mcp_tools_used"].append(mcp_result)
            state["history"].append(f"[{WORKER_NAME}] called MCP check_access_permission")

        worker_io["output"] = {
            "policy_applies": policy_result.get("policy_applies", True),
            "exceptions_count": len(policy_result.get("exceptions_found", [])),
            "mcp_calls": len(state["mcp_tools_used"]),
        }
        state["history"].append(
            f"[{WORKER_NAME}] policy_applies={policy_result.get('policy_applies')}, "
            f"exceptions={len(policy_result.get('exceptions_found', []))}"
        )

    except Exception as e:
        worker_io["error"] = {"code": "POLICY_CHECK_FAILED", "reason": str(e)}
        state["policy_result"] = {"error": str(e)}
        state["history"].append(f"[{WORKER_NAME}] ERROR: {e}")

    state.setdefault("worker_io_logs", []).append(worker_io)
    return state


# ─────────────────────────────────────────────
# Test độc lập
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("Policy Tool Worker — Standalone Test")
    print("=" * 50)
    
    print("⚠️  Đảm bảo bạn đã chạy MCP Server ở một terminal khác bằng lệnh:")
    print("   uvicorn mcp_server:app --port 8000\n")

    test_cases = [
        {
            "task": "Khách hàng Flash Sale yêu cầu hoàn tiền vì sản phẩm lỗi — được không?",
            "needs_tool": False,
            "retrieved_chunks": [
                {"text": "Điều 3: Đơn hàng Flash Sale và sản phẩm kỹ thuật số không được hỗ trợ hoàn tiền trong mọi trường hợp.", "source": "policy_refund_v4.txt", "score": 0.9}
            ],
        },
        {
            "task": "Kiểm tra tình trạng ticket P1 giúp tôi.",
            "needs_tool": True, # Test HTTP call
            "retrieved_chunks": [],
        }
    ]

    for tc in test_cases:
        print(f"▶ Task: {tc['task']}")
        result = run(tc.copy())
        
        pr = result.get("policy_result", {})
        print(f"  [LLM Policy] applies: {pr.get('policy_applies')}")
        if pr.get("exceptions_found"):
            for ex in pr["exceptions_found"]:
                print(f"      - Ngoại lệ: {ex.get('type')}")
                
        tools_used = result.get("mcp_tools_used", [])
        print(f"  [MCP Tools] Used {len(tools_used)} tools.")
        for t in tools_used:
            print(f"      - {t['tool']} trả về: {str(t['output'])[:80]}...")
        print("-" * 30)

    print("\n✅ policy_tool_worker test done.")