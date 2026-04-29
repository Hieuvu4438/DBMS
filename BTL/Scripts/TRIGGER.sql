--AUTOMATION TRIGGER: TỰ ĐỘNG CẬP NHẬT UPDATED_AT
-- 1.1. Tạo hàm dùng chung
CREATE OR REPLACE FUNCTION fn_update_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 1.2. Gắn vào bảng (Ví dụ bảng users và general_courses)
CREATE TRIGGER trg_users_update_timestamp
BEFORE UPDATE ON users
FOR EACH ROW
EXECUTE FUNCTION fn_update_timestamp();

CREATE TRIGGER trg_courses_update_timestamp
BEFORE UPDATE ON general_courses
FOR EACH ROW
EXECUTE FUNCTION fn_update_timestamp();


update users u 
set username = 'new_name' 
where user_id = '30000000-0000-0000-0000-000000000001';
--DỮ LIỆU BAN ĐẦU
SELECT user_id, username, updated_at 
FROM users 
WHERE user_id = '30000000-0000-0000-0000-000000000001';

--SỬA DỮ LIỆU 
UPDATE users 
SET username = 'student_minh_pro' 
WHERE user_id = '30000000-0000-0000-0000-000000000001';

--XEM KẾT QUẢ MỚI
SELECT user_id, username, updated_at 
FROM users 
WHERE user_id = '30000000-0000-0000-0000-000000000001';



--=========================================================================
--TRIGGER 2: DATA INTEGRITY: 
--2.1. CÀI ĐẶT TRIGGER
-- 1. TẠO HÀM (FUNCTION) KHỞI TẠO STREAK
CREATE OR REPLACE FUNCTION fn_init_student_streak()
RETURNS TRIGGER AS $$
BEGIN
    -- Ngay khi có ID học viên mới (NEW.user_id), tự động tạo 1 dòng bên bảng student_streaks
    INSERT INTO student_streaks (student_id, current_streak, highest_streak, last_activity_date)
    VALUES (NEW.user_id, 0, 0, NULL);
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 2. GẮN HÀM VÀO BẢNG STUDENTS
DROP TRIGGER IF EXISTS trg_after_insert_student ON students;

CREATE TRIGGER trg_after_insert_student
AFTER INSERT ON students
FOR EACH ROW
EXECUTE FUNCTION fn_init_student_streak();

--2.2. CHUẨN BỊ 1 TÀI KHOẢN USER
INSERT INTO users (user_id, username, password_hash, email, role_id)
VALUES (
    '30000000-0000-0000-0000-000000000599', 
    'demo_new_user_01', 
    'hash123', 
    'newuser@local_01', 
    (SELECT role_id FROM roles WHERE role_name = 'STUDENT')
);

--2.3. GẤP ĐÔI CỬA SỔ QUERY
SELECT * FROM student_streaks WHERE student_id = '30000000-0000-0000-0000-000000000599';

--2.4. KÍCH HOẠT TRIGGER BẰNG CÁCH THÊM VÀO BẢNG students
INSERT INTO students (user_id, grade_level, school_name)
VALUES ('30000000-0000-0000-0000-000000000999', 'Grade 10', 'Demo High School');

--2.5. CHẠY LẠI LỆNH SELECT Ở LỆNH 2

--TRIGGER 3: CHẶN XUẤT BẢN KHÓA HỌC RỖNG
-- 1. TẠO HÀM (FUNCTION) KIỂM TRA ĐIỀU KIỆN PUBLISH
CREATE OR REPLACE FUNCTION fn_validate_course_publish()
RETURNS TRIGGER AS $$
DECLARE
    module_count INT;
BEGIN
    -- Kịch bản chỉ xảy ra khi cố tình đổi status TỪ trạng thái khác SANG 'PUBLISHED'
    IF NEW.visibility_status = 'PUBLISHED' AND OLD.visibility_status != 'PUBLISHED' THEN
        
        -- Đếm số lượng module đang thuộc về khóa học này
        SELECT COUNT(*) INTO module_count 
        FROM general_course_modules 
        WHERE course_id = NEW.course_id;
        
        -- Nếu bằng 0 thì VĂNG LỖI, chặn đứng lệnh UPDATE
        IF module_count = 0 THEN
            RAISE EXCEPTION 'LỖI NGHIỆP VỤ (DATABASE BÁO CÁO): Không thể Publish khóa học "%" vì chưa có Module nào!', NEW.title;
        END IF;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 2. GẮN HÀM VÀO BẢNG GENERAL_COURSES
DROP TRIGGER IF EXISTS trg_before_publish_course ON general_courses;

CREATE TRIGGER trg_before_publish_course
BEFORE UPDATE ON general_courses
FOR EACH ROW
EXECUTE FUNCTION fn_validate_course_publish();

-- LỆNH 1: TẠO 1 KHÓA HỌC NHÁP
INSERT INTO general_courses (course_id, teacher_id, category_id, title, visibility_status)
VALUES (
    '40000000-0000-0000-0000-000000000678', 
    '20000000-0000-0000-0000-000000000001', -- Lấy ID giáo viên có sẵn
    1, 
    'Khóa học Test Trigger', 
    'DRAFT'
);
--LỆNH 2: CỐ TÍNH VI PHẠM NGHIỆP VỤ (CỐ GẮNG PUBLISH)
UPDATE general_courses 
SET visibility_status = 'PUBLISHED' 
WHERE course_id = '40000000-0000-0000-0000-000000000678';

--LỆNH 3: THÊM NỘI DUNG HỢP LỆ VÀ PUBLISH LẠI
-- Thêm 1 module cho khóa học
INSERT INTO general_course_modules (module_id, course_id, title, order_index)
VALUES ('41000000-0000-0000-0000-000000000999', '40000000-0000-0000-0000-000000000678', 'Module 1: Mở đầu', 1);

-- Chạy lại lệnh Publish
UPDATE general_courses 
SET visibility_status = 'PUBLISHED' 
WHERE course_id = '40000000-0000-0000-0000-000000000678';

