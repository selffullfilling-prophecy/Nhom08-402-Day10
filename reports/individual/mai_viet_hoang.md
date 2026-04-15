# Báo Cáo Cá Nhân — Lab Day 10: Data Pipeline & Observability

**Họ và tên:** Mai Viết Hoàng
**Vai trò:** Quality Assurance — Expectation Suite Maintainer
**Ngày nộp:** 2026-04-15
**Độ dài yêu cầu:** **400–650 từ**

---

## 1. Tôi phụ trách phần nào? (80–120 từ)

**File / module:**
- `quality/expectations.py`
- `docs/quality_report.md`

Tôi chịu trách nhiệm bảo trì và tích hợp các quy tắc kiểm tra chất lượng vào file trung tâm `quality/expectations.py`. Công việc của tôi không phải là tạo ra các quy tắc, mà là đảm bảo chúng được "kết nối" vào pipeline một cách chính xác. Tôi đã thêm một quy tắc mới do thành viên khác cung cấp vào bộ kiểm tra, định nghĩa cờ `halt` cho nó, và đảm bảo pipeline sẽ thực thi quy tắc này. Ngoài ra, tôi cập nhật `quality_report.md` để ghi lại kết quả tổng thể của bộ kiểm tra chất lượng (expectation suite).

**Kết nối với thành viên khác:**
Tôi là cầu nối giữa những người viết quy tắc (rules) và pipeline, đảm bảo các quy tắc của họ được tích hợp đúng chuẩn.

---

## 2. Một quyết định kỹ thuật (100–150 từ)

Quyết định kỹ thuật của tôi là đề xuất một quy ước chung cho tất cả các hàm kiểm tra (expectation functions): chúng phải trả về một dictionary có cấu trúc, thay vì chỉ một giá trị `True/False` đơn giản. Cấu trúc này, ví dụ `{"passed": bool, "details": {...}}`, cho phép hàm `run_expectation_suite` trong pipeline chính có thể "đọc" và ghi log các thông tin chẩn đoán chi tiết (như số lượng lỗi, ví dụ lỗi) mà không cần biết logic bên trong của từng hàm. Điều này giúp hệ thống dễ dàng mở rộng để đón nhận các quy tắc kiểm tra phức tạp trong tương lai mà không cần phải sửa đổi logic điều phối chính.

---

## 3. Một lỗi hoặc anomaly đã xử lý (100–150 từ)

**Triệu chứng:** Ban đầu, khi một quy tắc kiểm tra thất bại, log chỉ ghi nhận một thông báo rất chung chung, ví dụ `Expectation 'X' failed`. Điều này gây rất nhiều khó khăn cho việc debug vì không biết lý do cụ thể là gì.
**Phát hiện:** Tôi nhận ra rằng luồng thông tin từ các hàm kiểm tra đến hệ thống log quá nghèo nàn. Cần phải có một "kênh" để các hàm này có thể gửi thêm thông tin chẩn đoán về cho người vận hành.
**Fix/Xử lý:** Dựa trên quyết định kỹ thuật ở trên, tôi đã làm việc với team để chuẩn hóa output của các hàm kiểm tra. Sau đó, tôi cập nhật logic trong `etl_pipeline.py` để khi một expectation thất bại, nó sẽ tự động tìm và in ra các thông tin trong trường `details` của kết quả trả về. Điều này giúp người vận hành xác định lỗi nhanh hơn rất nhiều.

---

## 4. Bằng chứng trước / sau (80–120 từ)

- `run_id`: `bonus-inject-2026-04-15T05-45Z` và `bonus-clean-final-2026-04-15T05-50Z`
- **Bằng chứng:**
Trong log của run `bonus-inject-...`, một trong các expectation đã thất bại. Nhờ vào việc tích hợp của tôi, log đã ghi lại được thông tin chẩn đoán chi tiết do expectation đó cung cấp:
`"expectation_name": {"passed": false, "details": {"error_count": 7, ...}}`.
Ngược lại, trong log của run `bonus-clean-final-...`, tất cả expectation đều `passed: true`.
Điều này chứng tỏ vai trò tích hợp của tôi đã thành công trong việc làm cho pipeline trở nên minh bạch và dễ quan sát hơn.

---

## 5. Cải tiến tiếp theo (40–80 từ)

Nếu có thêm thời gian, tôi sẽ xây dựng một cơ chế "tagging" cho các expectation trong `quality/expectations.py`. Ví dụ, có thể thêm tag `schema`, `business_logic`, `freshness`. Điều này cho phép pipeline có thể chạy các nhóm expectation khác nhau một cách có chọn lọc (ví dụ: `run --only-schema-checks`), giúp tăng tốc độ debug và kiểm thử các phần riêng lẻ của hệ thống.
