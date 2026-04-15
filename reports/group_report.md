# Báo Cáo Nhóm — Lab Day 10: Data Pipeline & Data Observability

**Tên nhóm:** ___________  
**Thành viên:**
| Tên | Vai trò (Day 10) | Email |
|-----|------------------|-------|
| ___ | Ingestion / Raw Owner | ___ |
| ___ | Cleaning & Quality Owner | ___ |
| ___ | Embed & Idempotency Owner | ___ |
| ___ | Monitoring / Docs Owner | ___ |

**Ngày nộp:** 2026-04-15  
**Repo:** selffullfilling-prophecy/Nhom08-402-Day10 (branch: hung/feat/etl)  
**Độ dài khuyến nghị:** 600–1000 từ

---

> **Nộp tại:** `reports/group_report.md`  
> **Deadline commit:** xem `SCORING.md` (code/trace sớm; report có thể muộn hơn nếu được phép).  
> Phải có **run_id**, **đường dẫn artifact**, và **bằng chứng before/after** (CSV eval hoặc screenshot).

---

## 1. Pipeline tổng quan (150–200 từ)

> Nguồn raw là gì (CSV mẫu / export thật)? Chuỗi lệnh chạy end-to-end? `run_id` lấy ở đâu trong log?

**Tóm tắt luồng:**

Raw export duoc doc tu data/raw/policy_export_dirty.csv. ETL sinh run_id va log cac chi so raw_records, cleaned_records, quarantine_records. Sau do cleaning rules chuan hoa ngay, quarantine record loi, va ap stale-refund fix (7 ngay) o run chuan. Expectation suite phan tach halt/warn de chan publish khi gap loi nghiem trong, nhung van cho phep demo inject qua flag --skip-validate. Ngoai expectation custom, nhom them pydantic schema gate that su de validate tung cleaned row truoc embed. Lop embed publish cleaned snapshot vao Chroma collection day10_kb theo co che upsert chunk_id va prune id cu de dam bao idempotent. Moi run sinh manifest trong artifacts/manifests de truy vet lineage, va freshness monitor theo 2 boundary ingest/publish.

**Lệnh chạy một dòng (copy từ README thực tế của nhóm):**

python etl_pipeline.py run && python eval_retrieval.py --out artifacts/eval/before_after_eval.csv

---

## 2. Cleaning & expectation (150–200 từ)

> Baseline đã có nhiều rule (allowlist, ngày ISO, HR stale, refund, dedupe…). Nhóm thêm **≥3 rule mới** + **≥2 expectation mới**. Khai báo expectation nào **halt**.

### 2a. Bảng metric_impact (bắt buộc — chống trivial)

| Rule / Expectation mới (tên ngắn) | Trước (số liệu) | Sau / khi inject (số liệu) | Chứng cứ (log / CSV / commit) |
|-----------------------------------|------------------|-----------------------------|-------------------------------|
| invalid_source_chunk_id + duplicate_source_chunk_id | Khong track rieng | Quarantine tang khi co source id loi/trung | transform/cleaning_rules.py + cot reason trong quarantine CSV |
| invalid_exported_at_format | Khong track rieng | Quarantine khi exported_at sai format | transform/cleaning_rules.py |
| stale_refund_migration_marker | bonus-inject cleaned_records=7, quarantine=4 | bonus-clean-final cleaned_records=6, quarantine=5 | manifest_bonus-inject-2026-04-15T05-45Z.json vs manifest_bonus-clean-final-2026-04-15T05-50Z.json |
| chunk_id_unique (halt) | baseline chua co | duplicate_chunk_id_count=0 o ca 2 run | run_bonus-inject-2026-04-15T05-45Z.log + run_bonus-clean-final-2026-04-15T05-50Z.log |
| exported_at_iso_timestamp (warn) | baseline chua co | invalid_exported_at_rows=0 | expectation log run chuan |
| pydantic_cleaned_schema_valid (halt) | chua co trong baseline | validated_rows=7 (inject), validated_rows=6 (clean), error_count=0 | run_bonus-inject-2026-04-15T05-45Z.log + run_bonus-clean-final-2026-04-15T05-50Z.log |

