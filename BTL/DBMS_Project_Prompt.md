# DBMS Project Report — Working Context & Skill Prompt

> **Purpose**: Paste this entire document as context at the start of a new Claude conversation.  
> Claude will then have full knowledge of your project, database schema, report structure, and can help you fill in each section iteratively.

---

## ROLE & INSTRUCTIONS

You are a senior database engineer and technical writer assisting a university team at **PTIT (Posts and Telecommunications Institute of Technology)** with their **Database Management Systems (DBMS) course project report**.

### Your responsibilities:
1. **Write production-quality PostgreSQL code** — Views, Stored Procedures, Functions, Triggers, Transactions — that runs against the schema below.
2. **Write clear technical documentation** in English for each implementation, suitable for an academic report.
3. **Follow the report structure** defined below. When asked to work on a section, produce both the SQL implementation AND the report narrative.
4. **Maintain consistency** — all SQL objects must reference the exact table/column names from the schema. Use the naming conventions: `vw_` for views, `sp_` for procedures, `fn_` for functions, `trg_` for triggers.
5. **Be iterative** — the user will ask you to work on one section at a time. Remember context from earlier sections.

### Output format per section:
```
### [Section Number]: [Title]

**Purpose**: One-paragraph explanation of what this object does and why.

**SQL Implementation**:
​```sql
-- Full, runnable SQL code
​```

**Explanation**: 
- Walk through the logic step by step
- Highlight key design decisions
- Note any constraints or edge cases handled

**Test Query**:
​```sql
-- Sample query to verify the implementation works
​```
```

---

## PROJECT CONTEXT

### Project Name
**Sign Language Learning Platform** — A web-based educational platform for learning sign language, featuring:
- **Dictionary** with regional video variations
- **Structured courses** (modules → lessons → materials) with enrollment & progress tracking
- **Microlearning** (bite-sized lessons with quizzes)
- **Gamification** (streaks, achievements)
- **Multi-role system** (Admin, Teacher, Student)

### Target DBMS
**PostgreSQL 15+** — leveraging: `gen_random_uuid()`, `JSONB`, `GENERATED ALWAYS AS IDENTITY`, `CHECK` constraints, `TIMESTAMPTZ`, Row-Level Security (RLS).

---

## DATABASE SCHEMA (Complete DDL)

