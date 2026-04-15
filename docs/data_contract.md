# Data contract — Lab Day 10

> Bắt đầu từ `contracts/data_contract.yaml` — mở rộng và đồng bộ file này.

---

## 1. Nguồn dữ liệu (source map)

| Nguồn | Phương thức ingest | Failure mode chính | Metric / alert |
|-------|-------------------|-------------------|----------------|
| data/raw/policy_export_dirty.csv | CSV file được đọc bởi etl_pipeline.py | duplicate chunk, stale refund text, stale HR version, unknown doc_id, missing date/text | raw_records, cleaned_records, quarantine_records, expectation[*], freshness_check |
| data/docs/*.txt (canonical policy docs) | Canonical mapping trong contracts/data_contract.yaml | source drift vs export snapshot, out-of-date policy window | must_not_contain hit trong eval, hits_forbidden flag trong artifacts/eval/*.csv |

Freshness được theo dõi qua 2 ranh giới (boundary):
* **ingest boundary:** `latest_exported_at` so với `FRESHNESS_SLA_INGEST_HOURS`.
* **publish boundary:** `run_timestamp` so với `FRESHNESS_SLA_PUBLISH_HOURS`.

---

## 2. Schema cleaned (Sơ đồ dữ liệu sạch)

| Cột | Kiểu | Bắt buộc | Ghi chú |
|-----|------|----------|---------|
| chunk_id | string | Có | ID ổn định được tạo sau khi làm sạch, dùng cho idempotent upsert/prune |
| doc_id | string | Có | Phải thuộc danh sách allowed_doc_ids |
| chunk_text | string | Có | Độ dài tối thiểu 8, đã loại bỏ stale refund text nếu chế độ fix được bật |
| effective_date | date | Có | Chuẩn hóa về định dạng YYYY-MM-DD |
| exported_at | datetime | Có | Định dạng kỳ vọng YYYY-MM-DDTHH:MM:SS |

---

## 3. Quy tắc quarantine vs drop (Kiểm soát bản ghi lỗi)

> Record bị flag đi đâu? Ai approve merge lại?

* Bản ghi vi phạm quy tắc làm sạch (cleaning rule) được đưa vào `artifacts/quarantine/quarantine_<run_id>.csv`, **không** nạp (embed) vào Chroma.
* Bản ghi hợp lệ được đưa vào `artifacts/cleaned/cleaned_<run_id>.csv` và cập nhật (upsert) lên collection `day10_kb`.
* Team owner (**Nhóm08-402**) kiểm tra các lý do bị cách ly theo cột `reason`; chỉ gộp (merge) lại sau khi sửa nguồn dữ liệu thô (raw) và chạy lại (rerun) pipeline.

---

## 4. Phiên bản & canonical (Nguồn sự thật)

> Source of truth cho policy refund: file nào / version nào?

* **Canonical refund policy:** `data/docs/policy_refund_v4.txt` (thời hạn 7 ngày làm việc).
* **Canonical HR leave policy:** `data/docs/hr_leave_policy.txt` (quy định năm 2026: 12 ngày cho thâm niên < 3 năm).
* **Phiên bản HR:** Không ghi cứng (hard-code) trong mã nguồn; ưu tiên biến môi trường `HR_LEAVE_MIN_EFFECTIVE_DATE`, nếu không có sẽ dùng giá trị mặc định từ hợp đồng `policy_versioning.hr_leave_min_effective_date`.