**Rule chính (baseline + mở rộng):**

- Baseline: allowlist doc_id, normalize effective_date, quarantine stale HR policy, dedupe chunk text, stale refund 14->7 fix.
- Mo rong: validate source chunk_id, validate exported_at format, quarantine stale migration marker policy-v3.
- Expectation mo rong: chunk_id_unique (halt), exported_at_iso_timestamp (warn), pydantic_cleaned_schema_valid (halt).

**Ví dụ 1 lần expectation fail (nếu có) và cách xử lý:**

Run bonus-inject-2026-04-15T05-45Z co expectation[refund_no_stale_14d_window] FAIL (violations=2) do tat refund fix. Trong sprint 3 day la co chu dich va duoc tiep tuc bang --skip-validate de thu hoi bang chung retrieval xau. Sau do rerun chuan bonus-clean-final-2026-04-15T05-50Z de expectation nay tro lai OK truoc khi publish.

---

## 3. Before / after ảnh hưởng retrieval hoặc agent (200–250 từ)

> Bắt buộc: inject corruption (Sprint 3) — mô tả + dẫn `artifacts/eval/…` hoặc log.

**Kịch bản inject:**

Lenh inject: python etl_pipeline.py run --run-id bonus-inject-2026-04-15T05-45Z --no-refund-fix --skip-validate

Muc tieu: dua chunk stale "14 ngay lam viec" vao index de chung minh retrieval bi anh huong khi bo qua data quality gate.

**Kết quả định lượng (từ CSV / bảng):**

- artifacts/eval/bonus_inject_eval.csv: q_refund_window co hits_forbidden=yes.
- artifacts/eval/bonus_clean_final_eval.csv: q_refund_window tro lai hits_forbidden=no.
- q_leave_version giu on dinh: contains_expected=yes, hits_forbidden=no, top1_doc_expected=yes.

---

## 4. Freshness & monitoring (100–150 từ)

> SLA bạn chọn, ý nghĩa PASS/WARN/FAIL trên manifest mẫu.

Nhom tach freshness thanh 2 boundary: ingest (SLA 24h) va publish (SLA 2h). Voi run bonus-clean-final-2026-04-15T05-50Z, ingest boundary FAIL vi latest_exported_at=2026-04-10T08:00:00 da cu hon SLA, nhung publish boundary PASS vi run_timestamp vua tao. Dien giai: ingest FAIL canh bao do cu cua snapshot nguon; publish PASS xac nhan pipeline vua publish thanh cong. Cach do nay giam false positive va cung cap observability ro hon cho van hanh.

---

## 5. Liên hệ Day 09 (50–100 từ)

> Dữ liệu sau embed có phục vụ lại multi-agent Day 09 không? Nếu có, mô tả tích hợp; nếu không, giải thích vì sao tách collection.

Co. Day 10 publish snapshot vao Chroma collection day10_kb, Day 09 retrieval co the tro collection nay de su dung context da qua clean/validate. Neu can test song song voi index cu thi doi CHROMA_COLLECTION de tach moi truong thu nghiem.

---

## 6. Rủi ro còn lại & việc chưa làm

- Bộ eval/grading (đã thực hiện và đạt kết quả tốt qua `grading_run.jsonl`): Pipeline xử lý đúng theo thiết kế và truy xuất chính xác nội dung với cả 3 câu hỏi đánh giá theo chuẩn `gq_d10_01` (7 ngày hoàn), `gq_d10_02` (SLA P1 4 giờ), `gq_d10_03` (12 ngày nghỉ phép theo tài liệu 2026).
 - Hạn chế: Chưa có thêm nhiều bộ dataset test (eval data slice) mở rộng từ 5 câu trở lên để xem xét sự ổn định cho các trường hợp biên để thêm bằng chứng Distinction (c).
 - Việc cần làm tiếp theo: Hoàn tất report cá nhân cho từng thành viên.
 - Rủi ro Data drift: Trong thời gian tới nếu format schema từ HR bị update thì pydantic model cũng cần theo dõi để mở rộng rule.
