# Báo Cáo Nhóm — Lab Day 10: Data Pipeline & Data Observability

**Tên nhóm:** Nhóm 08 - 402 — Day10 Bonus Track  
**Thành viên:**
| Tên | Vai trò (Day 10) | Email |
|-----|------------------|-------|
| Nguyễn Hoàng Việt Hùng | System Upgrade Owner (Bonus Track) | nguyenhoangviethung@gmail.com |
| Hoàng Đức Hưng | Cleaning Owner | hoangduchung0311@gmail.com |
| Mai Viết Hoàng | Expectation Suite Maintainer |  hoangmai04222@gmail.com |
| Lê Hồng Anh | Monitoring Owner | anh.anhle2004@gmail.com |
| Nguyễn Thanh Bình | Grading & Tooling Owner | binhntph50046@gmail.com |
| Nguyễn Thị Hương Giang | Ingestion / Raw Owner | nguyenhuonggiang06092004@gmail.com |

**Ngày nộp:** 2026-04-15  
**Repo:** selffullfilling-prophecy/Nhom08-402-Day10  
**Độ dài khuyến nghị:** 600–1000 từ

---

> **Nộp tại:** `reports/group_report.md`  
> **Deadline commit:** xem `SCORING.md` (code/trace sớm; report có thể muộn hơn nếu được phép).  
> Phải có **run_id**, **đường dẫn artifact**, và **bằng chứng before/after** (CSV eval hoặc screenshot).

---

## 1. Pipeline tổng quan (150–200 từ)

> Nguồn raw là gì (CSV mẫu / export thật)? Chuỗi lệnh chạy end-to-end? `run_id` lấy ở đâu trong log?

**Tóm tắt luồng:**

Nguồn raw của nhóm là `data/raw/policy_export_dirty.csv`. Chuỗi xử lý end-to-end giữ kiến trúc ingest -> clean -> validate -> embed. `run_id` được sinh theo timestamp hoặc truyền tay qua `--run-id`, sau đó ghi vào log `artifacts/logs/run_<run-id>.log` và manifest `artifacts/manifests/manifest_<run-id>.json`.

Pipeline có 3 lớp chính: (1) cleaning + quarantine theo reason; (2) expectation suite có `halt/warn` và gate schema Pydantic; (3) embed idempotent vào Chroma (`upsert chunk_id` + prune id cũ). Nhánh bonus nâng freshness lên 2 boundary (ingest/publish) để tách lỗi upstream và lỗi publish. Evidence chính dùng 3 run: `bonus-clean-2026-04-15T05-40Z`, `bonus-inject-2026-04-15T05-45Z`, `bonus-clean-final-2026-04-15T05-50Z`.

**Lệnh chạy một dòng (copy từ README thực tế của nhóm):**

python etl_pipeline.py run && python eval_retrieval.py --out artifacts/eval/before_after_eval.csv

---

## 2. Cleaning & expectation (150–200 từ)

> Baseline đã có nhiều rule (allowlist, ngày ISO, HR stale, refund, dedupe…). Nhóm thêm **≥3 rule mới** + **≥2 expectation mới**. Khai báo expectation nào **halt**.

### 2a. Bảng metric_impact (bắt buộc — chống trivial)

| Rule / Expectation mới (tên ngắn) | Trước (số liệu) | Sau / khi inject (số liệu) | Chứng cứ (log / CSV / commit) |
|-----------------------------------|------------------|-----------------------------|-------------------------------|
| stale_refund_migration_marker (rule) | Chưa tách marker migration | Inject: `cleaned=7`, `quarantine=4`; Clean-final: `cleaned=6`, `quarantine=5` | `manifest_bonus-inject-2026-04-15T05-45Z.json` và `manifest_bonus-clean-final-2026-04-15T05-50Z.json` |
| hr_leave_cutoff_dynamic_from_contract_env (rule) | Dễ hard-code cutoff | Quarantine có `stale_hr_policy_effective_date`, `cutoff_source=contract` | `artifacts/quarantine/quarantine_hung-cleaning-report.csv` |
| exported_at_format_guard (rule) | Chưa có guard format exported_at | Run clean-final: `invalid_exported_at_rows=0` (không false positive) | `run_bonus-clean-final-2026-04-15T05-50Z.log` |
| chunk_id_unique (halt) | Chưa có gate idempotency-level | `duplicate_chunk_id_count=0` ở inject và clean-final | `run_bonus-inject-2026-04-15T05-45Z.log`, `run_bonus-clean-final-2026-04-15T05-50Z.log` |
| exported_at_iso_timestamp (warn) | Chưa có expectation timestamp | `invalid_exported_at_rows=0` | `run_bonus-clean-2026-04-15T05-40Z.log` |
| pydantic_cleaned_schema_valid (halt) | Chưa có schema gate thật | Inject: `validated_rows=7`; Clean-final: `validated_rows=6`; `error_count=0` | `run_bonus-inject-2026-04-15T05-45Z.log`, `run_bonus-clean-final-2026-04-15T05-50Z.log` |

