# Quality report — Lab Day 10 (nhom)

**run_id inject (du lieu xau):** bonus-inject-2026-04-15T05-45Z  
**run_id clean overwrite:** bonus-clean-final-2026-04-15T05-50Z  
**Ngay:** 2026-04-15

---

## 1. Tom tat so lieu

| Chi so | Truoc (inject) | Sau (run chuan) | Ghi chu |
|--------|------------------|------------------|---------|
| raw_records | 11 | 11 | Cung mot file raw |
| cleaned_records | 7 | 6 | Run inject giu stale refund, run chuan da loai chunk stale |
| quarantine_records | 4 | 5 | Tang 1 do ap stale_refund_migration_marker |
| Expectation halt? | Co (refund_no_stale_14d_window fail, nhung skip-validate) | Khong | Run chuan pass toan bo halt checks |
| Pydantic schema gate | PASS (validated_rows=7, error_count=0) | PASS (validated_rows=6, error_count=0) | Bonus +2 |

Nguon doi chieu:
- artifacts/manifests/manifest_bonus-inject-2026-04-15T05-45Z.json
- artifacts/manifests/manifest_bonus-clean-final-2026-04-15T05-50Z.json
- artifacts/logs/run_bonus-inject-2026-04-15T05-45Z.log
- artifacts/logs/run_bonus-clean-final-2026-04-15T05-50Z.log

---

## 2. Before / after retrieval (bat buoc)

Tep ket qua:
- artifacts/eval/bonus_inject_eval.csv
- artifacts/eval/bonus_clean_final_eval.csv

**Cau hoi then chot:** q_refund_window

**Truoc (inject):**
- top1_doc_id = policy_refund_v4
- top1_preview: "14 ngay lam viec ... policy-v3"
- contains_expected = yes, hits_forbidden = yes

**Sau (run chuan):**
- top1_doc_id = policy_refund_v4
- top1_preview: "7 ngay lam viec ... [cleaned: stale_refund_window]"
- contains_expected = yes, hits_forbidden = no

Ket luan: inject xau lam retrieval dinh chunk stale (14 ngay), sau clean overwrite thi context forbidden bien mat.

**Merit check:** q_leave_version

**Truoc:** contains_expected = yes, hits_forbidden = no, top1_doc_expected = yes  
**Sau:** contains_expected = yes, hits_forbidden = no, top1_doc_expected = yes

Ket luan: policy HR 2026 (12 ngay) duoc giu on dinh, khong bi regression version.

---

## 3. Freshness & monitor (2 boundary)

Boundary logs (tu run clean):
- freshness_ingest_check = FAIL (timestamp 2026-04-10T08:00:00, age_hours=121.847, sla=24)
- freshness_publish_check = PASS (timestamp run_timestamp, age_hours=0.0, sla=2)
- freshness_check overall = FAIL (ingest FAIL + publish PASS)

Y nghia:
- Ingest FAIL canh bao nguon raw snapshot cu.
- Publish PASS cho thay pipeline run vua hoan tat va publish boundary con moi.

Muc nay la bang chung bonus freshness 2 boundary (+1) va cung khop tieu chi Distinction (b).

---

## 4. Corruption inject (Sprint 3)

Kich ban inject da dung:
- Chay etl voi --no-refund-fix de giu lai stale refund 14 ngay.
- Chay them --skip-validate de cho phep embed du lieu da fail halt expectation.

Lenh da chay:
- python etl_pipeline.py run --run-id bonus-inject-2026-04-15T05-45Z --no-refund-fix --skip-validate
- python eval_retrieval.py --out artifacts/eval/bonus_inject_eval.csv
- python etl_pipeline.py run --run-id bonus-clean-final-2026-04-15T05-50Z
- python eval_retrieval.py --out artifacts/eval/bonus_clean_final_eval.csv

Bang chung phat hien:
- bonus_inject_eval.csv co hits_forbidden = yes tai q_refund_window.
- bonus_clean_final_eval.csv da tro lai hits_forbidden = no.

---

## 5. Han che & viec chua lam

- Chua bo sung bo eval mo rong >= 5 cau hoi theo tung data slice.
- Chua tao grading_run.jsonl (dang bo qua theo yeu cau hien tai vi chua co grading_questions).

---

## 6. Pydantic Gate & Kết quả lần chạy inject-bad

**Tại sao Pydantic Gate lại quan trọng?**
Cổng chặn (quality gate) sử dụng Pydantic đóng vai trò như một chốt chặn cuối cùng kiểm tra cấu trúc dữ liệu. Thay vì chỉ kiểm tra từng điều kiện rời rạc bằng Python thuần (như `len()`, `re.match()`), Pydantic cung cấp "schema contract" mạnh mẽ, đảm bảo rằng mọi dòng dữ liệu (row) đều có đủ các trường bắt buộc, kiểu dữ liệu chính xác, và nội dung hợp lệ (như `doc_id` phải nằm trong `ALLOWED_DOC_IDS`, `chunk_text` phải có độ dài nhất định, `effective_date` là Date hợp lệ). Việc gán "severity = halt" cho cổng Pydantic giúp hệ thống chủ động từ chối dữ liệu bẩn *trước khi* nó được lưu trữ hay nhúng (embed) vào hệ thống.

**Kết quả trong lần chạy `inject-bad`**:
Khi chạy pipeline với dữ liệu xấu (`inject-bad`), nếu dữ liệu thiếu các field bắt buộc hoặc sai lệch chuẩn dữ liệu quy định, Pydantic sẽ quét qua từng `cleaned_row` và bắt lỗi thông qua `CleanedRowModel.model_validate`. Hàm `validate_cleaned_rows_with_pydantic` khi đó sẽ trả về `passed=False` kèm theo `error_count` > 0.
Expectation `pydantic_cleaned_schema_valid` nhận kết quả thất bại và raise cờ `halt=True`. Điều này kích hoạt cơ chế dừng khẩn cấp toàn bộ pipeline, chặn không cho pipeline lưu file output bẩn vào kho và bảo vệ chất lượng truy cập dòng dữ liệu. Quá trình kiểm nghiệm thực tế đã chứng minh tính răn đe của rules này.
