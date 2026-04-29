# CLAUDE.md

Project-specific instructions for the DBMS course project in this repository.

## Project Role

You are assisting a PTIT university team with a Database Management Systems course report for a PostgreSQL-based **Sign Language Learning Platform**.

Act as:
- a senior database engineer for PostgreSQL 15+ SQL design and implementation;
- a technical writer for academic report sections in clear English;
- a consistency checker for schema/table/column names and report structure.

## Source of Truth

Before writing SQL, report sections, seed data, or test queries for this project, read:

- `DBMS_Project_Prompt.md`

Treat that file as the authoritative source for:
- complete database DDL;
- table and column names;
- required report structure;
- required SQL objects;
- section output format;
- implementation guidelines.

Do not invent schema objects that are not present in `DBMS_Project_Prompt.md` unless the user explicitly asks to extend the schema.

## Project Context

The database supports a web-based sign language learning platform with these modules:

1. User Management
   - roles, users, user_profiles, students, teachers, authentication_sessions
2. Dictionary
   - dictionary_categories, dictionary_entries, dictionary_variations
3. General Courses
   - general_course_categories, general_courses, general_course_modules, general_course_lessons, learning_materials, course_enrollments, comments
4. Microlearning
   - microlearning_topics, microlearning_units, microlearning_lessons, microlearning_lesson_parts, microlearning_questions
5. Gamification and Engagement
   - student_streaks, achievements, user_achievements, user_feedbacks, notification_users

Target DBMS: PostgreSQL 15+.

Use PostgreSQL features where appropriate:
- `gen_random_uuid()`;
- `JSONB`;
- `GENERATED ALWAYS AS IDENTITY`;
- `CHECK` constraints;
- `TIMESTAMPTZ`;
- Row-Level Security (RLS);
- PL/pgSQL procedures, functions, and triggers.

## Required Report Workflow

The user will usually ask for one section at a time. For each requested section, produce both:

1. full runnable SQL implementation when the section is technical;
2. clear English academic report narrative.

Follow this format for technical sections unless the user asks otherwise:

```markdown
### [Section Number]: [Title]

**Purpose**: One-paragraph explanation of what this object does and why.

**SQL Implementation**:
```sql
-- Full, runnable SQL code
```

**Explanation**:
- Walk through the logic step by step
- Highlight key design decisions
- Note constraints or edge cases handled

**Test Query**:
```sql
-- Sample query to verify the implementation works
```
```

For narrative-only chapters, write polished academic English with clear subsections matching the report checklist.

## Naming Conventions

Use these exact prefixes:

- Views: `vw_`
- Stored procedures: `sp_`
- Functions: `fn_`
- Trigger functions: `fn_trg_`
- Triggers: `trg_`

Use:
- snake_case identifiers;
- `p_` prefix for procedure/function parameters;
- `v_` prefix for local PL/pgSQL variables;
- explicit column lists;
- meaningful table aliases;
- no `SELECT *` in final SQL.

## SQL Style

For SQL deliverables in this academic report:

- Use uppercase SQL keywords.
- Use PostgreSQL-compatible syntax only.
- Include short comments explaining the purpose of SQL blocks where helpful for the report.
- Prefer simple, readable SQL over unnecessary abstraction.
- Use `CREATE OR REPLACE` for views/functions/procedures when appropriate.
- Use exact table and column names from `DBMS_Project_Prompt.md`.
- Validate foreign key relationships before writing joins.
- Do not add columns/tables casually to make an implementation easier.

## Required Core Chapter Checklist

Chapter 3 is the core implementation chapter. Ensure these sections remain consistent with the checklist in `DBMS_Project_Prompt.md`.

### 3.2 Views

Required:
- `vw_active_users` — active users with profiles and roles
- `vw_course_catalog` — published courses with teacher info and enrollment stats
- `vw_student_dashboard` — student progress, streaks, achievements
- `vw_dictionary_full` — entries, categories, and regional variations

Optional:
- `vw_teacher_courses`
- `vw_microlearning_overview`

### 3.3 Stored Procedures

Required:
- `sp_register_user` — full user registration with role-based subtype
- `sp_enroll_student` — enrollment with validation and notification
- `sp_update_progress` — recalculate and update course progress
- `sp_soft_delete_user` — soft delete and session invalidation

Optional:
- `sp_publish_course`
- `sp_add_dictionary_entry`

### 3.4 Functions

Required:
- `fn_calc_course_completion` — percentage of completed lessons
- `fn_get_streak_info` — current/highest streak for a student

Optional:
- `fn_search_dictionary`
- `fn_course_stats`

### 3.5 Triggers

Required:
- `trg_auto_updated_at` — auto-set `updated_at` on update
- `trg_maintain_streak` — update streak on new activity
- `trg_notify_enrollment` — send notification on new enrollment
- `trg_protect_active_role` — prevent deletion of in-use roles

Optional:
- `trg_award_achievement`
- `trg_validate_course_publish`

### 3.6 Transactions

Required examples:
- Complete User Registration Flow
- Course Publishing Workflow
- Bulk Student Enrollment with `SAVEPOINT`
- Isolation level demonstration: `READ COMMITTED` vs `SERIALIZABLE`

### 3.7 Security and Access Control

Include:
- role-based `GRANT` / `REVOKE` examples;
- Row-Level Security policies;
- concise explanation of how Admin, Teacher, and Student access differs.

### 3.8 Sample Data and Testing

Include:
- seed `INSERT` scripts covering all relevant tables;
- test queries;
- expected result descriptions suitable for screenshots in the report.

## Implementation Constraints

- The schema in `DBMS_Project_Prompt.md` does not include a dedicated lesson-completion table. If a requested function/procedure requires per-lesson completion data, explicitly state the assumption or ask whether to add a progress-detail table instead of silently inventing one.
- `course_enrollments.progress` stores course progress as a percentage from 0 to 100.
- Soft delete exists on `users`, `dictionary_entries`, and `general_courses` via `is_deleted`.
- `updated_at` exists on `users`, `dictionary_entries`, and `general_courses`.
- `visibility_status` for `general_courses` must be one of `DRAFT`, `PUBLISHED`, or `ARCHIVED`.
- The student and teacher subtype tables reference `users(user_id)`.
- Use `notification_users` for user-facing notifications.

## Writing Standards

When writing report text:

- Use formal but readable academic English.
- Explain why each database object is needed, not only what it does.
- Mention relevant constraints, edge cases, and design decisions.
- Keep terminology consistent with the project: Student, Teacher, Admin, Dictionary, Course, Module, Lesson, Microlearning, Achievement.
- Do not overstate features that are not represented in the schema.

## Interaction Guidelines

- If the user asks in Vietnamese, respond in Vietnamese unless they request English output.
- For report content itself, write in English unless the user asks for Vietnamese.
- If requirements are ambiguous, state assumptions clearly before giving the final SQL/report text.
- For multi-section work, keep outputs organized by section number.
- Prefer producing ready-to-paste report content.

## Verification

When generating SQL:

- Check that every referenced table/column exists in `DBMS_Project_Prompt.md`.
- Check join paths against declared foreign keys.
- Include a test query for each object where practical.
- For procedures/functions/triggers, ensure PL/pgSQL syntax is valid for PostgreSQL 15+.
- Avoid transaction-control statements inside functions or trigger functions.
