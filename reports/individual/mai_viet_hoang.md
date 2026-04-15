# Báo Cáo Cá Nhân — Lab Day 10: Data Pipeline & Observability

**Họ và tên:** Mai Viết Hoàng
**Vai trò:** Ingestion / Cleaning / Embed / Monitoring — Quality Gate (Pydantic Integration)
**Ngày nộp:** 2026-04-15
**Độ dài yêu cầu:** **400–650 từ**

---

## 1. Tôi phụ trách phần nào? (80–120 từ)

**File / module:**
- `quality/expectations.py`
- `quality/schema_validation.py`
- `docs/quality_report.md`

Tôi phụ trách việc tích hợp Pydantic thành một "quality gate" (cổng chặn) trong pipeline. Công việc của tôi là thêm hàm `validate_cleaned_rows_with_pydantic` vào danh sách các rules `expectations` và định nghĩa nó, đảm bảo rằng mọi dòng dữ liệu đã qua bước làm sạch (cleaning) đều phải tuân thủ nghiêm ngặt schema contract đã định nghĩa trong `CleanedRowModel` trước khi được lưu hay nhúng (embed).

**Kết nối với thành viên khác:**
Tôi làm việc với team Data Quality, đảm bảo phần kiểm tra chất lượng bằng Pydantic kết nối thông suốt với phần Cleaning và Ingestion của nhóm, cung cấp cơ chế halt pipeline nếu schema data không hợp lệ.

**Bằng chứng (commit / comment trong code):**
- Import và thêm expectation `pydantic_cleaned_schema_valid` vào `quality/expectations.py` với cờ hiệu `halt`.

---

## 2. Một quyết định kỹ thuật (100–150 từ)

Quyết định quan trọng nhất là việc phân loại Pydantic validation expectation là mức độ "halt" (dừng pipeline) thay vì chỉ "warn" (cảnh báo). Khi cấu trúc dữ liệu bị sai lệch chuẩn (ví dụ thiếu `doc_id`, `chunk_text` quá ngắn, sai chuẩn ISO date), đó không chỉ là sự thay đổi định dạng mà có khả năng phá hỏng các tác vụ hạ nguồn như upsert Vector DB hoặc RAG Retrieval. Bằng cách dùng `ConfigDict(extra="forbid")` và dựa trên các ValidationError, gateway Pydantic hoạt động như một barrier chủ động cắt đứt mọi lỗi cấu trúc dữ liệu từ đầu vào, giảm thiểu rủi ro dữ liệu rác lan truyền. Các expectation kiểm tra content-level có thể là warn, nhưng schema-level thì buộc phải là halt.

---

## 3. Một lỗi hoặc anomaly đã xử lý (100–150 từ)

Triệu chứng: Khi chèn dữ liệu không hợp lệ hoặc thiếu field (`inject-bad`), hệ thống vẫn có thể chạy qua luồng nếu chỉ dựa trên các rule if/else cơ bản mà không có chốt chặn cấu trúc schema.
Phát hiện: Việc thiếu schema validation cứng cho phép các trường thiếu thông tin len lỏi vào file output. Cần chặn đứng nó lại.
Fix/Xử lý: Tích hợp trực tiếp `validate_cleaned_rows_with_pydantic` gọi hàm `CleanedRowModel.model_validate` tại `expectations.py`. Nếu schema bị lỗi (ví dụ không thỏa format, text quá ngắn), kết quả `schema_result["passed"]` trở thành False, kích hoạt điều kiện halt và chặn toàn bộ tiến trình pipeline, in log ra các dòng lỗi (mảng sample_errors) để team Data dễ debug.

---

## 4. Bằng chứng trước / sau (80–120 từ)

- `run_id`: `bonus-inject-2026-04-15T05-45Z` và `bonus-clean-final-2026-04-15T05-50Z`
- Bằng chứng Pydantic gate hoạt động:
Trong logs và file `docs/quality_report.md` (mục 1. Tom tat so lieu), kết quả Pydantic schema gate cho ra `PASS (validated_rows=7, error_count=0)` ở file chuẩn do không vi phạm strict rules của `CleanedRowModel`. Trong khi ở các test lỗi cố ý, pydantic gate lập tức reject các validation (schema detail lỗi) khiến pipeline lập tức halt mà không tạo ra các bản ghi lỗi đẩy vào chromadb, đảm bảo Data Quality đầu vào. 

---

## 5. Cải tiến tiếp theo (40–80 từ)

Nếu có thêm thời gian, tôi sẽ bổ sung Custom error mapping của pydantic để hiển thị lỗi chi tiết hơn trên CLI (chỉ rõ tên field và lí do) để debug dễ dàng hơn thay vì in raw errors dict. Đồng thời, bổ sung thêm các custom field_validator cho `chunk_text` dùng regex chặn ký tự rác đặc thù.
