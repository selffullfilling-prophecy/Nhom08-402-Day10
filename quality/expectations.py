"""
Expectation suite đơn giản (không bắt buộc Great Expectations).

Sinh viên có thể thay bằng GE / pydantic / custom — miễn là có halt có kiểm soát.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from quality.schema_validation import validate_cleaned_rows_with_pydantic


@dataclass
class ExpectationResult:
    name: str
    passed: bool
    severity: str  # "warn" | "halt"
    detail: str


def run_expectations(cleaned_rows: List[Dict[str, Any]]) -> Tuple[List[ExpectationResult], bool]:
    """
    Trả về (results, should_halt).

    should_halt = True nếu có bất kỳ expectation severity halt nào fail.
    """
    results: List[ExpectationResult] = []

    # E1: có ít nhất 1 dòng sau clean
    ok = len(cleaned_rows) >= 1
    results.append(
        ExpectationResult(
            "min_one_row",
            ok,
            "halt",
            f"cleaned_rows={len(cleaned_rows)}",
        )
    )

    # E2: không doc_id rỗng
    bad_doc = [r for r in cleaned_rows if not (r.get("doc_id") or "").strip()]
    ok2 = len(bad_doc) == 0
    results.append(
        ExpectationResult(
            "no_empty_doc_id",
            ok2,
            "halt",
            f"empty_doc_id_count={len(bad_doc)}",
        )
    )

    # E3: policy refund không được chứa cửa sổ sai 14 ngày (sau khi đã fix)
    bad_refund = [
        r
        for r in cleaned_rows
        if r.get("doc_id") == "policy_refund_v4"
        and "14 ngày làm việc" in (r.get("chunk_text") or "")
    ]
    ok3 = len(bad_refund) == 0
    results.append(
        ExpectationResult(
            "refund_no_stale_14d_window",
            ok3,
            "halt",
            f"violations={len(bad_refund)}",
        )
    )

    # E4: chunk_text đủ dài
    short = [r for r in cleaned_rows if len((r.get("chunk_text") or "")) < 8]
    ok4 = len(short) == 0
    results.append(
        ExpectationResult(
            "chunk_min_length_8",
            ok4,
            "warn",
            f"short_chunks={len(short)}",
        )
    )

    # E5: effective_date đúng định dạng ISO sau clean (phát hiện parser lỏng)
    iso_bad = [
        r
        for r in cleaned_rows
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", (r.get("effective_date") or "").strip())
    ]
    ok5 = len(iso_bad) == 0
    results.append(
        ExpectationResult(
            "effective_date_iso_yyyy_mm_dd",
            ok5,
            "halt",
            f"non_iso_rows={len(iso_bad)}",
        )
    )

    # E6: không còn marker phép năm cũ 10 ngày trên doc HR (conflict version sau clean)
    bad_hr_annual = [
        r
        for r in cleaned_rows
        if r.get("doc_id") == "hr_leave_policy"
        and "10 ngày phép năm" in (r.get("chunk_text") or "")
    ]
    ok6 = len(bad_hr_annual) == 0
    results.append(
        ExpectationResult(
            "hr_leave_no_stale_10d_annual",
            ok6,
            "halt",
            f"violations={len(bad_hr_annual)}",
        )
    )

    # E7: chunk_id phải unique để đảm bảo upsert idempotent không bị đè sai.
    chunk_ids = [(r.get("chunk_id") or "").strip() for r in cleaned_rows]
    dup_count = len(chunk_ids) - len(set(chunk_ids))
    ok7 = dup_count == 0
    results.append(
        ExpectationResult(
            "chunk_id_unique",
            ok7,
            "halt",
            f"duplicate_chunk_id_count={dup_count}",
        )
    )

    # E8: exported_at sau clean phải đúng ISO timestamp cơ bản yyyy-mm-ddTHH:MM:SS.
    ts_bad = [
        r
        for r in cleaned_rows
        if not re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$", (r.get("exported_at") or "").strip())
    ]
    ok8 = len(ts_bad) == 0
    results.append(
        ExpectationResult(
            "exported_at_iso_timestamp",
            ok8,
            "warn",
            f"invalid_exported_at_rows={len(ts_bad)}",
        )
    )

    # E9: pydantic schema validation (bonus): enforce cleaned schema with strict contract checks.
    schema_result = validate_cleaned_rows_with_pydantic(cleaned_rows)
    schema_detail = (
        f"validated_rows={schema_result['validated_rows']} "
        f"error_count={schema_result['error_count']}"
    )
    if schema_result["sample_errors"]:
        first = schema_result["sample_errors"][0]
        schema_detail += f" first_error_row={first.get('row_index')}"
    results.append(
        ExpectationResult(
            "pydantic_cleaned_schema_valid",
            bool(schema_result["passed"]),
            "halt",
            schema_detail,
        )
    )

    halt = any(not r.passed and r.severity == "halt" for r in results)
    return results, halt
