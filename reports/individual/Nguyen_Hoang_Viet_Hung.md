# Báo Cáo Cá Nhân — Lab Day 10: Data Pipeline & Observability

**Họ và tên:** Nguyễn Hoàng Việt Hùng  
**Vai trò:** System Upgrade Owner (Bonus Track)  
**Ngày nộp:** 2026-04-15  
**Độ dài yêu cầu:** **400–650 từ**

---

## 1. Tôi phụ trách phần nào? (80–120 từ)

**File / module:**
- `quality/schema_validation.py`
- `quality/expectations.py`
- `monitoring/freshness_check.py`
- `transform/cleaning_rules.py`
- `etl_pipeline.py`

Tôi không đi theo hướng "hoàn thiện baseline" dựa trên các module của các thành viên khác, nâng cấp hệ thống để đạt các tiêu chí bonus và phân hạng Distinction trong SCORING. Cụ thể, tôi bổ sung gate kiểm tra schema thật bằng Pydantic, mở rộng freshness từ 1 mốc thành 2 boundary (ingest và publish), và bỏ hard-code cutoff của HR policy bằng cơ chế đọc động từ env hoặc contract. Tôi cũng nối toàn bộ logic nâng cấp vào `etl_pipeline.py` để các chỉ số mới được ghi log và manifest. Công việc của tôi đóng vai trò "nâng trần chất lượng" chứ không chỉ giúp pipeline chạy qua.

---

## 2. Một quyết định kỹ thuật (100–150 từ)

Quyết định kỹ thuật quan trọng nhất của tôi là tách kiểm soát chất lượng thành hai lớp: **schema integrity** và **data freshness observability**. Ở lớp schema, tôi chọn dùng Pydantic model thật (`CleanedRowModel`) và đưa vào expectation `pydantic_cleaned_schema_valid` với mức `halt`, vì nếu shape dữ liệu sai thì mọi bước sau (embed, retrieval, grading) đều có nguy cơ sai dây chuyền. Ở lớp observability, tôi chủ động tách freshness thành hai boundary độc lập thay vì gộp chung. Lý do là pipeline có thể chạy đúng giờ nhưng dữ liệu nguồn vẫn cũ; nếu chỉ có một chỉ số tổng quát, đội vận hành sẽ debug sai chỗ. Thiết kế này giúp log trả lời rõ câu hỏi "nguồn stale hay pipeline stale", giảm thời gian khoanh vùng sự cố khi chạy production theo lịch.

---

## 3. Một lỗi hoặc anomaly đã xử lý (100–150 từ)

Anomaly tôi xử lý là trạng thái "pipeline nhìn có vẻ ổn nhưng retrieval vẫn nhiễm policy cũ" trong kịch bản inject. Khi chạy `bonus-inject-2026-04-15T05-45Z`, log cho thấy `expectation[refund_no_stale_14d_window] FAIL (halt) :: violations=2`, nhưng do có `--skip-validate` nên pipeline vẫn tiếp tục embed để phục vụ demo before/after. Nếu không có cơ chế expectation rõ ràng và ghi chi tiết violations, team rất dễ bỏ qua lỗi này vì run vẫn `PIPELINE_OK`.

Tôi xử lý bằng cách giữ nguyên khả năng demo inject nhưng ép mọi fail được log định lượng, sau đó chạy lại luồng chuẩn để hồi phục index sạch. Kết quả run `bonus-clean-final-2026-04-15T05-50Z` đã quay về `violations=0`, đảm bảo hệ thống có cả hai chế độ: mô phỏng lỗi có kiểm soát và vận hành chuẩn có chặn chất lượng.

---

## 4. Bằng chứng trước / sau (80–120 từ)

**Run và log tiêu biểu:**
- `run_bonus-inject-2026-04-15T05-45Z.log`: `cleaned_records=7`, `quarantine_records=4`, `refund_no_stale_14d_window FAIL ... violations=2`, `pydantic_cleaned_schema_valid OK ... validated_rows=7 error_count=0`.
- `run_bonus-clean-final-2026-04-15T05-50Z.log`: `cleaned_records=6`, `quarantine_records=5`, `refund_no_stale_14d_window OK ... violations=0`, `embed_prune_removed=6`.

**Eval before/after:**
- `artifacts/eval/bonus_inject_eval.csv`: câu `q_refund_window` có `hits_forbidden=yes`, top preview vẫn chứa "14 ngày làm việc".
- `artifacts/eval/bonus_clean_final_eval.csv`: cùng câu chuyển thành `hits_forbidden=no`, preview là "7 ngày làm việc" kèm marker `[cleaned: stale_refund_window]`.

**Freshness 2 boundary:**
Ở run clean-final: ingest `FAIL` (age ~121.847h, SLA 24h), publish `PASS` (age 0.0h, SLA 2h), chứng minh phân tách boundary hoạt động đúng.

---

## 5. Cải tiến tiếp theo (40–80 từ)

Nếu có thêm 2 giờ, tôi sẽ thêm một "bonus regression command" chạy liên tục 3 kịch bản (clean -> inject -> clean-final), tự động xuất bảng delta cho `violations`, `hits_forbidden`, `top1_doc_matches`, và trạng thái freshness từng boundary. Mục tiêu là biến evidence bonus thành quy trình kiểm thử định kỳ, không phụ thuộc thao tác thủ công khi gần deadline.