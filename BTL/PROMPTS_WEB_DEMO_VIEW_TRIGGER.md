# Prompt Guide: Web Demo for PostgreSQL Views and Triggers

File này dùng để hướng dẫn AI code backend/frontend cho demo trực quan hai phần trong bài DBMS:

- Views từ `Scripts/VIEW.sql`
- Triggers từ `Scripts/TRIGGER_02.sql`

Mục tiêu là tạo một web demo giúp người xem hiểu rõ:

1. View là gì, view tổng hợp dữ liệu từ nhiều bảng như thế nào.
2. Trigger là gì, trigger tự động chạy khi dữ liệu thay đổi như thế nào.
3. Người dùng thao tác trên web, thấy dữ liệu trước và sau khi SQL object hoạt động.

Nên chia prompt thành nhiều bước nhỏ để tránh AI làm quá nhiều cùng lúc và dễ kiểm soát lỗi.

---

## 0. Bối cảnh chung cần đưa cho AI ở mọi prompt

Khi bắt đầu một phiên AI mới, hãy gửi prompt nền này trước.

```text
Bạn đang hỗ trợ tôi xây dựng web demo cho bài tập lớn môn Hệ quản trị cơ sở dữ liệu.

Project là Vietnamese Sign Language Online Education System, dùng PostgreSQL.

Nguồn đúng về database hiện tại nằm trong các file:
- Scripts/TABLE.sql: schema chính
- Scripts/DATA.sql: seed data
- Scripts/VIEW.sql: các view cần demo
- Scripts/TRIGGER_02.sql: các trigger cần demo

Yêu cầu quan trọng:
- Không tự bịa bảng/cột mới nếu không có trong schema.
- Luôn đọc TABLE.sql trước khi viết query.
- Backend nên đơn giản, ưu tiên Flask vì project đã dùng Python/Flask.
- Frontend nên đơn giản, trực quan, dễ demo trên lớp.
- Mỗi tính năng demo phải có: mô tả, nút thao tác, dữ liệu trước thao tác, dữ liệu sau thao tác, và giải thích ngắn gọn điều gì vừa xảy ra trong DBMS.
- Không cần authentication thật, không cần deploy production.
- Ưu tiên code rõ ràng, dễ chạy local, dễ chụp screenshot cho báo cáo.
```

---

## 1. Prompt kiểm tra hiện trạng project trước khi code

Dùng prompt này để AI đọc repo và đề xuất kiến trúc trước, chưa code ngay.

```text
Hãy kiểm tra repo hiện tại để chuẩn bị xây dựng web demo cho Views và Triggers.

Cần đọc các file:
- Scripts/TABLE.sql
- Scripts/DATA.sql
- Scripts/VIEW.sql
- Scripts/TRIGGER_02.sql
- Nếu có thư mục demo/ thì đọc cấu trúc backend/frontend hiện tại.

Sau khi đọc, hãy báo cáo ngắn gọn:
1. Hiện repo đã có Flask demo chưa, entrypoint là file nào.
2. Database connection đang được cấu hình ở đâu.
3. Các view trong VIEW.sql gồm những gì và nên demo bằng màn hình nào.
4. Các trigger trong TRIGGER_02.sql gồm những gì và nên demo bằng thao tác nào.
5. Có điểm bất thường nào trong TRIGGER_02.sql không.
6. Đề xuất kiến trúc tối thiểu để demo trên web.

Chưa sửa file ở bước này.
```

Lưu ý: `TRIGGER_02.sql` hiện tại có `TRIGGER 1` và `TRIGGER 2` giống nhau, đều là demo cập nhật `updated_at` của bảng `users`. Nếu muốn demo đa dạng hơn, có thể yêu cầu AI dùng thêm trigger khởi tạo streak từ `Scripts/TRIGGER.sql`, nhưng nếu bài chỉ theo `TRIGGER_02.sql` thì nên giữ đúng file này.

---

## 2. Prompt thiết kế flow demo trực quan

Dùng prompt này để chốt giao diện và luồng thao tác trước khi code.

