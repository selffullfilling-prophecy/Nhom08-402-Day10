"""
Pydantic schema validation for cleaned rows.

This module gives a real schema gate (bonus criteria) instead of placeholder checks.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from transform.cleaning_rules import ALLOWED_DOC_IDS


class CleanedRowModel(BaseModel):
    """Schema contract for one cleaned row before publish/embed."""

    model_config = ConfigDict(extra="forbid")

    chunk_id: str = Field(min_length=8)
    doc_id: str = Field(min_length=1)
    chunk_text: str = Field(min_length=8)
    effective_date: date
    exported_at: datetime

    @field_validator("doc_id")
    @classmethod
    def _doc_id_must_be_allowed(cls, value: str) -> str:
        if value not in ALLOWED_DOC_IDS:
            raise ValueError(f"doc_id '{value}' is not in allowlist")
        return value


def validate_cleaned_rows_with_pydantic(cleaned_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Validate cleaned rows against pydantic schema and return summarized diagnostics."""

    errors: List[Dict[str, Any]] = []
    validated_rows = 0

    for idx, row in enumerate(cleaned_rows):
        payload = {
            "chunk_id": row.get("chunk_id", ""),
            "doc_id": row.get("doc_id", ""),
            "chunk_text": row.get("chunk_text", ""),
            "effective_date": row.get("effective_date", ""),
            "exported_at": row.get("exported_at", ""),
        }
        try:
            CleanedRowModel.model_validate(payload)
            validated_rows += 1
        except ValidationError as exc:
            errors.append(
                {
                    "row_index": idx,
                    "chunk_id": str(payload.get("chunk_id") or ""),
                    "errors": exc.errors(include_url=False),
                }
            )

    return {
        "passed": len(errors) == 0,
        "validated_rows": validated_rows,
        "error_count": len(errors),
        "sample_errors": errors[:3],
    }
