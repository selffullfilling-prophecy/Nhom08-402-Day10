# Báo Cáo Cá Nhân — Lab Day 10: Data Pipeline & Observability

**Họ và tên:** Nguyễn Thị Hương Giang 
**Vai trò:** Embed Owner (Chroma collection, idempotency, eval)  
**Ngày nộp:** 15/4/2026 
**Độ dài yêu cầu:** **400–650 từ**

---

> Viết **"tôi"**, đính kèm **run_id**, **tên file**, **đoạn log** hoặc **dòng CSV** thật.  
> Nếu làm phần clean/expectation: nêu **một số liệu thay đổi** (vd `quarantine_records`, `hits_forbidden`, `top1_doc_expected`) khớp bảng `metric_impact` của nhóm.  
> Lưu: `reports/individual/[ten_ban].md`

---

## 1. Tôi phụ trách phần nào? (80–120 từ)

**File / module:**

- Tôi xây dựng toàn bộ luồng chạy chính của hệ thống trong file `etl_pipeline.py` (hàm `cmd_run`). Tôi thiết lập bộ khung orchestration để gọi tuần tự các module: Ingest -> Clean -> Validate -> Embed. Đồng thời, tôi xây dựng cơ chế tự động tracking và xuất metadata ra file JSON (`manifest`) sau mỗi lần run.

**Kết nối với thành viên khác:**

Nhận file raw, truyền cho hàm `clean_rows` của Cleaning Owner, nhận lại file `cleaned` để chạy `run_expectations`, và cuối cùng quyết định có gọi hàm embed của Embed Owner hay không dựa trên cờ `halt`.

**Bằng chứng (commit / comment trong code):**

Đoạn code tôi xử lý ghi nhận metadata cho quá trình Ingestion và xuất Manifest:
```python
manifest = {
    "run_id": run_id,
    "raw_records": raw_count,
    "cleaned_records": len(cleaned),
    "quarantine_records": len(quarantine),
    "skipped_validate": bool(args.skip_validate and halt),
    # ...
}
man_path = MAN_DIR / f"manifest_{run_id.replace(':', '-')}.json"
man_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
```
---

## 2. Một quyết định kỹ thuật (100–150 từ)

> VD: chọn halt vs warn, chiến lược idempotency, cách đo freshness, format quarantine.

không hard-code việc dừng pipeline (halt) khi expectation thất bại, mà sử dụng kết hợp biến halt trả về từ bộ Quality và cờ --skip-validate truyền từ command line.

---

## 3. Một lỗi hoặc anomaly đã xử lý (100–150 từ)

> Mô tả triệu chứng → metric/check nào phát hiện → fix.

script bị crash với lỗi FileNotFoundError khi ghi log hoặc xuất manifest vì các thư mục artifacts/logs/, artifacts/manifests/ chưa được tạo thủ công trên máy.

Phát hiện: Code ghi file trực tiếp mà không kiểm tra cấu trúc cây thư mục của workspace hiện tại.

Xử lý (Fix): Tôi đã khắc phục bằng cách sử dụng thư viện pathlib, thêm logic tự động đệ quy tạo thư mục nếu chưa tồn tại ngay đầu hàm cmd_run và trong hàm helper _log.

---

## 4. Bằng chứng trước / sau (80–120 từ)
Vì tôi phụ trách Orchestration, tôi dùng log luồng chạy của pipeline để minh chứng kịch bản Before/After của Sprint 3

> Khi chạy chuẩn (python etl_pipeline.py run): Pipeline pass toàn bộ rule, chạy mượt mà: expectation[pydantic_cleaned_schema_valid] OK (halt) :: Passed PIPELINE_OK
> Khi cố ý inject bẩn (python etl_pipeline.py run --no-refund-fix): Pipeline lập tức giăng bẫy được lỗi schema và tự động Halt để bảo vệ Vector DB: expectation[pydantic_cleaned_schema_valid] FAIL (halt) :: Failed PIPELINE_HALT: expectation suite failed (halt).

_________________

---

## 5. Cải tiến tiếp theo (40–80 từ)

> Nếu có thêm 2 giờ, tôi sẽ nâng cấp cơ chế Logging trong etl_pipeline.py. Thay vì chỉ ghi text tuần tự vào file .log, tôi sẽ chuyển sang dùng thư viện logging chuẩn của Python tích hợp jsonlogger, để toàn bộ log của pipeline được xuất ra dưới định dạng JSON Lines (.jsonl). Việc này giúp sau này dễ dàng đưa log lên các hệ thống giám sát như ELK stack hoặc Datadog.

_________________