```text
Hãy thiết kế flow web demo cho phần PostgreSQL Views và Triggers.

Yêu cầu giao diện:
- Có trang chính `/dbms-demo` hoặc trang tương đương.
- Có 2 tab lớn:
  1. Views Demo
  2. Triggers Demo

Tab Views Demo cần có 3 card:
1. Student Progress Report
   - Dùng view `vw_student_progress_report`
   - Có nút Load Data
   - Hiển thị bảng: course_title, progress, learning_status
   - Có mô tả view này join users, profiles, students, enrollments, courses.

2. Course Analytics
   - Dùng view `vw_course_analytics`
   - Có nút Load Data
   - Hiển thị bảng: course_title, teacher_name, total_students, avg_progress, avg_rating
   - Có mô tả view này tổng hợp enrollment và feedback.

3. Top Learners Leaderboard
   - Dùng view `vw_top_learners_leaderboard`
   - Có nút Load Data
   - Hiển thị bảng: full_name, current_streak, highest_streak, total_achievements
   - Có mô tả view này phục vụ leaderboard/gamification.

Tab Triggers Demo cần có ít nhất 2 card:
1. Auto Updated At Trigger
   - Hiển thị dữ liệu user trước khi update.
   - Có nút Update Username.
   - Hiển thị dữ liệu sau update.
   - Làm nổi bật cột `updated_at` tự thay đổi dù backend không gửi giá trị updated_at.

2. Course Publish Validation Trigger
   - Tạo hoặc reset một course test ở trạng thái DRAFT và chưa có module.
   - Có nút Try Publish Without Module, kỳ vọng database trả lỗi.
   - Hiển thị error message rõ ràng.
   - Có nút Add Module.
   - Có nút Publish Again, kỳ vọng thành công.
   - Hiển thị trạng thái cuối cùng là PUBLISHED.

Hãy trả về thiết kế endpoint backend, component/frontend layout, và dữ liệu JSON mẫu cho từng thao tác. Chưa code ở bước này.
```

---

## 3. Prompt code backend Flask API

Dùng prompt này sau khi đã có thiết kế. Nếu project đã có Flask app, yêu cầu AI sửa đúng file hiện có. Nếu chưa có, tạo tối thiểu trong `demo/`.

```text
Hãy implement backend Flask API cho web demo Views và Triggers.

Trước khi code, đọc lại:
- Scripts/TABLE.sql
- Scripts/VIEW.sql
- Scripts/TRIGGER_02.sql
- code Flask hiện có trong demo/ nếu có

Yêu cầu kỹ thuật:
- Dùng PostgreSQL connection hiện có nếu project đã có.
- Nếu chưa có, tạo config đơn giản dùng environment variables:
  - DB_HOST
  - DB_PORT
  - DB_NAME
  - DB_USER
  - DB_PASSWORD
- Dùng psycopg hoặc driver PostgreSQL hiện có trong project.
- Không hardcode password thật.
- Không dùng SELECT * trong API query.
- Query phải dùng đúng view/table/column trong schema.

Tạo các API endpoints sau:

Views:
- GET /api/demo/views/student-progress
  - Query `vw_student_progress_report`
  - Có thể filter email mặc định `minh.student@signlearn.local`

- GET /api/demo/views/course-analytics
  - Query `vw_course_analytics`
  - Trả về course_title, teacher_name, total_students, avg_progress, avg_rating

- GET /api/demo/views/top-learners
  - Query `vw_top_learners_leaderboard`
  - Limit 5

Triggers:
- GET /api/demo/triggers/user-before
  - Lấy user test `30000000-0000-0000-0000-000000000001`
  - Trả về user_id, username, updated_at

- POST /api/demo/triggers/update-username
  - Update username của user test thành một giá trị mới, ví dụ thêm timestamp suffix
  - Tuyệt đối không update cột updated_at trong SQL
  - Sau update, select lại user_id, username, updated_at
  - Trả về before và after để chứng minh trigger tự chạy

- POST /api/demo/triggers/reset-course-publish-demo
  - Tạo hoặc reset course test `40000000-0000-0000-0000-000000000999`
  - Đảm bảo course ở DRAFT
  - Xóa module test của course này nếu cần để tạo case lỗi
  - Trả về trạng thái hiện tại

- POST /api/demo/triggers/publish-without-module
  - Update course test sang PUBLISHED
  - Bắt exception từ PostgreSQL nếu trigger raise error
  - Trả JSON gồm success=false và error message

- POST /api/demo/triggers/add-module
  - Insert module cho course test
  - Trả về module vừa thêm hoặc danh sách module

- POST /api/demo/triggers/publish-with-module
  - Update course test sang PUBLISHED sau khi đã có module
  - Trả về success=true và course status

Yêu cầu response JSON:
- Luôn có `success`
- Có `data` nếu thành công
- Có `error` nếu thất bại
- Không expose stack trace ra frontend

Sau khi code xong:
- Cho biết file nào đã sửa/tạo.
- Cho biết cách chạy backend.
- Nếu có test thủ công bằng curl thì liệt kê 3-5 lệnh curl quan trọng.
```

---

## 4. Prompt code frontend demo

Dùng prompt này sau khi backend đã chạy được.

