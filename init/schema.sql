-- Kích hoạt extension UUID để có thể tự động sinh UUID (nếu cần mặc định)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ===================================================================
-- 1. HỆ THỐNG QUẢN LÝ NGƯỜI DÙNG & XÁC THỰC (USER MANAGEMENT)
-- ===================================================================

CREATE TABLE roles (
    role_id SERIAL PRIMARY KEY,
    role_name VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE users (
    user_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    email VARCHAR(100) UNIQUE,
    role_id INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_users_role FOREIGN KEY (role_id) REFERENCES roles (role_id) ON DELETE RESTRICT
);

CREATE TABLE user_profiles (
    profile_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL,
    full_name VARCHAR(100) NOT NULL,
    avatar_url VARCHAR(255),
    phone_number VARCHAR(20),
    date_of_birth DATE,
    CONSTRAINT fk_user_profiles_user FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
);

CREATE TABLE students (
    user_id UUID PRIMARY KEY,
    grade_level VARCHAR(50),
    school_name VARCHAR(150),
    CONSTRAINT fk_students_user FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
);

CREATE TABLE teachers (
    user_id UUID PRIMARY KEY,
    bio TEXT,
    department VARCHAR(100),
    CONSTRAINT fk_teachers_user FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
);

CREATE TABLE authentication_sessions (
    session_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL,
    session_key VARCHAR(255) NOT NULL,
    otp_code VARCHAR(10),
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_auth_sessions_user FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
);

-- ===================================================================
-- 2. TỪ ĐIỂN NGÔN NGỮ KÝ HIỆU (SIGN LANGUAGE DICTIONARY)
-- ===================================================================

CREATE TABLE dictionary_categories (
    category_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT
);

CREATE TABLE dictionary_entries (
    entry_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    category_id INT NOT NULL,
    word VARCHAR(100) NOT NULL,
    meaning TEXT NOT NULL,
    CONSTRAINT fk_dict_entries_category FOREIGN KEY (category_id) REFERENCES dictionary_categories (category_id) ON DELETE RESTRICT
);

CREATE TABLE dictionary_variations (
    variation_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    entry_id UUID NOT NULL,
    region VARCHAR(100),
    video_url VARCHAR(255) NOT NULL,
    description TEXT,
    CONSTRAINT fk_dict_variations_entry FOREIGN KEY (entry_id) REFERENCES dictionary_entries (entry_id) ON DELETE CASCADE
);

-- ===================================================================
-- 3. KHÓA HỌC VĂN HÓA (GENERAL COURSE)
-- ===================================================================

CREATE TABLE general_course_categories (
    category_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL
);

CREATE TABLE general_courses (
    course_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    teacher_id UUID NOT NULL,
    category_id INT NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    visibility_status VARCHAR(20) DEFAULT 'DRAFT',
    CONSTRAINT fk_courses_teacher FOREIGN KEY (teacher_id) REFERENCES teachers (user_id) ON DELETE RESTRICT,
    CONSTRAINT fk_courses_category FOREIGN KEY (category_id) REFERENCES general_course_categories (category_id) ON DELETE RESTRICT
);

CREATE TABLE general_course_modules (
    module_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    course_id UUID NOT NULL,
    title VARCHAR(255) NOT NULL,
    order_index INT NOT NULL,
    CONSTRAINT fk_modules_course FOREIGN KEY (course_id) REFERENCES general_courses (course_id) ON DELETE CASCADE
);

CREATE TABLE general_course_lessons (
    lesson_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    module_id UUID NOT NULL,
    title VARCHAR(255) NOT NULL,
    order_index INT NOT NULL,
    CONSTRAINT fk_lessons_module FOREIGN KEY (module_id) REFERENCES general_course_modules (module_id) ON DELETE CASCADE
);

CREATE TABLE learning_materials (
    material_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    lesson_id UUID NOT NULL,
    title VARCHAR(255) NOT NULL,
    content_url VARCHAR(255) NOT NULL,
    material_transcript JSONB, -- Sử dụng JSONB cho PostgreSQL để lưu trữ config tối ưu hơn JSON thường
    CONSTRAINT fk_materials_lesson FOREIGN KEY (lesson_id) REFERENCES general_course_lessons (lesson_id) ON DELETE CASCADE
);

CREATE TABLE course_enrollments (
    enrollment_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    student_id UUID NOT NULL,
    course_id UUID NOT NULL,
    progress DECIMAL(5,2) DEFAULT 0.00,
    enrolled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_enrollments_student FOREIGN KEY (student_id) REFERENCES students (user_id) ON DELETE CASCADE,
    CONSTRAINT fk_enrollments_course FOREIGN KEY (course_id) REFERENCES general_courses (course_id) ON DELETE CASCADE
);

CREATE TABLE comments (
    comment_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    lesson_id UUID NOT NULL,
    user_id UUID NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_comments_lesson FOREIGN KEY (lesson_id) REFERENCES general_course_lessons (lesson_id) ON DELETE CASCADE,
    CONSTRAINT fk_comments_user FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
);

-- ===================================================================
-- 4. CHẾ ĐỘ MICROLEARNING (HỌC TẬP SIÊU NHỎ)
-- ===================================================================

CREATE TABLE microlearning_topics (
    topic_id SERIAL PRIMARY KEY,
    title VARCHAR(150) NOT NULL,
    description TEXT
);

CREATE TABLE microlearning_units (
    unit_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    topic_id INT NOT NULL,
    title VARCHAR(255) NOT NULL,
    order_index INT NOT NULL,
    CONSTRAINT fk_ml_units_topic FOREIGN KEY (topic_id) REFERENCES microlearning_topics (topic_id) ON DELETE CASCADE
);

CREATE TABLE microlearning_lessons (
    lesson_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    unit_id UUID NOT NULL,
    title VARCHAR(255) NOT NULL,
    order_index INT NOT NULL,
    CONSTRAINT fk_ml_lessons_unit FOREIGN KEY (unit_id) REFERENCES microlearning_units (unit_id) ON DELETE CASCADE
);

CREATE TABLE microlearning_lesson_parts (
    part_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    lesson_id UUID NOT NULL,
    title VARCHAR(255),
    part_type VARCHAR(50) NOT NULL,
    content TEXT,
    order_index INT NOT NULL,
    CONSTRAINT fk_ml_parts_lesson FOREIGN KEY (lesson_id) REFERENCES microlearning_lessons (lesson_id) ON DELETE CASCADE
);

CREATE TABLE microlearning_questions (
    question_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    part_id UUID NOT NULL,
    question_text TEXT NOT NULL,
    question_type VARCHAR(20) NOT NULL,
    options_json JSONB NOT NULL,
    correct_answer VARCHAR(255) NOT NULL,
    CONSTRAINT fk_ml_questions_part FOREIGN KEY (part_id) REFERENCES microlearning_lesson_parts (part_id) ON DELETE CASCADE
);

-- ===================================================================
-- 5. GAMIFICATION & TƯƠNG TÁC (GAMIFICATION & ENGAGEMENT)
-- ===================================================================

CREATE TABLE student_streaks (
    streak_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    student_id UUID NOT NULL UNIQUE,
    current_streak INT DEFAULT 0,
    highest_streak INT DEFAULT 0,
    last_activity_date DATE,
    CONSTRAINT fk_streaks_student FOREIGN KEY (student_id) REFERENCES students (user_id) ON DELETE CASCADE
);

CREATE TABLE achievements (
    achievement_id SERIAL PRIMARY KEY,
    title VARCHAR(100) NOT NULL,
    description TEXT NOT NULL,
    icon_url VARCHAR(255)
);

-- (Theo định nghĩa ban đầu, có thực thể user_achievements như một mapping table N-N, nhưng ở prompt 2 chưa có chi tiết, tôi bổ sung cho hợp lý dựa trên ERD)
CREATE TABLE user_achievements (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL,
    achievement_id INT NOT NULL,
    earned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_ua_user FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE,
    CONSTRAINT fk_ua_achievement FOREIGN KEY (achievement_id) REFERENCES achievements (achievement_id) ON DELETE CASCADE
);

CREATE TABLE user_feedbacks (
    feedback_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL,
    rating INT,
    feedback_text TEXT,
    context VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_feedbacks_user FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
);

CREATE TABLE notification_users (
    notification_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL,
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_notifications_user FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
);
