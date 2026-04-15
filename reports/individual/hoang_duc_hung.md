# Báo Cáo Cá Nhân — Lab Day 10: Data Pipeline & Observability

**Họ và tên:** Hoàng Đức Hưng  
**Vai trò:** Cleaning — `transform/cleaning_rules.py`  
**Ngày nộp:** 2026-04-15  

---

## 1. Tôi phụ trách phần nào?

Tôi phụ trách `transform/cleaning_rules.py`. Phần tôi làm là nhận các dòng raw đã được load, áp dụng rule clean, rồi tách dữ liệu thành hai nhánh `cleaned` và `quarantine`. Trong commit `7dbc978`, tôi đã thêm các xử lý có thể kiểm chứng trực tiếp trong file này: kiểm tra `source_chunk_id`, kiểm tra định dạng `exported_at`, đọc cutoff HR từ `contracts/data_contract.yaml`, và quarantine chunk refund còn marker migration cũ.

---

## 2. Một quyết định kỹ thuật

Quyết định kỹ thuật rõ nhất của tôi là với `policy_refund_v4`, tôi không chỉ thay chuỗi `14 ngày làm việc` thành `7 ngày làm việc`, mà còn quarantine bản ghi nào vẫn còn marker `policy-v3` hoặc `lỗi migration`. Rule này nằm trong `clean_rows()` với reason `stale_refund_migration_marker`. Tôi chọn cách chuyển hẳn bản ghi đó sang quarantine thay vì sửa xong rồi giữ lại trong cleaned. Trong code hiện tại, rule này chỉ chạy khi `apply_refund_window_fix=True`. Khi so sánh hai chế độ trên cùng bộ raw, kết quả đo được là: nếu `apply_refund_window_fix=False` thì `cleaned=6`, `quarantine=4`; còn nếu bật fix thì `cleaned=5`, `quarantine=5`. Như vậy tác động của rule là có đo được bằng số lượng bản ghi, không phải chỉ thay đổi hình thức.

---

## 3. Một lỗi hoặc anomaly đã xử lý

Một anomaly tôi xử lý là xung đột version của tài liệu nghỉ phép HR. Trong raw có đồng thời một dòng `hr_leave_policy` với `effective_date=2025-01-01` và một dòng khác với `effective_date=2026-02-01`. Nếu chỉ kiểm tra `doc_id` thì cả hai đều lọt qua. Tôi xử lý bằng cách đọc ngưỡng `policy_versioning.hr_leave_min_effective_date: "2026-01-01"` từ `contracts/data_contract.yaml`, rồi quarantine mọi bản ghi HR cũ hơn mốc đó với reason `stale_hr_policy_effective_date`. Dòng thực tế trong `artifacts/quarantine/quarantine_hung-cleaning-report.csv` là: `7,hr_leave_policy,...,2025-01-01,...,stale_hr_policy_effective_date,2025-01-01,2026-01-01,contract`. Tôi cũng ghi thêm `cutoff_source=contract` vào quarantine row để khi đọc CSV có thể biết ngay rule đang lấy cutoff từ đâu.

---

## 4. Bằng chứng trước / sau

Tôi dùng `run_id=hung-cleaning-report` làm mốc bằng chứng cho phần cleaning. Hai dòng CSV dưới đây cho thấy rõ một thay đổi trước/sau mà file `cleaning_rules.py` tạo ra:

```text
Raw:    10,it_helpdesk_faq,"FAQ bổ sung: đổi mật khẩu qua portal self-service có thể mất tối đa 24 giờ để đồng bộ toàn hệ thống.",01/02/2026,2026-04-10T08:00:00
Cleaned: it_helpdesk_faq_5_74bc2a3cec7e24e0,it_helpdesk_faq,"FAQ bổ sung: đổi mật khẩu qua portal self-service có thể mất tối đa 24 giờ để đồng bộ toàn hệ thống.",2026-02-01,2026-04-10T08:00:00
```

Ngoài ra, cùng run này, log `artifacts/logs/run_hung-cleaning-report.log` ghi `cleaned_records=5` và `quarantine_records=5`. File `artifacts/quarantine/quarantine_hung-cleaning-report.csv` cũng cho thấy các reason do tôi xử lý trong `cleaning_rules.py` như `duplicate_chunk_text`, `stale_refund_migration_marker`, `stale_hr_policy_effective_date` và `unknown_doc_id`.

---

## 5. Cải tiến tiếp theo

Nếu có thêm 2 giờ, tôi sẽ viết test hồi quy riêng cho `clean_rows()` trong `transform/cleaning_rules.py`. Cụ thể, tôi muốn có một fixture raw nhỏ để kiểm từng reason như `invalid_exported_at_format`, `stale_hr_policy_effective_date`, `duplicate_chunk_text` và `stale_refund_migration_marker`. Cách này sát đúng phần tôi phụ trách và giúp kiểm tra lại nhanh mỗi khi chỉnh rule clean.
