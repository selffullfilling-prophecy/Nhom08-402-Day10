"""
Cleaning rules — raw export → cleaned rows + quarantine.

Baseline gồm các failure mode mở rộng (allowlist doc_id, parse ngày, HR stale version).
Sinh viên thêm ≥3 rule mới: mỗi rule phải ghi `metric_impact` (xem README — chống trivial).
"""

from __future__ import annotations

import csv
import hashlib
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml

# Khớp export hợp lệ trong lab (mở rộng khi nhóm thêm doc mới — phải đồng bộ contract).
ALLOWED_DOC_IDS = frozenset(
    {
        "policy_refund_v4",
        "sla_p1_2026",
        "it_helpdesk_faq",
        "hr_leave_policy",
    }
)

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DMY_SLASH = re.compile(r"^(\d{2})/(\d{2})/(\d{4})$")
_ISO_TS = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$")

_ROOT = Path(__file__).resolve().parents[1]
_CONTRACT_PATH = _ROOT / "contracts" / "data_contract.yaml"
_DEFAULT_HR_LEAVE_MIN_EFFECTIVE_DATE = "2026-01-01"


def _load_hr_leave_cutoff_from_contract() -> str:
    if not _CONTRACT_PATH.is_file():
        return ""
    try:
        data = yaml.safe_load(_CONTRACT_PATH.read_text(encoding="utf-8")) or {}
    except Exception:
        return ""
    cutoff = (
        data.get("policy_versioning", {})
        .get("hr_leave_min_effective_date", "")
    )
    cutoff_str = str(cutoff).strip()
    if _ISO_DATE.match(cutoff_str):
        return cutoff_str
    return ""


def _resolve_hr_leave_cutoff() -> Tuple[str, str]:
    env_cutoff = os.environ.get("HR_LEAVE_MIN_EFFECTIVE_DATE", "").strip()
    if env_cutoff and _ISO_DATE.match(env_cutoff):
        return env_cutoff, "env"

    contract_cutoff = _load_hr_leave_cutoff_from_contract()
    if contract_cutoff:
        return contract_cutoff, "contract"

    return _DEFAULT_HR_LEAVE_MIN_EFFECTIVE_DATE, "default"


HR_LEAVE_MIN_EFFECTIVE_DATE, HR_LEAVE_CUTOFF_SOURCE = _resolve_hr_leave_cutoff()


def _norm_text(s: str) -> str:
    return " ".join((s or "").strip().split()).lower()


def _stable_chunk_id(doc_id: str, chunk_text: str, seq: int) -> str:
    h = hashlib.sha256(f"{doc_id}|{chunk_text}|{seq}".encode("utf-8")).hexdigest()[:16]
    return f"{doc_id}_{seq}_{h}"


def _normalize_effective_date(raw: str) -> Tuple[str, str]:
    """
    Trả về (iso_date, error_reason).
    iso_date rỗng nếu không parse được.
    """
    s = (raw or "").strip()
    if not s:
        return "", "empty_effective_date"
    if _ISO_DATE.match(s):
        return s, ""
    m = _DMY_SLASH.match(s)
    if m:
        dd, mm, yyyy = m.group(1), m.group(2), m.group(3)
        return f"{yyyy}-{mm}-{dd}", ""
    return "", "invalid_effective_date_format"


def load_raw_csv(path: Path) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append({k: (v or "").strip() for k, v in r.items()})
    return rows


def clean_rows(
    rows: List[Dict[str, str]],
    *,
    apply_refund_window_fix: bool = True,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    quarantine: List[Dict[str, Any]] = []
    seen_text: set[str] = set()
    cleaned: List[Dict[str, Any]] = []
    seen_source_chunk_ids: set[str] = set()
    seq = 0

    for raw in rows:
        source_chunk_id = (raw.get("chunk_id", "") or "").strip()
        doc_id = raw.get("doc_id", "")
        text = raw.get("chunk_text", "")
        eff_raw = raw.get("effective_date", "")
        exported_at = (raw.get("exported_at", "") or "").strip()

        if not source_chunk_id or not source_chunk_id.isdigit():
            quarantine.append({**raw, "reason": "invalid_source_chunk_id"})
            continue

        if source_chunk_id in seen_source_chunk_ids:
            quarantine.append({**raw, "reason": "duplicate_source_chunk_id"})
            continue
        seen_source_chunk_ids.add(source_chunk_id)

        if not _ISO_TS.match(exported_at):
            quarantine.append({**raw, "reason": "invalid_exported_at_format"})
            continue

        if doc_id not in ALLOWED_DOC_IDS:
            quarantine.append({**raw, "reason": "unknown_doc_id"})
            continue

        eff_norm, eff_err = _normalize_effective_date(eff_raw)
        if eff_err == "empty_effective_date":
            quarantine.append({**raw, "reason": "missing_effective_date"})
            continue
        if eff_err == "invalid_effective_date_format":
            quarantine.append({**raw, "reason": eff_err, "effective_date_raw": eff_raw})
            continue

        # Lọc HR bản cũ theo cutoff versioning (env > contract > default).
        if doc_id == "hr_leave_policy" and eff_norm < HR_LEAVE_MIN_EFFECTIVE_DATE:
            quarantine.append(
                {
                    **raw,
                    "reason": "stale_hr_policy_effective_date",
                    "effective_date_normalized": eff_norm,
                    "min_effective_date": HR_LEAVE_MIN_EFFECTIVE_DATE,
                    "cutoff_source": HR_LEAVE_CUTOFF_SOURCE,
                }
            )
            continue

        if not text:
            quarantine.append({**raw, "reason": "missing_chunk_text"})
            continue

        key = _norm_text(text)
        if key in seen_text:
            quarantine.append({**raw, "reason": "duplicate_chunk_text"})
            continue
        seen_text.add(key)

        fixed_text = text
        
        # --- ĐOẠN FIX LOGIC CHÍNH Ở ĐÂY ---
        if doc_id == "policy_refund_v4":
            # NẾU bật cờ sửa lỗi (Luồng chuẩn)
            if apply_refund_window_fix:
                if "14 ngày làm việc" in fixed_text:
                    fixed_text = fixed_text.replace(
                        "14 ngày làm việc",
                        "7 ngày làm việc",
                    )
                    fixed_text += " [cleaned: stale_refund_window]"
                
                # Chỉ lọc bỏ marker khi bật chế độ làm sạch
                if "policy-v3" in fixed_text or "lỗi migration" in fixed_text.lower():
                    quarantine.append({**raw, "reason": "stale_refund_migration_marker"})
                    continue

        seq += 1
        cleaned.append(
            {
                "chunk_id": _stable_chunk_id(doc_id, fixed_text, seq),
                "doc_id": doc_id,
                "chunk_text": fixed_text,
                "effective_date": eff_norm,
                "exported_at": exported_at or "",
            }
        )

    return cleaned, quarantine


def write_cleaned_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("chunk_id,doc_id,chunk_text,effective_date,exported_at\n", encoding="utf-8")
        return
    fieldnames = ["chunk_id", "doc_id", "chunk_text", "effective_date", "exported_at"]
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fieldnames})


def write_quarantine_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("chunk_id,doc_id,chunk_text,effective_date,exported_at,reason\n", encoding="utf-8")
        return
    keys: List[str] = []
    seen_k: set[str] = set()
    for r in rows:
        for k in r.keys():
            if k not in seen_k:
                seen_k.add(k)
                keys.append(k)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore", restval="")
        w.writeheader()
        for r in rows:
            w.writerow(r)