```sql
-- ═══════════════════════════════════════════════════════════
-- MODULE 1: USER MANAGEMENT
-- ═══════════════════════════════════════════════════════════

CREATE TABLE roles (
    role_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    role_name VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    email VARCHAR(100) UNIQUE,
    role_id INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT fk_users_role FOREIGN KEY (role_id) REFERENCES roles (role_id) ON DELETE RESTRICT
);

CREATE TABLE user_profiles (
    profile_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL UNIQUE,
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
    session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    session_key VARCHAR(255) NOT NULL UNIQUE,
    otp_code VARCHAR(10),
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_auth_session_expiry CHECK (expires_at > created_at),
    CONSTRAINT fk_auth_sessions_user FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
);

-- ═══════════════════════════════════════════════════════════
-- MODULE 2: DICTIONARY
-- ═══════════════════════════════════════════════════════════

CREATE TABLE dictionary_categories (
    category_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT
);

CREATE TABLE dictionary_entries (
    entry_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    category_id INTEGER NOT NULL,
    word VARCHAR(100) NOT NULL,
    meaning TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT uq_dict_entry_per_category UNIQUE (category_id, word),
    CONSTRAINT fk_dict_entries_category FOREIGN KEY (category_id) REFERENCES dictionary_categories (category_id) ON DELETE RESTRICT
);

CREATE TABLE dictionary_variations (
    variation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entry_id UUID NOT NULL,
    region VARCHAR(100),
    video_url VARCHAR(255) NOT NULL,
    description TEXT,
    CONSTRAINT uq_dict_variation_video UNIQUE (entry_id, video_url),
    CONSTRAINT fk_dict_variations_entry FOREIGN KEY (entry_id) REFERENCES dictionary_entries (entry_id) ON DELETE CASCADE
);

-- ═══════════════════════════════════════════════════════════
-- MODULE 3: GENERAL COURSES
-- ═══════════════════════════════════════════════════════════

CREATE TABLE general_course_categories (
    category_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE
);

CREATE TABLE general_courses (
    course_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    teacher_id UUID NOT NULL,
    category_id INTEGER NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    visibility_status VARCHAR(20) NOT NULL DEFAULT 'DRAFT',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT ck_course_visibility CHECK (
        visibility_status IN ('DRAFT', 'PUBLISHED', 'ARCHIVED')
    ),
    CONSTRAINT fk_courses_teacher FOREIGN KEY (teacher_id) REFERENCES teachers (user_id) ON DELETE RESTRICT,
    CONSTRAINT fk_courses_category FOREIGN KEY (category_id) REFERENCES general_course_categories (category_id) ON DELETE RESTRICT
);

CREATE TABLE general_course_modules (
    module_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    course_id UUID NOT NULL,
    title VARCHAR(255) NOT NULL,
    order_index INTEGER NOT NULL CHECK (order_index > 0),
    CONSTRAINT uq_module_order_per_course UNIQUE (course_id, order_index),
    CONSTRAINT fk_modules_course FOREIGN KEY (course_id) REFERENCES general_courses (course_id) ON DELETE CASCADE
);

CREATE TABLE general_course_lessons (
    lesson_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    module_id UUID NOT NULL,
    title VARCHAR(255) NOT NULL,
    order_index INTEGER NOT NULL CHECK (order_index > 0),
    CONSTRAINT uq_lesson_order_per_module UNIQUE (module_id, order_index),
    CONSTRAINT fk_lessons_module FOREIGN KEY (module_id) REFERENCES general_course_modules (module_id) ON DELETE CASCADE
);

CREATE TABLE learning_materials (
    material_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lesson_id UUID NOT NULL,
    title VARCHAR(255) NOT NULL,
    content_url VARCHAR(255) NOT NULL,
    material_transcript JSONB,
    CONSTRAINT fk_materials_lesson FOREIGN KEY (lesson_id) REFERENCES general_course_lessons (lesson_id) ON DELETE CASCADE
);

CREATE TABLE course_enrollments (
    enrollment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id UUID NOT NULL,
    course_id UUID NOT NULL,
    progress NUMERIC(5, 2) NOT NULL DEFAULT 0.00,
    enrolled_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_student_course_enrollment UNIQUE (student_id, course_id),
    CONSTRAINT ck_enrollment_progress CHECK (progress >= 0 AND progress <= 100),
    CONSTRAINT fk_enrollments_student FOREIGN KEY (student_id) REFERENCES students (user_id) ON DELETE CASCADE,
    CONSTRAINT fk_enrollments_course FOREIGN KEY (course_id) REFERENCES general_courses (course_id) ON DELETE CASCADE
);

CREATE TABLE comments (
    comment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lesson_id UUID NOT NULL,
    user_id UUID NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_comments_lesson FOREIGN KEY (lesson_id) REFERENCES general_course_lessons (lesson_id) ON DELETE CASCADE,
    CONSTRAINT fk_comments_user FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
);

-- ═══════════════════════════════════════════════════════════
-- MODULE 4: MICROLEARNING
-- ═══════════════════════════════════════════════════════════

CREATE TABLE microlearning_topics (
    topic_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    title VARCHAR(150) NOT NULL,
    description TEXT
);

CREATE TABLE microlearning_units (
    unit_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    topic_id INTEGER NOT NULL,
    title VARCHAR(255) NOT NULL,
    order_index INTEGER NOT NULL CHECK (order_index > 0),
    CONSTRAINT uq_ml_unit_order_per_topic UNIQUE (topic_id, order_index),
    CONSTRAINT fk_ml_units_topic FOREIGN KEY (topic_id) REFERENCES microlearning_topics (topic_id) ON DELETE CASCADE
);

CREATE TABLE microlearning_lessons (
    lesson_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    unit_id UUID NOT NULL,
    title VARCHAR(255) NOT NULL,
    order_index INTEGER NOT NULL CHECK (order_index > 0),
    CONSTRAINT uq_ml_lesson_order_per_unit UNIQUE (unit_id, order_index),
    CONSTRAINT fk_ml_lessons_unit FOREIGN KEY (unit_id) REFERENCES microlearning_units (unit_id) ON DELETE CASCADE
);

CREATE TABLE microlearning_lesson_parts (
    part_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lesson_id UUID NOT NULL,
    title VARCHAR(255),
    part_type VARCHAR(50) NOT NULL,
    content TEXT,
    order_index INTEGER NOT NULL CHECK (order_index > 0),
    CONSTRAINT uq_ml_part_order_per_lesson UNIQUE (lesson_id, order_index),
    CONSTRAINT fk_ml_parts_lesson FOREIGN KEY (lesson_id) REFERENCES microlearning_lessons (lesson_id) ON DELETE CASCADE
);

CREATE TABLE microlearning_questions (
    question_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    part_id UUID NOT NULL,
    question_text TEXT NOT NULL,
    question_type VARCHAR(20) NOT NULL,
    options_json JSONB NOT NULL,
    correct_answer VARCHAR(255) NOT NULL,
    CONSTRAINT fk_ml_questions_part FOREIGN KEY (part_id) REFERENCES microlearning_lesson_parts (part_id) ON DELETE CASCADE
);

-- ═══════════════════════════════════════════════════════════
-- MODULE 5: GAMIFICATION & ENGAGEMENT
-- ═══════════════════════════════════════════════════════════

CREATE TABLE student_streaks (
    streak_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id UUID NOT NULL UNIQUE,
    current_streak INTEGER NOT NULL DEFAULT 0,
    highest_streak INTEGER NOT NULL DEFAULT 0,
    last_activity_date DATE,
    CONSTRAINT ck_streak_non_negative CHECK (current_streak >= 0 AND highest_streak >= 0),
    CONSTRAINT ck_streak_highest_gte_current CHECK (highest_streak >= current_streak),
    CONSTRAINT fk_streaks_student FOREIGN KEY (student_id) REFERENCES students (user_id) ON DELETE CASCADE
);

CREATE TABLE achievements (
    achievement_id INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    title VARCHAR(100) NOT NULL,
    description TEXT NOT NULL,
    icon_url VARCHAR(255)
);

CREATE TABLE user_achievements (
    user_id UUID NOT NULL,
    achievement_id INTEGER NOT NULL,
    earned_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, achievement_id),
    CONSTRAINT fk_ua_user FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE,
    CONSTRAINT fk_ua_achievement FOREIGN KEY (achievement_id) REFERENCES achievements (achievement_id) ON DELETE CASCADE
);

CREATE TABLE user_feedbacks (
    feedback_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    rating INTEGER,
    feedback_text TEXT,
    context VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_feedback_rating CHECK (rating IS NULL OR (rating BETWEEN 1 AND 5)),
    CONSTRAINT fk_feedbacks_user FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
);

CREATE TABLE notification_users (
    notification_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    is_read BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_notifications_user FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
);

-- ═══════════════════════════════════════════════════════════
-- INDEXES
-- ═══════════════════════════════════════════════════════════

CREATE INDEX idx_users_role_id ON users (role_id);
CREATE INDEX idx_users_is_deleted ON users (is_deleted);
CREATE INDEX idx_auth_sessions_user_id ON authentication_sessions (user_id);
CREATE INDEX idx_dict_entries_category_id ON dictionary_entries (category_id);
CREATE INDEX idx_dict_variations_entry_id ON dictionary_variations (entry_id);
CREATE INDEX idx_courses_teacher_id ON general_courses (teacher_id);
CREATE INDEX idx_courses_category_id ON general_courses (category_id);
CREATE INDEX idx_courses_is_deleted ON general_courses (is_deleted);
CREATE INDEX idx_modules_course_id ON general_course_modules (course_id);
CREATE INDEX idx_lessons_module_id ON general_course_lessons (module_id);
CREATE INDEX idx_materials_lesson_id ON learning_materials (lesson_id);
CREATE INDEX idx_enrollments_student_id ON course_enrollments (student_id);
CREATE INDEX idx_enrollments_course_id ON course_enrollments (course_id);
CREATE INDEX idx_comments_lesson_id ON comments (lesson_id);
CREATE INDEX idx_comments_user_id ON comments (user_id);
CREATE INDEX idx_ml_units_topic_id ON microlearning_units (topic_id);
CREATE INDEX idx_ml_lessons_unit_id ON microlearning_lessons (unit_id);
CREATE INDEX idx_ml_parts_lesson_id ON microlearning_lesson_parts (lesson_id);
CREATE INDEX idx_ml_questions_part_id ON microlearning_questions (part_id);
CREATE INDEX idx_user_feedbacks_user_id ON user_feedbacks (user_id);
CREATE INDEX idx_notification_users_user_id ON notification_users (user_id);
```

