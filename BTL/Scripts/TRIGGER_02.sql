--TRIGGER 1
-- ==============================================================================
-- BƯỚC 1: CÀI ĐẶT HỆ THỐNG (Chạy 1 lần trước khi demo)
-- ==============================================================================
CREATE OR REPLACE FUNCTION fn_update_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_users_update_timestamp ON users;
CREATE TRIGGER trg_users_update_timestamp
BEFORE UPDATE ON users
FOR EACH ROW
EXECUTE FUNCTION fn_update_timestamp();

-- ==============================================================================
-- BƯỚC 2: KIỂM TRA DỮ LIỆU TRƯỚC KHI THAY ĐỔI
-- Lời thoại: "Thầy xem, đây là dữ liệu cũ với updated_at ở trong quá khứ."
-- ==============================================================================
SELECT user_id, username, updated_at 
FROM users 
WHERE user_id = '30000000-0000-0000-0000-000000000001';

-- ==============================================================================
-- BƯỚC 3: THỰC HIỆN NGHIỆP VỤ (Giả lập Backend sửa tên user)
-- Lời thoại: "Em thực hiện đổi tên user, và tuyệt đối KHÔNG đụng tới cột updated_at."
-- ==============================================================================
UPDATE users 
SET username = 'student_minh_pro_vip' 
WHERE user_id = '30000000-0000-0000-0000-000000000001';

-- ==============================================================================
-- BƯỚC 4: KIỂM TRA LẠI DỮ LIỆU SAU KHI THAY ĐỔI (PHÉP MÀU XẢY RA)
-- Lời thoại: "Dù em không truyền thời gian vào, Trigger đã tự động gắn timestamp của giây phút hiện tại."
-- ==============================================================================
SELECT user_id, username, updated_at 
FROM users 
WHERE user_id = '30000000-0000-0000-0000-000000000001';

--TRIGGER 2
-- ==============================================================================
-- BƯỚC 1: CÀI ĐẶT HỆ THỐNG (Chạy 1 lần trước khi demo)
-- ==============================================================================
CREATE OR REPLACE FUNCTION fn_update_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_users_update_timestamp ON users;
CREATE TRIGGER trg_users_update_timestamp
BEFORE UPDATE ON users
FOR EACH ROW
EXECUTE FUNCTION fn_update_timestamp();

-- ==============================================================================
-- BƯỚC 2: KIỂM TRA DỮ LIỆU TRƯỚC KHI THAY ĐỔI
-- Lời thoại: "Thầy xem, đây là dữ liệu cũ với updated_at ở trong quá khứ."
-- ==============================================================================
SELECT user_id, username, updated_at 
FROM users 
WHERE user_id = '30000000-0000-0000-0000-000000000001';

-- ==============================================================================
-- BƯỚC 3: THỰC HIỆN NGHIỆP VỤ (Giả lập Backend sửa tên user)
-- Lời thoại: "Em thực hiện đổi tên user, và tuyệt đối KHÔNG đụng tới cột updated_at."
-- ==============================================================================
UPDATE users 
SET username = 'student_minh_pro_vip' 
WHERE user_id = '30000000-0000-0000-0000-000000000001';

-- ==============================================================================
-- BƯỚC 4: KIỂM TRA LẠI DỮ LIỆU SAU KHI THAY ĐỔI (PHÉP MÀU XẢY RA)
-- Lời thoại: "Dù em không truyền thời gian vào, Trigger đã tự động gắn timestamp của giây phút hiện tại."
-- ==============================================================================
SELECT user_id, username, updated_at 
FROM users 
WHERE user_id = '30000000-0000-0000-0000-000000000001';


--TRIGGER 3
-- ==============================================================================
-- BƯỚC 1: CÀI ĐẶT HỆ THỐNG
-- ==============================================================================
CREATE OR REPLACE FUNCTION fn_validate_course_publish()
RETURNS TRIGGER AS $$
DECLARE
    module_count INT;
BEGIN
    IF NEW.visibility_status = 'PUBLISHED' AND OLD.visibility_status != 'PUBLISHED' THEN
        SELECT COUNT(*) INTO module_count FROM general_course_modules WHERE course_id = NEW.course_id;
        IF module_count = 0 THEN
            RAISE EXCEPTION 'LỖI: Không thể Publish khóa học "%" vì chưa có bài giảng (Module = 0)!', NEW.title;
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_before_publish_course ON general_courses;
CREATE TRIGGER trg_before_publish_course
BEFORE UPDATE ON general_courses
FOR EACH ROW
EXECUTE FUNCTION fn_validate_course_publish();

-- ==============================================================================
-- BƯỚC 2: CHUẨN BỊ 1 KHÓA HỌC TRỐNG (TRƯỚC THAY ĐỔI)
-- Lời thoại: "Em tạo 1 khóa học mới tinh, trạng thái DRAFT, chưa có bài giảng nào."
-- ==============================================================================
INSERT INTO general_courses (course_id, teacher_id, category_id, title, visibility_status)
VALUES ('40000000-0000-0000-0000-000000000999', '20000000-0000-0000-0000-000000000001', 1, 'Khóa học Test Chặn Lỗi', 'DRAFT')
ON CONFLICT DO NOTHING;

SELECT course_id, title, visibility_status 
FROM general_courses WHERE course_id = '40000000-0000-0000-0000-000000000999';

-- ==============================================================================
-- BƯỚC 3: CỐ TÌNH PHẠM LỖI
-- Lời thoại: "Em sẽ thử Update trạng thái thành PUBLISHED. Thầy sẽ thấy Database văng lỗi chặn lại ngay."
-- ==============================================================================
-- Khi chạy lệnh này, màn hình sẽ báo lỗi đỏ chót!
UPDATE general_courses 
SET visibility_status = 'PUBLISHED' 
WHERE course_id = '40000000-0000-0000-0000-000000000999';

-- ==============================================================================
-- BƯỚC 4: THÊM DỮ LIỆU HỢP LỆ VÀ PUBLISH LẠI (THÀNH CÔNG)
-- Lời thoại: "Khóa học bị chặn nên vẫn là DRAFT. Giờ em thêm 1 bài giảng vào, rồi mới Publish lại."
-- ==============================================================================
-- Thêm nội dung cho khóa học
INSERT INTO general_course_modules (course_id, title, order_index)
VALUES ('40000000-0000-0000-0000-000000000999', 'Chương 1: Giới thiệu', 1);

-- Thử Publish lần 2 (Lần này sẽ thành công)
UPDATE general_courses 
SET visibility_status = 'PUBLISHED' 
WHERE course_id = '40000000-0000-0000-0000-000000000999';

-- Xem kết quả cuối cùng
SELECT course_id, title, visibility_status 
FROM general_courses WHERE course_id = '40000000-0000-0000-0000-000000000999';