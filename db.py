import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "instance" / "cbc.db"


# -------------------------------------------------
# DB CONNECTION
# -------------------------------------------------
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# -------------------------------------------------
# INIT DATABASE
# -------------------------------------------------
def init_db():
    conn = get_db()
    cur = conn.cursor()

    # -------------------------------
    # TEACHERS TABLE
    # -------------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS teachers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            subject TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # -------------------------------
    # CLASSES TABLE (PHASE B1)
    # -------------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS classes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            subject TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (teacher_id) REFERENCES teachers(id)
        )
    """)

    # -------------------------------
    # LEARNERS TABLE (PHASE B2)
    # -------------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS learners (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            class_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (class_id) REFERENCES classes(id)
        )
    """)

    # -------------------------------
    # OBSERVATIONS TABLE
    # -------------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS observations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_id INTEGER NOT NULL,
            class_name TEXT NOT NULL,
            learner_id INTEGER NOT NULL,
            activity TEXT NOT NULL,
            skill TEXT NOT NULL,
            level TEXT NOT NULL,
            note TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (teacher_id) REFERENCES teachers(id),
            FOREIGN KEY (learner_id) REFERENCES learners(id)
        )
    """)

    conn.commit()
    conn.close()


# -------------------------------------------------
# TEACHERS
# -------------------------------------------------
def get_or_create_teacher(email, name, subject):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT id FROM teachers WHERE email = ?", (email,))
    row = cur.fetchone()

    if row:
        teacher_id = row["id"]
    else:
        cur.execute(
            "INSERT INTO teachers (email, name, subject) VALUES (?, ?, ?)",
            (email, name, subject)
        )
        conn.commit()
        teacher_id = cur.lastrowid

    conn.close()
    return teacher_id


# -------------------------------------------------
# CLASSES
# -------------------------------------------------
def seed_default_classes(teacher_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT COUNT(*) FROM classes WHERE teacher_id = ?",
        (teacher_id,)
    )
    count = cur.fetchone()[0]

    if count == 0:
        cur.executemany(
            "INSERT INTO classes (teacher_id, name, subject) VALUES (?, ?, ?)",
            [
                (teacher_id, "Grade 10 A", "Mathematics"),
                (teacher_id, "Grade 10 B", "Mathematics"),
                (teacher_id, "Grade 11 Science", "Mathematics"),
            ]
        )

    conn.commit()
    conn.close()


def get_classes_for_teacher(teacher_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT id, name, subject FROM classes WHERE teacher_id = ? ORDER BY name",
        (teacher_id,)
    )

    rows = cur.fetchall()
    conn.close()
    return rows


# -------------------------------------------------
# LEARNERS (PHASE B2)
# -------------------------------------------------
def seed_default_learners(class_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT COUNT(*) FROM learners WHERE class_id = ?",
        (class_id,)
    )
    count = cur.fetchone()[0]

    if count == 0:
        cur.executemany(
            "INSERT INTO learners (class_id, name) VALUES (?, ?)",
            [
                (class_id, "Faith Achieng"),
                (class_id, "Brian Kamau"),
                (class_id, "Mark Otieno"),
                (class_id, "Sarah Wanjiku"),
                (class_id, "John Mwangi"),
            ]
        )

    conn.commit()
    conn.close()


def get_learners_for_class(class_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT id, name FROM learners WHERE class_id = ? ORDER BY name",
        (class_id,)
    )

    rows = cur.fetchall()
    conn.close()
    return rows


# -------------------------------------------------
# OBSERVATIONS
# -------------------------------------------------
def save_observation(
    teacher_id,
    class_name,
    learner_id,
    activity,
    skill,
    level,
    note
):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO observations
        (teacher_id, class_name, learner_id, activity, skill, level, note)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (teacher_id, class_name, learner_id, activity, skill, level, note)
    )

    conn.commit()
    conn.close()


def get_recent_observations(teacher_id, limit=5):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            classes.name AS class_name,
            learners.name AS learner_name,
            observations.activity,
            observations.skill,
            observations.level,
            observations.note,
            observations.created_at
        FROM observations
        JOIN learners ON observations.learner_id = learners.id
        JOIN classes ON learners.class_id = classes.id
        WHERE observations.teacher_id = ?
        ORDER BY observations.created_at DESC
        LIMIT ?
    """, (teacher_id, limit))

    rows = cur.fetchall()
    conn.close()
    return rows

def get_all_observations(teacher_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            observations.created_at,
            classes.name AS class_name,
            learners.name AS learner_name,
            observations.activity,
            observations.skill,
            observations.level
        FROM observations
        JOIN learners ON observations.learner_id = learners.id
        JOIN classes ON learners.class_id = classes.id
        WHERE observations.teacher_id = ?
        ORDER BY observations.created_at DESC
    """, (teacher_id,))

    rows = cur.fetchall()
    conn.close()
    return rows




def get_weekly_summary(teacher_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            COUNT(*) as total_observations,
            COUNT(DISTINCT learner_id) as learners_count,
            COUNT(DISTINCT skill) as skills_count
        FROM observations
        WHERE teacher_id = ?
          AND date(created_at) >= date('now', '-7 days')
    """, (teacher_id,))

    row = cur.fetchone()
    conn.close()

    return {
        "total": row["total_observations"],
        "learners": row["learners_count"],
        "skills": row["skills_count"]
    }

def get_learner_with_class(learner_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT
            learners.id as learner_id,
            learners.name as learner_name,
            classes.name as class_name,
            classes.subject as subject
        FROM learners
        JOIN classes ON learners.class_id = classes.id
        WHERE learners.id = ?
        """,
        (learner_id,)
    )

    row = cur.fetchone()
    conn.close()
    return row