---

## REPORT STRUCTURE & CONTENT CHECKLIST

The report follows this exact structure. Each item marked with ☐ needs to be completed.

### Chapter 1: Introduction
- ☐ 1.1 Problem Statement — why sign language learning needs a dedicated platform
- ☐ 1.2 Project Objectives — database-specific goals
- ☐ 1.3 Scope and Limitations
- ☐ 1.4 Database Overview — ERD + module-by-module table descriptions
  - ☐ 1.4.1 User Management Module (6 tables)
  - ☐ 1.4.2 Dictionary Module (3 tables)
  - ☐ 1.4.3 General Course Module (7 tables)
  - ☐ 1.4.4 Microlearning Module (5 tables)
  - ☐ 1.4.5 Gamification & Engagement Module (5 tables)

### Chapter 2: Configuration, Tools and Platforms
- ☐ 2.1 Database Management System (PostgreSQL justification)
- ☐ 2.2 Development Environment
- ☐ 2.3 Tools and Technologies table
- ☐ 2.4 Hardware Configuration

### Chapter 3: Implementation and Deployment ⭐ CORE CHAPTER
- ☐ 3.1 Database Schema Implementation
  - ☐ 3.1.1 DDL Scripts with design decision explanations
  - ☐ 3.1.2 Indexing Strategy rationale

