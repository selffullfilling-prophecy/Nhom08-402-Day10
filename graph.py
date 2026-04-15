"""
graph.py — Supervisor Orchestrator
Sprint 2+3: Kết nối đồ thị (Graph) với các Worker thực tế.

Kiến trúc:
    Input → Supervisor → [retrieval_worker | policy_tool_worker | human_review] → synthesis → Output

Chạy thử:
    python graph.py
"""

import json
import os
from datetime import datetime
from typing import TypedDict, Literal, Optional

# Dùng LangGraph:
from langgraph.graph import StateGraph, END

# Import các Worker thực tế (Sprint 2+3)
from workers.retrieval import run as retrieval_run
from workers.policy_tool import run as policy_tool_run
from workers.synthesis import run as synthesis_run

# ─────────────────────────────────────────────
# 1. Shared State — dữ liệu đi xuyên toàn graph
# ─────────────────────────────────────────────

class AgentState(TypedDict):
    # Input
    task: str                           # Câu hỏi đầu vào từ user

    # Supervisor decisions
    route_reason: str                   # Lý do route sang worker nào
    risk_high: bool                     # True → cần HITL hoặc human_review
    needs_tool: bool                    # True → cần gọi external tool qua MCP
    hitl_triggered: bool                # True → đã pause cho human review

    # Worker outputs
    retrieved_chunks: list              # Output từ retrieval_worker
    retrieved_sources: list             # Danh sách nguồn tài liệu
    policy_result: dict                 # Output từ policy_tool_worker
    mcp_tools_used: list                # Danh sách MCP tools đã gọi

    # Final output
    final_answer: str                   # Câu trả lời tổng hợp
    sources: list                       # Sources được cite
    confidence: float                   # Mức độ tin cậy (0.0 - 1.0)

    # Trace & history
    history: list                       # Lịch sử các bước đã qua
    workers_called: list                # Danh sách workers đã được gọi
    supervisor_route: str               # Worker được chọn bởi supervisor
    latency_ms: Optional[int]           # Thời gian xử lý (ms)
    run_id: str                         # ID của run này
    worker_io_logs: list                # Log I/O của các workers


def make_initial_state(task: str) -> AgentState:
    """Khởi tạo state cho một run mới."""
    return {
        "task": task,
        "route_reason": "",
        "risk_high": False,
        "needs_tool": False,
        "hitl_triggered": False,
        "retrieved_chunks": [],
        "retrieved_sources": [],
        "policy_result": {},
        "mcp_tools_used": [],
        "final_answer": "",
        "sources": [],
        "confidence": 0.0,
        "history": [],
        "workers_called": [],
        "supervisor_route": "",
        "latency_ms": None,
        "run_id": f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "worker_io_logs": []
    }


# ─────────────────────────────────────────────
# 2. Supervisor Node — quyết định route
# ─────────────────────────────────────────────

def supervisor_node(state: AgentState) -> AgentState:
    """
    Supervisor phân tích task và quyết định:
    1. Route sang worker nào
    2. Có cần MCP tool không
    3. Có risk cao cần HITL không
    """
    task = state["task"].lower()
    state["history"].append(f"[supervisor] received task: {state['task'][:80]}")

    route = "retrieval_worker"         
    route_reason = "default route"    
    needs_tool = False
    risk_high = False

    policy_keywords = ["hoàn tiền", "refund", "flash sale", "license", "cấp quyền", "access", "level 3", "ticket", "p1"]
    risk_keywords = ["emergency", "khẩn cấp", "2am", "không rõ", "err-"]

    if any(kw in task for kw in policy_keywords):
        route = "policy_tool_worker"
        route_reason = "task chứa keyword liên quan policy/quyền truy cập/ticket"
        needs_tool = True

    if any(kw in task for kw in risk_keywords):
        risk_high = True
        route_reason += " | bật cờ risk_high"

    # Human review override
    if risk_high and "err-" in task:
        route = "human_review"
        route_reason = "mã lỗi lạ + risk_high -> dừng lại cần human review"

    state["supervisor_route"] = route
    state["route_reason"] = route_reason
    state["needs_tool"] = needs_tool
    state["risk_high"] = risk_high
    state["history"].append(f"[supervisor] route={route} reason={route_reason}")

    return state


# ─────────────────────────────────────────────
# 3. Route Decision — conditional edge
# ─────────────────────────────────────────────

def route_decision(state: AgentState) -> Literal["retrieval_worker", "policy_tool_worker", "human_review"]:
    """
    Trả về tên worker tiếp theo dựa vào supervisor_route trong state.
    Đây là conditional edge của graph.
    """
    route = state.get("supervisor_route", "retrieval_worker")
    return route  # type: ignore


# ─────────────────────────────────────────────
# 4. Human Review Node — HITL placeholder
# ─────────────────────────────────────────────

def human_review_node(state: AgentState) -> AgentState:
    """
    HITL node: pause và chờ human approval.
    """
    state["hitl_triggered"] = True
    state["history"].append("[human_review] HITL triggered — awaiting human input")
    state["workers_called"].append("human_review")

    # Placeholder: tự động approve để pipeline tiếp tục
    print(f"\n⚠️  HITL TRIGGERED")
    print(f"   Task: {state['task']}")
    print(f"   Reason: {state['route_reason']}")
    print(f"   Action: Auto-approving in lab mode (set hitl_triggered=True)\n")

    # Sau khi human approve, route về retrieval để lấy evidence
    state["supervisor_route"] = "retrieval_worker"
    state["route_reason"] += " | human approved → retrieval"

    return state