```text
Hãy implement frontend cho web demo Views và Triggers dựa trên API backend đã có.

Yêu cầu:
- Giao diện đơn giản, trực quan, dễ trình bày trước lớp.
- Có tiêu đề: PostgreSQL Views and Triggers Demo.
- Có 2 tab: Views Demo và Triggers Demo.
- Mỗi card demo có:
  - Tên SQL object
  - Purpose ngắn gọn
  - Nút thao tác
  - Bảng dữ liệu hoặc panel kết quả
  - Box giải thích: "What happened in the database?"

Views Demo:
1. Student Progress Report
   - Button: Load Student Progress View
   - Render table từ `/api/demo/views/student-progress`

2. Course Analytics
   - Button: Load Course Analytics View
   - Render table từ `/api/demo/views/course-analytics`

3. Top Learners Leaderboard
   - Button: Load Leaderboard View
   - Render table từ `/api/demo/views/top-learners`

Triggers Demo:
1. Auto Updated At Trigger
   - Button 1: Load Before Data
   - Button 2: Update Username
   - Hiển thị Before và After cạnh nhau
   - Highlight `updated_at` sau update
   - Giải thích rằng backend không truyền updated_at, trigger tự set CURRENT_TIMESTAMP

2. Course Publish Validation Trigger
   - Button 1: Reset Demo Course
   - Button 2: Try Publish Without Module
   - Button 3: Add Module
   - Button 4: Publish Again
   - Hiển thị timeline 4 bước
   - Nếu có lỗi từ DB thì hiển thị error box màu đỏ
   - Nếu publish thành công thì hiển thị success box màu xanh

Yêu cầu code:
- Không cần framework phức tạp nếu project đang dùng template HTML/CSS/JS thường.
- Nếu project đã dùng Flask templates, tạo template trong đúng cấu trúc hiện có.
- Nếu project đã có static CSS/JS, thêm file nhỏ riêng cho demo.
- Không làm lại toàn bộ UI cũ nếu không cần.

Sau khi code xong:
- Cho biết URL để mở demo.
- Cho biết các bước thao tác khi thuyết trình.
```

---

## 5. Prompt tích hợp SQL setup vào demo

Dùng prompt này nếu muốn web có nút tự setup view/trigger, hoặc muốn backend đảm bảo SQL object đã tồn tại.

```text
Hãy thêm cơ chế setup SQL objects cho web demo.

Yêu cầu:
- Đọc `Scripts/VIEW.sql` và `Scripts/TRIGGER_02.sql`.
- Tạo endpoint admin/demo-only:
  - POST /api/demo/setup/views
  - POST /api/demo/setup/triggers
  - hoặc POST /api/demo/setup/all
- Endpoint này chạy các câu CREATE OR REPLACE VIEW, CREATE OR REPLACE FUNCTION, DROP TRIGGER IF EXISTS, CREATE TRIGGER cần thiết.
- Không chạy các SELECT demo trong file SQL setup nếu chúng chỉ dùng để kiểm tra thủ công.
- Nếu có SQL comment tiếng Việt thì không sao, nhưng response JSON nên dùng tiếng Anh hoặc tiếng Việt không dấu để tránh lỗi encoding ở frontend.
- Endpoint setup chỉ dùng local demo, không cần bảo mật production.

Sau khi code:
- Thêm nút Setup SQL Objects trên web.
- Khi bấm setup, hiển thị danh sách object đã tạo:
  - vw_student_progress_report
  - vw_course_analytics
  - vw_top_learners_leaderboard
  - fn_update_timestamp
  - trg_users_update_timestamp
  - fn_validate_course_publish
  - trg_before_publish_course
```

---

## 6. Prompt kiểm thử end-to-end

Dùng prompt này sau khi backend/frontend đã code xong.

```text
Hãy kiểm thử end-to-end web demo Views và Triggers.

Cần làm:
1. Kiểm tra database đã có schema từ Scripts/TABLE.sql.
2. Kiểm tra seed data từ Scripts/DATA.sql.
3. Kiểm tra views từ Scripts/VIEW.sql.
4. Kiểm tra triggers từ Scripts/TRIGGER_02.sql.
5. Chạy backend Flask.
6. Mở frontend demo.
7. Test từng flow:
   - Load Student Progress View
   - Load Course Analytics View
   - Load Top Learners View
   - Auto Updated At Trigger: before -> update -> after
   - Course Publish Trigger: reset -> publish fail -> add module -> publish success

Yêu cầu báo cáo kết quả:
- Endpoint nào pass/fail.
- Nếu fail, lỗi từ backend hay PostgreSQL.
- File/dòng cần sửa.
- Không sửa lan man ngoài phạm vi demo.
```

---

## 7. Prompt tạo script hướng dẫn chạy demo

Dùng prompt này để AI tạo hướng dẫn chạy local cho nhóm.