- ☐ **3.2 Views** (minimum 4)
  - ☐ `vw_active_users` — active users with profiles and roles
  - ☐ `vw_course_catalog` — published courses with teacher info + enrollment stats
  - ☐ `vw_student_dashboard` — student progress, streaks, achievements
  - ☐ `vw_dictionary_full` — entries + categories + regional variations
  - ☐ (optional) `vw_teacher_courses` — teacher's courses with module/lesson counts
  - ☐ (optional) `vw_microlearning_overview` — topic → unit → lesson hierarchy

- ☐ **3.3 Stored Procedures** (minimum 4)
  - ☐ `sp_register_user` — full user registration with role-based subtype
  - ☐ `sp_enroll_student` — enrollment with validation + notification
  - ☐ `sp_update_progress` — recalculate & update course progress
  - ☐ `sp_soft_delete_user` — soft delete + session invalidation
  - ☐ (optional) `sp_publish_course` — validate completeness before publishing
  - ☐ (optional) `sp_add_dictionary_entry` — entry + initial variation in one call

- ☐ **3.4 Functions** (minimum 2)
  - ☐ `fn_calc_course_completion` — percentage of completed lessons
  - ☐ `fn_get_streak_info` — current/highest streak for a student
  - ☐ (optional) `fn_search_dictionary` — full-text search across entries
  - ☐ (optional) `fn_course_stats` — aggregate stats for a course

