
---

### Giai đoạn 1: Xây dựng & Chạy Luồng Chuẩn (Sprint 1 & 2)
*Mục tiêu: Đưa dữ liệu "bẩn" qua màng lọc, làm sạch, và đưa vào Vector Database thành công.*

1. **Ingestion (Đọc & Log):** * Đọc file `policy_export_dirty.csv`.
   * Khởi tạo Run ID và ghi log số lượng dòng thô (Raw records).
2. **Cleaning & Validation (Làm sạch & Kiểm duyệt):**
   * Mở file `transform/cleaning_rules.py` và `quality/expectations.py`.
   * **Nhiệm vụ cốt lõi:** Code thêm ít nhất 3 rule làm sạch và 2 expectation (bộ kiểm thử chất lượng dữ liệu) mới. 
   * *Lưu ý quan trọng:* Các rule này phải "bắt" được lỗi thực tế từ data. Ví dụ: Phát hiện dòng nào ghi sai số ngày phép, dòng nào thiếu ID, đẩy các dòng vi phạm này vào thư mục `quarantine/` (cách ly) thay vì cho đi tiếp.
3. **Embedding (Lưu trữ Vector):**
   * Phần dữ liệu "sạch" (đã pass qua các rule) sẽ được chunk và đưa vào ChromaDB. Đảm bảo logic "upsert" (cập nhật nếu trùng ID) và xóa các ID rác.
4. **Chạy thử Luồng Chuẩn:**
   * Chạy lệnh: `python etl_pipeline.py run`
   * **Kỳ vọng:** Script chạy thành công (exit 0), trong thư mục `artifacts/logs/` và `manifests/` có file mới chứng minh luồng chạy hoàn tất.

---

### Giai đoạn 2: "Phá" Dữ Liệu & Lấy Bằng Chứng (Sprint 3)
*Mục tiêu: Chứng minh rằng bộ lọc Data Observability của nhóm thực sự có tác dụng bằng cách so sánh kết quả RAG trước và sau khi làm sạch.*

1. **Inject Corruption (Chạy luồng lỗi cố ý):**
   * Nhóm chạy lệnh với các cờ (flags) để "tắt" bộ lọc: `python etl_pipeline.py run --run-id inject-bad --no-refund-fix --skip-validate`
   * Lúc này, dữ liệu sai (ví dụ: chính sách hoàn tiền 14 ngày đã cũ) sẽ bị đẩy thẳng vào ChromaDB.
2. **Đánh giá Before/After (Bằng chứng thép):**
   * Chạy script kiểm tra câu trả lời của AI: `python eval_retrieval.py --out artifacts/eval/after_inject_bad.csv`
   * Quan sát file CSV sinh ra: Bạn sẽ thấy model AI bị "ảo giác" hoặc trả lời sai chính sách vì đọc trúng dữ liệu bẩn.
3. **Chạy lại Luồng Chuẩn & Đánh giá lại:**
   * Chạy lại pipeline bình thường để ghi đè dữ liệu sạch vào ChromaDB.
   * Chạy lại eval: `python eval_retrieval.py --out artifacts/eval/before_after_eval.csv`
   * **Kỳ vọng:** Model AI bây giờ trả lời chính xác (ví dụ: chính sách hoàn tiền đúng là 7 ngày). Đây chính là dữ liệu để viết báo cáo vào file `quality_report.md`.

---

### Giai đoạn 3: Giám sát, Tài liệu & Đóng gói (Sprint 4)
*Mục tiêu: Chuyển giao hệ thống như một kỹ sư Data/ML chuyên nghiệp.*

1. **Freshness Check (Kiểm tra độ tươi của dữ liệu):**
   * Chạy lệnh kiểm tra xem hệ thống có chạy đúng lịch không: `python etl_pipeline.py freshness --manifest artifacts/manifests/manifest_<run-id>.json`
2. **Hoàn thiện Văn bản (Docs):**
   * Cập nhật `data_contract.yaml` (cam kết chất lượng dữ liệu giữa hệ nguồn và đội AI).
   * Viết `runbook.md` (hướng dẫn xử lý sự cố nếu pipeline báo lỗi WARN/FAIL).
   * Vẽ/Viết kiến trúc luồng dữ liệu vào `pipeline_architecture.md`.
3. **Chấm điểm tự động (Sau 17:00):**
   * Chạy `python grading_run.py` để sinh ra file `.jsonl` phục vụ việc giảng viên chấm điểm keyword tự động.

---

### Giai đoạn 4: Bàn giao (Deliverables)
Nhóm kiểm tra lại repo Git xem đã commit đủ các thành phần chưa:
* Code pipeline (`.py`).
* Bằng chứng chạy hệ thống (files trong `artifacts/logs/`, `manifests/`, `quarantine/`, `eval/`). **Tuyệt đối không commit thư mục database của ChromaDB lên Git.**
* Các file tài liệu `.md` và file Contract `.yaml`.
* Báo cáo nhóm (`group_report.md`) và báo cáo cá nhân (`individual/*.md`).

***

Bạn hoặc nhóm của bạn có muốn đi sâu vào kỹ thuật của bất kỳ giai đoạn nào không (ví dụ: cách viết bộ rules/expectations để không bị đánh giá là "trivial" - làm cho có)?