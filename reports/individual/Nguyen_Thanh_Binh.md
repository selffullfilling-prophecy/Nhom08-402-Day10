# Báo Cáo Cá Nhân — Lab Day 10: Data Pipeline & Observability

**Họ và tên:** Nguyễn Thanh Bình 
**Vai trò:** Grading & Tooling Owner — Chịu trách nhiệm về kịch bản chấm điểm tự động  
**Ngày nộp:** 15/04/2026 
**Độ dài yêu cầu:** **400–650 từ** (ngắn hơn Day 09 vì rubric slide cá nhân ~10% — vẫn phải đủ bằng chứng)

---

> Viết **"tôi"**, đính kèm **run_id**, **tên file**, **đoạn log** hoặc **dòng CSV** thật.  
> Nếu làm phần clean/expectation: nêu **một số liệu thay đổi** (vd `quarantine_records`, `hits_forbidden`, `top1_doc_expected`) khớp bảng `metric_impact` của nhóm.  
> Lưu: `reports/individual/[ten_ban].md`

---

## 1. Tôi phụ trách phần nào? (80–120 từ)

**File / module:**

- grading_run.py: Script chính để chạy bộ câu hỏi grading, query ChromaDB để retrieval, kiểm tra các tiêu chí như must_contain_any, must_not_contain, và expect_top1_doc_id, sau đó xuất ra file grading_run.jsonl hợp lệ.

**Kết nối với thành viên khác:**

Tôi kết nối với người phụ trách retrieval (eval_retrieval.py) để đảm bảo logic query và embedding tương thích. Ngoài ra, phối hợp với người làm quality expectations để các tiêu chí grading khớp với expectation rules. Cuối cùng, làm việc với người monitoring để log và validate output.

**Bằng chứng (commit / comment trong code):**

Trong grading_run.py, tôi đã thêm logic kiểm tra top1_doc_matches dựa trên expect_top1_doc_id, và đảm bảo output JSONL có đủ fields như id, question, top1_doc_id, contains_expected, hits_forbidden, top1_doc_matches. Commit hash: [insert commit hash if available].

---

## 2. Một quyết định kỹ thuật (100–150 từ)

Tôi quyết định sử dụng top-k=5 mặc định trong query ChromaDB để cân bằng giữa độ chính xác và hiệu suất. Điều này cho phép retrieval nhiều documents để kiểm tra must_contain_any trên toàn bộ blob, nhưng vẫn tập trung vào top1_doc_id cho expect_top1_doc_matches. Thay vì chỉ check top1, tôi join tất cả documents thành một blob để tìm bất kỳ từ khóa nào trong must_contain_any, giúp phát hiện nội dung phân tán. Đối với must_not_contain, tôi check toàn bộ blob để tránh false positive. Tôi cũng thêm field top1_doc_matches chỉ khi expect_top1_doc_id được chỉ định, tránh null không cần thiết. Quyết định này đảm bảo grading script linh hoạt và khớp với rubric, cho phép đánh giá retrieval quality một cách toàn diện mà không quá phức tạp.

---

## 3. Một lỗi hoặc anomaly đã xử lý (100–150 từ)

Trong quá trình test grading_run.py, tôi phát hiện output grading_run.jsonl thiếu field top1_doc_matches cho một số câu hỏi không có expect_top1_doc_id, dẫn đến inconsistency. Metric check trong instructor_quick_check.py phát hiện lỗi này khi validate schema. Tôi fix bằng cách set top1_doc_matches=None khi không có expect_top1_doc_id, thay vì luôn true. Ngoài ra, ban đầu script dùng grading_questions.json nhưng file thực tế là test_questions.json, gây ImportError. Tôi update default path trong argparse để dùng đúng file. Sau fix, script chạy thành công và tạo JSONL hợp lệ, với tất cả fields đúng format.

---

## 4. Bằng chứng trước / sau (80–120 từ)

Sau khi chạy grading_run.py với run_id=2026-04-15T10-42Z, file grading_run.jsonl cho thấy retrieval hoạt động tốt. Ví dụ:

- {"id": "q_refund_window", "question": "Khách hàng có bao nhiêu ngày để yêu cầu hoàn tiền...", "top1_doc_id": "policy_refund_v4", "contains_expected": true, "hits_forbidden": false, "top1_doc_matches": null}

- {"id": "q_leave_version", "question": "Theo chính sách nghỉ phép hiện hành (2026)...", "top1_doc_id": "hr_leave_policy", "contains_expected": true, "hits_forbidden": false, "top1_doc_matches": true}

Trước khi fix path questions, script fail với FileNotFoundError. Sau fix, tất cả 4 câu đều contains_expected=true, hits_forbidden=false, và q_leave_version top1_doc_matches=true, chứng minh cleaning rules loại bỏ version cũ thành công.

---

## 5. Cải tiến tiếp theo (40–80 từ)

Nếu có thêm 2 giờ, tôi sẽ thêm validation schema cho grading_run.jsonl sử dụng Pydantic, để đảm bảo format output luôn đúng và dễ debug. Ngoài ra, implement caching cho embedding để tránh download model mỗi lần chạy, tăng tốc pipeline.