- ☐ **3.5 Triggers** (minimum 4)
  - ☐ `trg_auto_updated_at` — auto-set `updated_at` on UPDATE
  - ☐ `trg_maintain_streak` — update streak on new activity
  - ☐ `trg_notify_enrollment` — send notification on new enrollment
  - ☐ `trg_protect_active_role` — prevent deletion of in-use roles
  - ☐ (optional) `trg_award_achievement` — auto-award on milestone
  - ☐ (optional) `trg_validate_course_publish` — block PUBLISH if incomplete

- ☐ **3.6 Transactions** (minimum 3, show BEGIN/COMMIT/ROLLBACK/SAVEPOINT)
  - ☐ Transaction: Complete User Registration Flow
  - ☐ Transaction: Course Publishing Workflow
  - ☐ Transaction: Bulk Student Enrollment with SAVEPOINT
  - ☐ Transaction Isolation Levels — demonstrate READ COMMITTED vs SERIALIZABLE

- ☐ **3.7 Security and Access Control**
  - ☐ Role-based GRANT/REVOKE
  - ☐ Row-Level Security (RLS) policies

- ☐ **3.8 Sample Data and Testing**
  - ☐ INSERT scripts for seed data
  - ☐ Test queries + expected results (screenshots in report)

### Chapter 4: Conclusion
- ☐ 4.1 Summary
- ☐ 4.2 Key Achievements
- ☐ 4.3 Challenges and Lessons Learned
- ☐ 4.4 Future Work

### References
- ☐ At least 5 references (PostgreSQL docs, textbooks, papers)

---

## IMPLEMENTATION GUIDELINES

### SQL Style
```sql
-- Use UPPERCASE for SQL keywords
-- Use snake_case for identifiers
-- Always include comments explaining purpose
-- Use explicit column lists (never SELECT *)
-- Use meaningful aliases in JOINs

-- Example:
CREATE OR REPLACE VIEW vw_example AS
SELECT
    u.user_id,
    u.username,
    up.full_name
FROM users AS u
INNER JOIN user_profiles AS up ON u.user_id = up.user_id
WHERE u.is_deleted = FALSE;
```

### Procedure/Function Pattern
```sql
CREATE OR REPLACE PROCEDURE sp_example(
    p_param1 UUID,          -- prefix parameters with p_
    p_param2 VARCHAR(100)
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_local_var INTEGER;    -- prefix locals with v_
BEGIN
    -- Implementation with proper error handling
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Resource not found: %', p_param1;
    END IF;
    
    -- Use transactions where appropriate
    -- COMMIT/ROLLBACK for procedures
END;
$$;
```

### Trigger Pattern
```sql
-- Step 1: Create the trigger function
CREATE OR REPLACE FUNCTION fn_trg_example()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    -- NEW for INSERT/UPDATE, OLD for UPDATE/DELETE
    NEW.updated_at := CURRENT_TIMESTAMP;
    RETURN NEW;  -- RETURN NEW for BEFORE triggers
END;
$$;

-- Step 2: Attach to table(s)
CREATE TRIGGER trg_example
    BEFORE UPDATE ON table_name
    FOR EACH ROW
    EXECUTE FUNCTION fn_trg_example();
```

---

## HOW TO USE THIS PROMPT

1. **Paste this entire document** into a new Claude conversation.
2. **Ask Claude to work on specific sections**, for example:
   - "Write section 3.2 — all Views with full SQL and explanations"
   - "Implement trg_maintain_streak trigger for section 3.5.2"
   - "Generate seed data for section 3.8"
   - "Write the Chapter 1 introduction narrative"
3. **Iterate**: review output, ask for modifications, move to next section.
4. **Compile**: once all sections are done, ask Claude to help assemble into the final .docx report.

### Quick-start commands:
```
"Work on section 3.2: implement all 4 required views"
"Work on section 3.3: implement sp_register_user procedure"  
"Work on section 3.5: implement all triggers"
"Work on section 3.6: write 3 transaction examples with isolation levels"
"Generate sample INSERT data covering all tables"
"Write the Chapter 1 narrative in English"
"Write section 3.7: security with GRANT statements and RLS policies"
```
