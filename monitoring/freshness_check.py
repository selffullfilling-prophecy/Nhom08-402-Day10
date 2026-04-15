"""
Kiểm tra freshness từ manifest pipeline (SLA đơn giản theo giờ).

Sinh viên mở rộng: đọc watermark DB, so sánh với clock batch, v.v.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Tuple


def parse_iso(ts: str) -> datetime | None:
    if not ts:
        return None
    try:
        # Cho phép "2026-04-10T08:00:00" không có timezone
        if ts.endswith("Z"):
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def _evaluate_boundary(
    *,
    boundary: str,
    timestamp_raw: str,
    sla_hours: float,
    now: datetime,
) -> Dict[str, Any]:
    dt = parse_iso(timestamp_raw)
    if dt is None:
        return {
            "status": "WARN",
            "detail": {
                "reason": f"{boundary}_timestamp_missing_or_invalid",
                "timestamp": timestamp_raw,
                "sla_hours": sla_hours,
            },
        }

    age_hours = (now - dt).total_seconds() / 3600.0
    detail = {
        "timestamp": timestamp_raw,
        "age_hours": round(age_hours, 3),
        "sla_hours": sla_hours,
    }
    if age_hours <= sla_hours:
        return {"status": "PASS", "detail": detail}
    return {"status": "FAIL", "detail": {**detail, "reason": "freshness_sla_exceeded"}}


def check_manifest_freshness_boundaries(
    manifest_path: Path,
    *,
    ingest_sla_hours: float = 24.0,
    publish_sla_hours: float = 2.0,
    now: datetime | None = None,
) -> Dict[str, Any]:
    """Check freshness across two boundaries: ingest timestamp and publish timestamp."""
    now = now or datetime.now(timezone.utc)

    if not manifest_path.is_file():
        missing = {
            "status": "FAIL",
            "detail": {"reason": "manifest_missing", "path": str(manifest_path)},
        }
        return {
            "overall_status": "FAIL",
            "ingest": missing,
            "publish": missing,
        }

    data: Dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
    ingest_ts = str(data.get("latest_exported_at") or "")
    publish_ts = str(data.get("run_timestamp") or "")

    ingest = _evaluate_boundary(
        boundary="ingest",
        timestamp_raw=ingest_ts,
        sla_hours=ingest_sla_hours,
        now=now,
    )
    publish = _evaluate_boundary(
        boundary="publish",
        timestamp_raw=publish_ts,
        sla_hours=publish_sla_hours,
        now=now,
    )

    statuses = {ingest["status"], publish["status"]}
    if "FAIL" in statuses:
        overall_status = "FAIL"
    elif "WARN" in statuses:
        overall_status = "WARN"
    else:
        overall_status = "PASS"

    return {
        "run_id": data.get("run_id", ""),
        "overall_status": overall_status,
        "ingest": ingest,
        "publish": publish,
    }


def check_manifest_freshness(
    manifest_path: Path,
    *,
    sla_hours: float = 24.0,
    now: datetime | None = None,
) -> Tuple[str, Dict[str, Any]]:
    """
    Trả về ("PASS" | "WARN" | "FAIL", detail dict).

    Đọc trường `latest_exported_at` hoặc max exported_at trong cleaned summary.
    """
    summary = check_manifest_freshness_boundaries(
        manifest_path,
        ingest_sla_hours=sla_hours,
        publish_sla_hours=sla_hours,
        now=now,
    )
    ingest = summary["ingest"]
    return str(ingest["status"]), dict(ingest["detail"])
