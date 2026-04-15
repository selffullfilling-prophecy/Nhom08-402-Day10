# Kiến trúc pipeline — Lab Day 10

**Nhóm:** Nhóm08-402  
**Cập nhật:** 2026-04-15

---

## 1. Sơ đồ luồng (bắt buộc có 1 diagram: Mermaid / ASCII)

```
data/raw/policy_export_dirty.csv
    -> ingest (etl_pipeline.py run, log raw_records, run_id)
    -> clean (transform/cleaning_rules.py)
    -> quarantine (artifacts/quarantine/quarantine_<run_id>.csv)
    -> validate (quality/expectations.py + pydantic schema gate, halt/warn)
    -> publish cleaned snapshot (artifacts/cleaned/cleaned_<run_id>.csv)
    -> embed publish boundary (Chroma day10_kb, upsert chunk_id + prune stale ids)
    -> retrieval serving (eval_retrieval.py, grading_run.py, Day 09 agents)

freshness ingest boundary: manifest.latest_exported_at vs FRESHNESS_SLA_INGEST_HOURS
freshness publish boundary: manifest.run_timestamp vs FRESHNESS_SLA_PUBLISH_HOURS
lineage checkpoint: artifacts/manifests/manifest_<run_id>.json
```

> Vẽ thêm: điểm đo **freshness**, chỗ ghi **run_id**, và file **quarantine**.

---

## 2. Ranh giới trách nhiệm

| Thành phần | Đầu vào (Input) | Đầu ra (Output) | Chủ sở hữu (Owner) nhóm |
|------------|-------|--------|--------------|
| Ingest | data/raw/policy_export_dirty.csv | raw_records + log run_id | Ingestion owner |
| Transform | các dòng raw | các dòng đã làm sạch + các dòng bị cách ly | Cleaning owner |
| Quality | các dòng đã làm sạch | kết quả kiểm định + quyết định dừng/tiếp tục | Quality owner |
| Embed | bản chụp (snapshot) CSV đã làm sạch | Chroma collection day10_kb | Embed owner |
| Monitor | manifest json | trạng thái ingest + trạng thái publish + độ tươi (freshness) tổng thể | Monitoring owner |

---

## 3. Tính nhất quán (Idempotency) & chạy lại (rerun)

> Mô tả: upsert theo `chunk_id` hay chiến lược khác? Chạy lại 2 lần có bị trùng lặp (duplicate) vector không?

Lớp Embed thực hiện cập nhật (upsert) theo `chunk_id` và loại bỏ (prune) các ID không còn tồn tại trong lượt chạy làm sạch (cleaned run) hiện tại. Chiến lược này giữ cho chỉ mục (index) tuân theo ranh giới xuất bản (publish boundary) của bản chụp, tránh trùng lặp vector và tránh các đoạn dữ liệu cũ (stale chunk) tồn tại sau khi chạy lại.

---

## 4. Liên hệ Day 09

> Pipeline này cung cấp / làm mới kho dữ liệu (corpus) cho việc truy xuất (retrieval) trong `day09/lab` như thế nào? (cùng `data/docs/` hay xuất riêng?)

Pipeline Day 10 tạo lại collection `day10_kb` từ bản xuất đã làm sạch. Việc truy xuất ở Day 09 có thể trỏ vào collection này để đảm bảo ngữ cảnh (context) đúng phiên bản chính sách. Nếu cần tách biệt để thử nghiệm, hãy thay đổi `CHROMA_COLLECTION` trong file `.env` để không ảnh hưởng đến các luồng khác.

---

## 5. Rủi ro đã biết

- Bản chụp thô (raw snapshot) cũ có thể khiến việc kiểm tra độ tươi khi nạp (ingest freshness) bị THẤT BẠI (FAIL) dù việc kiểm tra độ tươi khi xuất bản (publish freshness) vẫn VƯỢT QUA (PASS).
- Nếu bật tham số `--skip-validate` trong môi trường vận hành (production) có thể dẫn đến việc xuất bản dữ liệu xấu.
- Việc thiếu file `grading_questions.json` sẽ chặn bước tạo `grading_run.jsonl` cho đến khi Giảng viên công bố file.