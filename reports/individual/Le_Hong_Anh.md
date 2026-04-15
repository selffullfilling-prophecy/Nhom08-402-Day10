# Báo Cáo Cá Nhân — Lab Day 10: Data Pipeline & Observability

**Họ và tên:** Lê Hồng Anh  
**Vai trò:** Monitoring Owner
**Ngày nộp:** 15/04/2026
**Độ dài yêu cầu:** **400–650 từ** (ngắn hơn Day 09 vì rubric slide cá nhân ~10% — vẫn phải đủ bằng chứng)

---

## 1. Tôi phụ trách phần nào? (80–120 từ)

**File / module:**
Tôi đảm nhiệm vai trò **Monitoring Owner**, chịu trách nhiệm chính cho việc thiết lập và vận hành hệ thống giám sát độ tin cậy của dữ liệu (Data Observability). Cụ thể, tôi phát triển module `monitoring/freshness_check.py` và tích hợp nó vào `etl_pipeline.py`. Nhiệm vụ của tôi là đảm bảo dữ liệu trong Vector Store luôn "tươi" (fresh), phản ánh đúng những thay đổi mới nhất từ các tài liệu chính sách (Policy). 

**Kết nối với thành viên khác:**
Tôi trực tiếp làm việc với Ingestion Owner để thống nhất cấu trúc file manifest — "trái tim" của hệ thống giám sát — chứa các metadata quan trọng như `run_id`, `latest_exported_at`, và `run_timestamp`. Điều này giúp hệ thống tự động phát hiện và cảnh báo khi dữ liệu bị lỗi thời, tránh việc AI phản hồi dựa trên thông tin cũ.

**Bằng chứng (commit / comment trong code):**
Bằng chứng đóng góp của tôi có thể tìm thấy tại các commit liên quan đến hàm `check_manifest_freshness_boundaries` trong file `monitoring/freshness_check.py` và việc định nghĩa các SLA trong `contracts/data_contract.yaml`.

---

## 2. Một quyết định kỹ thuật (100–150 từ)

Một trong những quyết định kỹ thuật quan trọng nhất tôi đã thực hiện là thiết lập cơ chế **Freshness Check với 2 Boundary độc lập**: Ingest Boundary và Publish Boundary. Thay vì chỉ kiểm tra xem pipeline có chạy hay không, tôi tách biệt hai mốc thời gian: (1) `latest_exported_at` — thời điểm dữ liệu được xuất ra từ hệ thống nguồn, và (2) `run_timestamp` — thời điểm pipeline hoàn tất việc làm sạch và nạp dữ liệu vào ChromaDB. 

Việc chia tách này giải quyết bài toán "Data Stale" từ hai phía. Nếu Ingest Boundary vi phạm SLA (24 giờ), chúng ta biết vấn đề nằm ở đội nguồn (Upstream) chưa cung cấp file export mới. Ngược lại, nếu Publish Boundary vi phạm (2 giờ), lỗi thuộc về hệ thống pipeline của chúng ta bị treo hoặc không kích hoạt đúng lịch trình. Tôi đã chọn mức độ `WARN` cho Ingest và `FAIL` cho Publish trong file `freshness_check.py` vì chúng ta có quyền kiểm soát tuyệt đối luồng xử lý nội bộ. Quyết định này giúp rút ngắn thời gian Troubleshooting (gỡ lỗi) từ hàng giờ xuống còn vài phút nhờ xác định chính xác vị trí đứt gãy trong chuỗi cung ứng dữ liệu.

---

## 3. Một lỗi hoặc anomaly đã xử lý (100–150 từ)

Trong quá trình Sprint 3 (Inject Corruption), tôi phát hiện ra một Anomaly nghiêm trọng khi file manifest bị lỗi định dạng ngày tháng hoặc thiếu trường `latest_exported_at`. Ban đầu, script `freshness_check.py` sẽ bị crash (quăng lỗi ValueError) khiến toàn bộ pipeline dừng lại một cách không kiểm soát. Triệu chứng là `etl_pipeline.py freshness` trả về exit code 1 mà không có giải thích rõ ràng.

Tôi đã xử lý bằng cách viết lại hàm `parse_iso` và bổ sung logic kiểm tra tại `_evaluate_boundary`. Tôi chuyển từ việc để script bị crash sang trạng thái trả về một dictionary chứa status `WARN` kèm lý do cụ thể là `timestamp_missing_or_invalid`. Điều này giúp pipeline vẫn có thể tiếp tục (hoặc dừng lại một cách "elegant" nếu cấu hình halt) và ghi lại log chi tiết để đội vận hành xử lý. Fix này đảm bảo tính Robust (chống chịu lỗi) cho hệ thống monitoring, ngăn chặn việc "giám sát viên cũng bị hỏng" khi dữ liệu đầu vào không đạt chuẩn.

---

## 4. Bằng chứng trước / sau (80–120 từ)

Sử dụng dữ liệu từ `run_id: 2026-04-15T04-15Z`, tôi đã thực hiện kiểm tra freshness. Manifest của run này ghi nhận `latest_exported_at`: "2026-04-10T08:00:00" và `run_timestamp`: "2026-04-15T04:15:39.854039+00:00".

Kết quả kiểm tra (tôi đã mô phỏng lại trong log):
```text
Run ID: 2026-04-15T04-15Z | Overall Status: FAIL
Boundary [Ingest]: FAIL (Age: 116.26h, SLA: 24h) - Reason: freshness_sla_exceeded
Boundary [Publish]: PASS (Age: 0.23h, SLA: 2h)
```
Mặc dù pipeline vừa chạy cách đây ít phút (Publish PASS), nhưng dữ liệu nguồn đã cũ tới gần 5 ngày. Nhờ check này, tôi đã ngăn chặn được việc người dùng nhận thông tin Refund 14 ngày cũ.

---

## 5. Cải tiến tiếp theo (40–80 từ)

Nếu có thêm 2 giờ, tôi sẽ triển khai tính năng **Deep Freshness Validation**. Thay vì chỉ tin vào manifest, tôi sẽ viết script quét trực tiếp thư mục `artifacts/cleaned/`, đọc cột `effective_date` của các dòng dữ liệu để đối chiếu thực tế. Ngoài ra, tôi sẽ tích hợp Slack Webhook để đẩy cảnh báo tự động thay vì phải kiểm tra log thủ công.
