"""
mcp_tools.py - Tool implementations and mock data for the MCP server.
"""

from workers.retrieval import retrieve_hybrid


MOCK_TICKETS = {
    "P1-LATEST": {
        "ticket_id": "IT-9847",
        "priority": "P1",
        "title": "API Gateway down - toan bo nguoi dung khong dang nhap duoc",
        "status": "in_progress",
        "assignee": "nguyen.van.a@company.internal",
        "created_at": "2026-04-13T22:47:00",
        "sla_deadline": "2026-04-14T02:47:00",
        "escalated": True,
        "notifications_sent": ["slack:#incident-p1", "pagerduty:oncall"],
    },
    "IT-1234": {
        "ticket_id": "IT-1234",
        "priority": "P2",
        "title": "Feature login cham cho mot so user",
        "status": "open",
        "assignee": None,
        "created_at": "2026-04-13T09:15:00",
    },
}


ACCESS_RULES = {
    1: {"required_approvers": ["Line Manager"], "emergency_can_bypass": False},
    2: {"required_approvers": ["Line Manager", "IT Admin"], "emergency_can_bypass": True},
    3: {"required_approvers": ["Line Manager", "IT Admin", "IT Security"], "emergency_can_bypass": False},
}


def tool_search_kb(query: str, top_k: int = 3) -> dict:
    """Search the vector database via the retrieval worker."""
    print(f"  [MCP Tools] Running 'search_kb' with query: '{query}'")
    try:
        chunks = retrieve_hybrid(query, top_k=top_k)
        sources = list({chunk.get("source", "unknown") for chunk in chunks})
        print(f"  [MCP Tools] -> Found {len(chunks)} chunks.")
        return {
            "chunks": chunks,
            "sources": sources,
            "total_found": len(chunks),
        }
    except Exception as exc:
        print(f"  [MCP Tools] search_kb error: {exc}")
        return {
            "chunks": [],
            "sources": [],
            "total_found": 0,
            "error": str(exc),
        }


def tool_get_ticket_info(ticket_id: str) -> dict:
    """Return ticket information from the mock incident system."""
    print(f"  [MCP Tools] Running 'get_ticket_info' for id: {ticket_id}")
    ticket = MOCK_TICKETS.get(ticket_id.upper())
    if ticket:
        return ticket
    return {"error": f"Ticket '{ticket_id}' khong tim thay."}


def tool_check_access_permission(access_level: int, requester_role: str, is_emergency: bool = False) -> dict:
    """Check access approval rules from the mock Access Control SOP."""
    print(
        f"  [MCP Tools] Running 'check_access_permission' "
        f"(level={access_level}, emergency={is_emergency}, role={requester_role})"
    )
    rule = ACCESS_RULES.get(access_level)
    if not rule:
        return {"error": f"Access level {access_level} khong hop le."}

    notes = []
    if is_emergency and rule.get("emergency_can_bypass"):
        notes.append("Duoc phep bo qua quy trinh duyet vi ly do khan cap.")
    elif is_emergency and not rule.get("emergency_can_bypass"):
        notes.append(
            f"CANH BAO: Level {access_level} KHONG cho phep bo qua quy trinh duyet du khan cap."
        )

    return {
        "access_level": access_level,
        "can_grant": True,
        "required_approvers": rule["required_approvers"],
        "emergency_override": is_emergency and rule.get("emergency_can_bypass", False),
        "notes": notes,
    }


def tool_create_ticket(priority: str, title: str, description: str = "") -> dict:
    """Create a mock ticket and return a fake URL."""
    mock_id = f"IT-{9900 + hash(title) % 99}"
    print(f"  [MCP Tools] Running 'create_ticket': {mock_id} ({priority})")
    return {
        "ticket_id": mock_id,
        "priority": priority,
        "status": "open",
        "url": f"https://jira.company.internal/browse/{mock_id}",
        "description": description,
    }