# ─────────────────────────────────────────────
# 5. Worker Nodes (Gọi logic thực tế)
# ─────────────────────────────────────────────

def retrieval_worker_node(state: AgentState) -> AgentState:
    """Wrapper gọi retrieval worker thực tế."""
    state["workers_called"].append("retrieval_worker")
    state["history"].append("[retrieval_worker] called")
    return retrieval_run(state)


def policy_tool_worker_node(state: AgentState) -> AgentState:
    """Wrapper gọi policy/tool worker thực tế."""
    # Worker này tự append vào workers_called bên trong code của nó, 
    # nhưng gọi trực tiếp qua run() là đủ
    return policy_tool_run(state)


def synthesis_worker_node(state: AgentState) -> AgentState:
    """Wrapper gọi synthesis worker thực tế."""
    return synthesis_run(state)


# ─────────────────────────────────────────────
# 6. Build Graph
# ─────────────────────────────────────────────

def build_graph():
    """
    Xây dựng graph với supervisor-worker pattern sử dụng LangGraph.
    """
    workflow = StateGraph(AgentState)

    # Đăng ký các Nodes
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("human_review", human_review_node)
    workflow.add_node("retrieval_worker", retrieval_worker_node)
    workflow.add_node("policy_tool_worker", policy_tool_worker_node)
    workflow.add_node("synthesis_worker", synthesis_worker_node)

    # Đặt điểm bắt đầu
    workflow.set_entry_point("supervisor")

    # Routing có điều kiện từ Supervisor
    workflow.add_conditional_edges(
        "supervisor",
        route_decision,
        {
            "human_review": "human_review",
            "policy_tool_worker": "policy_tool_worker",
            "retrieval_worker": "retrieval_worker"
        }
    )

    # Luồng xử lý tuần tự (Edges)
    workflow.add_edge("human_review", "retrieval_worker")
    
    # Định tuyến sau policy_tool_worker
    def policy_next_edge(state: AgentState):
        # Nếu chưa có chunk nào (MCP tool ko lấy được), phải quay về Retrieval thuần
        if not state.get("retrieved_chunks"):
            return "retrieval_worker"
        return "synthesis_worker"
        
    workflow.add_conditional_edges("policy_tool_worker", policy_next_edge)
    
    # Sau khi retrieval xong -> tổng hợp thành answer
    workflow.add_edge("retrieval_worker", "synthesis_worker")
    
    # Đóng graph
    workflow.add_edge("synthesis_worker", END)

    # Biên dịch đồ thị
    app = workflow.compile()

    def run(state: AgentState) -> AgentState:
        import time
        start = time.time()

        # Thực thi LangGraph
        final_state = app.invoke(state)

        final_state["latency_ms"] = int((time.time() - start) * 1000)
        final_state["history"].append(f"[graph] completed in {final_state['latency_ms']}ms")
        return final_state

    return run


# ─────────────────────────────────────────────
# 7. Public API
# ─────────────────────────────────────────────

_graph = build_graph()

def run_graph(task: str) -> AgentState:
    """
    Entry point: nhận câu hỏi, trả về AgentState với full trace.
    """
    state = make_initial_state(task)
    result = _graph(state)
    return result

def save_trace(state: AgentState, output_dir: str = "./artifacts/traces") -> str:
    """Lưu trace ra file JSON."""
    os.makedirs(output_dir, exist_ok=True)
    filename = f"{output_dir}/{state['run_id']}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    return filename


# ─────────────────────────────────────────────
# 8. Manual Test
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("Day 09 Lab — Supervisor-Worker Graph (FULL INTEGRATION)")
    print("=" * 60)
    
    print("⚠️  Đảm bảo bạn đã chạy MCP Server ở một terminal khác bằng lệnh:")
    print("   uvicorn mcp_server:app --port 8000\n")

    test_queries = [
        "SLA xử lý ticket P1 là bao lâu?",
        "Khách hàng Flash Sale yêu cầu hoàn tiền vì sản phẩm lỗi — được không?",
        "Ai phê duyệt cấp quyền Level 3?"
    ]

    for query in test_queries:
        print(f"\n▶ Query: {query}")
        result = run_graph(query)
        print(f"  Route   : {result['supervisor_route']}")
        print(f"  Reason  : {result['route_reason']}")
        print(f"  Workers : {result['workers_called']}")
        
        policy = result.get('policy_result', {})
        if policy and policy.get('exceptions_found'):
            print(f"  ⚠️ Policy Exceptions: {policy['exceptions_found'][0].get('type')}")
            
        mcp_tools = result.get('mcp_tools_used', [])
        if mcp_tools:
            print(f"  🛠️ MCP Tools Dùng: {len(mcp_tools)}")
            for t in mcp_tools:
                tool_name = t.get('tool', 'unknown_tool')
                tool_output = str(t.get('output', ''))[:80].replace('\n', ' ')
                print(f"      - Gọi [{tool_name}] -> Kết quả: {tool_output}...")
        else:
            print("  🛠️ MCP Tools Dùng: 0")
        # -----------------------------------------

        print(f"  Answer  : {result['final_answer']}")
        print(f"  Confidence: {result['confidence']}")
        print(f"  Latency : {result['latency_ms']}ms")

        # Lưu trace
        trace_file = save_trace(result)
        print(f"  Trace saved → {trace_file}")
    print("\n✅ graph.py test complete. Hệ thống đã liên thông hoàn toàn!")