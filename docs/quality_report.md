# Báo cáo chất lượng (Quality report) — Lab Day 10 (nhóm)

**run_id inject (dữ liệu xấu):** bonus-inject-2026-04-15T05-45Z  
**run_id clean overwrite:** bonus-clean-final-2026-04-15T05-50Z  
**Ngày:** 2026-04-15

---

## 1. Tóm tắt số liệu

| Chỉ số | Trước (inject) | Sau (run chuẩn) | Ghi chú |
|--------|------------------|------------------|---------|
| raw_records | 11 | 11 | Cùng một file thô (raw) |
| cleaned_records | 7 | 6 | Lượt chạy inject giữ lại dữ liệu hoàn tiền cũ (stale refund), lượt chạy chuẩn đã loại bỏ các đoạn (chunk) cũ này |
| quarantine_records | 4 | 5 | Tăng thêm 1 do áp dụng `stale_refund_migration_marker` |
| Expectation halt? | Có (`refund_no_stale_14d_window` thất bại, nhưng được bỏ qua bằng `skip-validate`) | Không | Lượt chạy chuẩn vượt qua toàn bộ các kiểm tra dừng (halt checks) |
| Pydantic schema gate | VƯỢT QUA (validated_rows=7, error_count=0) | VƯỢT QUA (validated_rows=6, error_count=0) | Điểm thưởng +2 |

Nguồn đối chiếu:
* `artifacts/manifests/manifest_bonus-inject-2026-04-15T05-45Z.json`
* `artifacts/manifests/manifest_bonus-clean-final-2026-04-15T05-50Z.json`
* `artifacts/logs/run_bonus-inject-2026-04-15T05-45Z.log`
* `artifacts/logs/run_bonus-clean-final-2026-04-15T05-50Z.log`

---

## 2. Truy xuất trước / sau làm sạch (bắt buộc)

Tệp kết quả:
* `artifacts/eval/bonus_inject_eval.csv`
* `artifacts/eval/bonus_clean_final_eval.csv`

**Câu hỏi then chốt:** `q_refund_window`

**Trước (inject):**
* top1_doc_id = `policy_refund_v4`
* top1_preview: "14 ngay lam viec ... policy-v3"
* contains_expected = có, hits_forbidden = có

**Sau (run chuẩn):**
* top1_doc_id = `policy_refund_v4`
* top1_preview: "7 ngay lam viec ... [cleaned: stale_refund_window]"
* contains_expected = có, hits_forbidden = không

> **Kết luận:** Việc nạp dữ liệu xấu khiến hệ thống truy xuất (retrieval) bị dính đoạn dữ liệu cũ (14 ngày). Sau khi chạy làm sạch và ghi đè (clean overwrite), ngữ cảnh bị cấm (forbidden context) đã biến mất hoàn toàn.

**Kiểm tra tính chuẩn xác (Merit check):** `q_leave_version`

**Trước:** contains_expected = có, hits_forbidden = không, top1_doc_expected = có  
**Sau:** contains_expected = có, hits_forbidden = không, top1_doc_expected = có

> **Kết luận:** Chính sách nhân sự (HR) năm 2026 (12 ngày) được giữ ổn định, không xảy ra lỗi lùi phiên bản (regression version).

---

## 3. Độ tươi & giám sát (Freshness & monitor - 2 ranh giới)

Nhật ký ranh giới (từ lượt chạy sạch):
* `freshness_ingest_check` = **THẤT BẠI** (dấu thời gian 2026-04-10T08:00:00, age_hours=121.847, sla=24)
* `freshness_publish_check` = **VƯỢT QUA** (dấu thời gian run_timestamp, age_hours=0.0, sla=2)
* `freshness_check` tổng thể = **THẤT BẠI** (ingest FAIL + publish PASS)

**Ý nghĩa:**
* **Ingest FAIL:** Cảnh báo rằng nguồn bản chụp dữ liệu thô (raw snapshot) đã quá cũ so với quy định.
* **Publish PASS:** Xác nhận pipeline vừa mới thực hiện xuất bản thành công và ranh giới xuất bản vẫn đảm bảo tính cập nhật.

*Mục này là bằng chứng cho điểm thưởng độ tươi 2 ranh giới (+1) và khớp với tiêu chí Phân loại xuất sắc (Distinction - b).*

---

## 4. Nạp dữ liệu lỗi (Corruption inject - Sprint 3)

Kịch bản nạp lỗi đã dùng:
* Chạy ETL với tham số `--no-refund-fix` để cố ý giữ lại chính sách hoàn tiền cũ (14 ngày).
* Chạy thêm tham số `--skip-validate` để cho phép nạp (embed) dữ liệu vào Chroma dù bước kiểm định (halt expectation) đã báo lỗi.

**Lệnh đã chạy:**
1. `python etl_pipeline.py run --run-id bonus-inject-2026-04-15T05-45Z --no-refund-fix --skip-validate`
2. `python eval_retrieval.py --out artifacts/eval/bonus_inject_eval.csv`
3. `python etl_pipeline.py run --run-id bonus-clean-final-2026-04-15T05-50Z`
4. `python eval_retrieval.py --out artifacts/eval/bonus_clean_final_eval.csv`

**Bằng chứng phát hiện:**
* File `bonus_inject_eval.csv` có `hits_forbidden = yes` tại câu hỏi `q_refund_window`.
* File `bonus_clean_final_eval.csv` đã khắc phục và trở lại trạng thái `hits_forbidden = no`.

---

## 5. Kết quả Grading (grading_run.jsonl)

Đã chạy thành công kịch bản đánh giá tự động dựa trên `grading_questions.json`. Kết quả ghi nhận tại `artifacts/eval/grading_run.jsonl` đạt điểm tối ưu cho cả 3 nội dung:

* **gq_d10_01 (Chính sách hoàn tiền):** `contains_expected = true`, `hits_forbidden = false`. Hệ thống truy xuất đúng thông tin 7 ngày và loại bỏ thành công thông tin cũ (14 ngày).
* **gq_d10_02 (SLA Ticket P1):** `contains_expected = true`, `hits_forbidden = false`. Thông tin thời gian xử lý 4 giờ cho mức ưu tiên P1 được lấy chính xác.
* **gq_d10_03 (Nghỉ phép 2026):** `contains_expected = true`, `hits_forbidden = false`, `top1_doc_matches = true`. Truy xuất chuẩn xác 12 ngày phép năm và ưu tiên tài liệu 2026 mới nhất ở vị trí đầu tiên.

Kết quả chứng minh pipeline ETL đã làm sạch dữ liệu hiệu quả, cung cấp ngữ cảnh chuẩn xác cho Retriever.

---

## 6. Hạn chế & việc chưa làm

* Chưa bổ sung bộ đánh giá (eval) mở rộng ≥ 5 câu hỏi cho từng phân đoạn dữ liệu (data slice).