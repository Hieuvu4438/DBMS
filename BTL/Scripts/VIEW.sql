--VIEW BÁO CÁO HỌC TẬP TỔNG QUÁT
CREATE OR REPLACE VIEW vw_student_progress_report AS
SELECT 
    up.full_name AS student_name,
    u.email,
    s.school_name,
    c.title AS course_title,
    ce.progress,
    ce.enrolled_at,
    CASE 
        WHEN ce.progress = 100 THEN 'Hoàn thành'
        WHEN ce.progress > 0 THEN 'Đang học'
        ELSE 'Mới đăng ký'
    END AS learning_status
FROM users u
JOIN user_profiles up ON u.user_id = up.user_id
JOIN students s ON u.user_id = s.user_id
JOIN course_enrollments ce ON s.user_id = ce.student_id
JOIN general_courses c ON ce.course_id = c.course_id
WHERE u.is_deleted = FALSE;

SELECT course_title, progress, learning_status 
FROM vw_student_progress_report
WHERE email = 'minh.student@signlearn.local'
ORDER BY progress DESC;

--THỐNG KÊ HIỆU NĂNG KHÓA HỌC

CREATE OR REPLACE VIEW vw_course_analytics AS
SELECT 
    c.course_id,
    c.title AS course_title,
    up.full_name AS teacher_name,
    COUNT(ce.enrollment_id) AS total_students,
    ROUND(AVG(ce.progress), 2) AS avg_progress,
    (SELECT ROUND(AVG(rating), 1) FROM user_feedbacks WHERE context LIKE '%' || c.title || '%') AS avg_rating
FROM general_courses c
JOIN teachers t ON c.teacher_id = t.user_id
JOIN user_profiles up ON t.user_id = up.user_id
LEFT JOIN course_enrollments ce ON c.course_id = ce.course_id
WHERE c.is_deleted = FALSE
GROUP BY c.course_id, c.title, up.full_name;

SELECT course_title, total_students, avg_rating
FROM vw_course_analytics
WHERE avg_rating >= 4.0 
  AND teacher_name = 'Nguyen Thi Lan';

-- VIEW HIỂN THỊ BẢNG XẾP HẠNG
CREATE OR REPLACE VIEW vw_top_learners_leaderboard AS
SELECT 
    up.full_name,
    up.avatar_url,
    ss.current_streak,
    ss.highest_streak,
    (SELECT COUNT(*) FROM user_achievements ua WHERE ua.user_id = s.user_id) AS total_achievements
FROM students s
JOIN user_profiles up ON s.user_id = up.user_id
JOIN student_streaks ss ON s.user_id = ss.student_id
ORDER BY ss.current_streak DESC, total_achievements DESC;

SELECT full_name, current_streak, total_achievements
FROM vw_top_learners_leaderboard
ORDER BY current_streak DESC, total_achievements DESC
LIMIT 5;