```text
Hãy tạo hoặc cập nhật file README hướng dẫn chạy web demo Views và Triggers.

Nội dung cần có:
1. Yêu cầu môi trường:
   - PostgreSQL
   - Python
   - Flask
   - psycopg
2. Cách tạo database.
3. Thứ tự chạy SQL:
   - Scripts/TABLE.sql
   - Scripts/DATA.sql
   - Scripts/VIEW.sql
   - Scripts/TRIGGER_02.sql
4. Cách cấu hình biến môi trường DB.
5. Cách chạy Flask app.
6. URL mở demo.
7. Kịch bản thuyết trình 3-5 phút:
   - View demo: nhấn 3 nút load view và giải thích dữ liệu tổng hợp.
   - Trigger demo 1: cập nhật username, chứng minh updated_at tự đổi.
   - Trigger demo 2: publish course fail khi chưa có module, sau đó add module và publish thành công.
8. Troubleshooting:
   - Không kết nối được DB.
   - View chưa tồn tại.
   - Trigger chưa tồn tại.
   - Seed data thiếu user/course test.
```

---

## 8. Prompt polish giao diện cho dễ demo trước lớp

Dùng sau khi chức năng đã chạy đúng.

```text
Hãy polish giao diện web demo để dễ thuyết trình trước lớp.

Yêu cầu:
- Không đổi logic backend nếu đang chạy đúng.
- Cải thiện layout, màu sắc, spacing.
- Thêm badge cho SQL object type: VIEW hoặc TRIGGER.
- Thêm box SQL Concept giải thích ngắn:
  - View: virtual table, reusable query, hides join complexity.
  - Trigger: database-side automation, runs automatically on event, protects consistency.
- Với trigger updated_at, highlight before.updated_at và after.updated_at.
- Với trigger publish course, dùng timeline:
  1. Draft course without module
  2. Try publish -> rejected by trigger
  3. Add module
  4. Publish again -> success
- Giao diện phải phù hợp để chụp screenshot đưa vào báo cáo.
```

---

## 9. Prompt nếu muốn AI sửa chính xác theo lỗi

Khi chạy bị lỗi, đừng gửi prompt chung chung. Hãy gửi theo mẫu này.

```text
Web demo đang lỗi ở bước: [mô tả bước]

Tôi đã làm:
1. [bước 1]
2. [bước 2]
3. [bước 3]

Kết quả mong muốn:
- [mô tả]

Kết quả thực tế:
- [mô tả]

Log backend:
```text
[paste log]
```

Response API nếu có:
```json
[paste response]
```

Yêu cầu:
- Tìm nguyên nhân gốc.
- Chỉ sửa file liên quan.
- Không refactor lan man.
- Sau khi sửa, đưa lại bước test chính xác.
```

---

## 10. Kịch bản demo đề xuất khi đã có web

### Phần 1: Views Demo

1. Mở tab Views Demo.
2. Nhấn `Load Student Progress View`.
3. Giải thích:
   - View này giúp giáo viên/sinh viên xem tiến độ học tập mà không cần viết lại nhiều câu JOIN.
   - Dữ liệu đến từ `users`, `user_profiles`, `students`, `course_enrollments`, `general_courses`.

4. Nhấn `Load Course Analytics View`.
5. Giải thích:
   - View này tổng hợp số lượng học viên, tiến độ trung bình, rating trung bình.
   - Đây là ví dụ view phục vụ dashboard phân tích khóa học.

6. Nhấn `Load Leaderboard View`.
7. Giải thích:
   - View này phục vụ gamification, xếp hạng người học theo streak và achievement.

### Phần 2: Triggers Demo

1. Mở tab Triggers Demo.
2. Nhấn `Load Before Data`.
3. Nhấn `Update Username`.
4. Chỉ vào `updated_at` sau update và giải thích:
   - Backend chỉ update `username`.
   - Trigger `trg_users_update_timestamp` tự gọi function `fn_update_timestamp()`.
   - Vì vậy `updated_at` được cập nhật tự động trong database.

5. Nhấn `Reset Demo Course`.
6. Nhấn `Try Publish Without Module`.
7. Giải thích:
   - Course đang DRAFT và chưa có module.
   - Trigger `trg_before_publish_course` kiểm tra trước khi update.
   - Database reject thao tác publish bằng `RAISE EXCEPTION`.

8. Nhấn `Add Module`.
9. Nhấn `Publish Again`.
10. Giải thích:
   - Khi course đã có module, trigger cho phép update sang PUBLISHED.
   - Đây là business rule được bảo vệ ở tầng database, không phụ thuộc hoàn toàn vào frontend/backend.

---

## 11. Checklist thành công

Web demo được xem là đạt yêu cầu nếu:

- Backend kết nối được PostgreSQL.
- Load được cả 3 view.
- Frontend hiển thị bảng rõ ràng.
- Trigger updated_at chứng minh được before/after.
- Trigger publish course chứng minh được cả case lỗi và case thành công.
- Error từ PostgreSQL được hiển thị dễ hiểu trên web.
- Không có bảng/cột nào ngoài schema thật.
- Demo có thể thao tác bằng nút, không cần gõ SQL thủ công khi thuyết trình.