**Rule chính (baseline + mở rộng):**

- Baseline: allowlist `doc_id`, normalize `effective_date`, quarantine dữ liệu thiếu, dedupe chunk text, fix refund 14 -> 7 ở run chuẩn.
- Mở rộng: quarantine marker migration cũ, cutoff HR động theo contract/env, guard timestamp.
- Expectation mới: `chunk_id_unique` (halt), `exported_at_iso_timestamp` (warn), `pydantic_cleaned_schema_valid` (halt).

**Ví dụ 1 lần expectation fail (nếu có) và cách xử lý:**

Ở run `bonus-inject-2026-04-15T05-45Z`, expectation `refund_no_stale_14d_window` fail với `violations=2` do cố tình tắt refund fix (`--no-refund-fix`) và bật `--skip-validate` để ghi nhận scenario xấu cho Sprint 3. Sau đó nhóm chạy lại run chuẩn `bonus-clean-final-2026-04-15T05-50Z`, expectation này trở về `OK (violations=0)` trước khi chốt evidence.

---

## 3. Before / after ảnh hưởng retrieval hoặc agent (200–250 từ)

> Bắt buộc: inject corruption (Sprint 3) — mô tả + dẫn `artifacts/eval/…` hoặc log.

**Kịch bản inject:**

Lệnh inject: `python etl_pipeline.py run --run-id bonus-inject-2026-04-15T05-45Z --no-refund-fix --skip-validate`

Mục tiêu của kịch bản này là cố ý cho dữ liệu stale (refund 14 ngày) đi qua publish để đo suy giảm retrieval khi bypass quality gate.

**Kết quả định lượng (từ CSV / bảng):**

- `artifacts/eval/bonus_inject_eval.csv`: câu `q_refund_window` có `hits_forbidden=yes`, top preview chứa cụm stale `14 ngày làm việc`.
- `artifacts/eval/bonus_clean_final_eval.csv`: cùng câu `q_refund_window` chuyển về `hits_forbidden=no`, preview đã là `7 ngày làm việc`.
- Các câu còn lại giữ ổn định: `q_p1_sla`, `q_lockout`, `q_leave_version` đều đúng kỳ vọng; riêng `q_leave_version` có `top1_doc_expected=yes`.
- Grading chuẩn `artifacts/eval/grading_run.jsonl` có đủ 3 dòng `gq_d10_01..03`; cả 3 câu `contains_expected=true`, và `gq_d10_03` có `top1_doc_matches=true`.

---

## 4. Freshness & monitoring (100–150 từ)

> SLA bạn chọn, ý nghĩa PASS/WARN/FAIL trên manifest mẫu.

Nhóm dùng freshness 2 boundary với SLA tách riêng: ingest = 24h, publish = 2h. Ở run `bonus-clean-final-2026-04-15T05-50Z`, manifest ghi ingest `FAIL` (age `121.847h` > `24h`) nhưng publish `PASS` (age `0.0h` <= `2h`). Kết luận: nguồn cũ nhưng pipeline publish đúng hạn.

Nhóm cũng bổ sung parse timestamp an toàn để tránh crash khi manifest thiếu/sai định dạng thời gian; thay vào đó trả về trạng thái có diễn giải (`WARN/FAIL`) kèm lý do.

---

## 5. Liên hệ Day 09 (50–100 từ)

> Dữ liệu sau embed có phục vụ lại multi-agent Day 09 không? Nếu có, mô tả tích hợp; nếu không, giải thích vì sao tách collection.

Có. Day 10 publish snapshot đã clean/validate vào collection `day10_kb`, nên stack retrieval từ Day 09 có thể reuse trực tiếp bằng cách trỏ đúng `CHROMA_COLLECTION`. Trong trường hợp cần A/B test với index cũ, nhóm giữ khả năng tách collection theo biến môi trường để chạy song song mà không làm nhiễu kết quả demo.

---

## 6. Rủi ro còn lại & việc chưa làm

- Grading đã pass đủ 3 câu trong `artifacts/eval/grading_run.jsonl`; cần rerun sau mỗi lần đổi rule clean để tránh regression.
- Rủi ro lớn nhất hiện tại là ingest stale (nhiều run liên tiếp FAIL ở ingest boundary).
- Bộ eval còn nhỏ; chưa có slice mở rộng >= 5 câu theo từng nhóm lỗi để tăng độ tin cậy Distinction nhánh (c).
