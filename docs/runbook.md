# Sổ tay xử lý sự cố (Runbook) — Lab Day 10 (incident tối giản)

---

## Triệu chứng (Symptom)

> Người dùng / tác vụ (agent) thấy gì? (Ví dụ: trả lời “14 ngày” thay vì 7 ngày)

- Hệ thống truy xuất (retrieval) trả về ngữ cảnh cũ (stale context): câu hỏi về hoàn tiền (refund) có thể dính phải đoạn dữ liệu (chunk) "14 ngày làm việc".
- Kiểm tra độ tươi (freshness check) có thể báo THẤT BẠI (FAIL) khi bản chụp dữ liệu thô (raw snapshot) cũ hơn mức quy định trong SLA.

---

## Phát hiện (Detection)

> Chỉ số (metric) nào thông báo? (độ tươi, kiểm định thất bại, đánh giá `hits_forbidden`)

- Kiểm định `expectation[refund_no_stale_14d_window]` báo THẤT BẠI trong nhật ký chạy (log run) `bonus-inject-2026-04-15T05-45Z`.
- File `artifacts/eval/bonus_inject_eval.csv` có câu hỏi `q_refund_window` hiển thị `hits_forbidden=yes`.
- Lệnh `etl_pipeline.py freshness` trả về kết quả cho 2 ranh giới: nạp (ingest) báo THẤT BẠI, xuất bản (publish) báo VƯỢT QUA.

---

## Chẩn đoán (Diagnosis)

| Bước | Việc làm | Kết quả mong đợi |
|------|----------|------------------|
| 1 | Kiểm tra `artifacts/manifests/manifest_<run_id>.json` | Xác định các trạng thái `no_refund_fix`, `skipped_validate`, số lượng bản ghi sạch/cách ly |
| 2 | Mở `artifacts/quarantine/quarantine_<run_id>.csv` | Thấy rõ lý do cách ly và các dữ liệu vi phạm quy tắc |
| 3 | Chạy `python eval_retrieval.py --out artifacts/eval/check.csv` | Kiểm tra trạng thái `hits_forbidden` và tài liệu hàng đầu (top 1 doc) trên các câu hỏi mẫu (golden questions) |

---

## Khắc phục (Mitigation)

> Chạy lại pipeline, hoàn tác (rollback) nhúng dữ liệu, tạm treo thông báo “dữ liệu cũ”, …

- Nếu chế độ nạp lỗi (inject mode) đang bật: Chạy lại pipeline chuẩn, không kèm tham số `--no-refund-fix` và không kèm `--skip-validate`.
- Xác minh file `artifacts/eval/bonus_clean_final_eval.csv` có câu hỏi `q_refund_window` đạt trạng thái `hits_forbidden=no`.
- Nếu độ tươi THẤT BẠI do bản chụp (snapshot) cũ: Hiển thị thông báo "dữ liệu cũ" (data stale) trên bảng điều khiển (dashboard) và tạo tác vụ cập nhật bản xuất (export) mới.

---

## Phòng ngừa (Prevention)

> Thêm kiểm định (expectation), cảnh báo (alert), chủ sở hữu — kết nối sang Day 11 nếu có rào chắn (guardrail).

- Duy trì kiểm định dừng (expectation halt) cho các đoạn dữ liệu hoàn tiền cũ (refund stale window).
- Thêm kiểm định dừng `pydantic_cleaned_schema_valid` để chặn các sai lệch sơ đồ dữ liệu (schema drift) trước khi thực hiện nhúng (embed).
- Bảo toàn cơ chế loại bỏ và cập nhật (prune + upsert) để tránh các vector cũ còn tồn tại sau khi chạy lại.
- Duy trì kênh cảnh báo trong hợp đồng: `slack:#vin-assignment-alerts`.
- Tách biệt SLA độ tươi cho ranh giới nạp (ingest) và xuất bản (publish) để cảnh báo đúng ngữ cảnh.
- Thêm công việc chạy hàng ngày (daily job) để tạo bản xuất mới hoặc điều chỉnh SLA theo bản chất của bản chụp nhằm tránh cảnh báo giả (false alarm).