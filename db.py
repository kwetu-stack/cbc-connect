import os
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
_default_db = BASE_DIR / "instance" / "cbc.db"
_env_db = os.getenv("CBC_DB_PATH")

# If the repo lives in OneDrive, SQLite locks are common. Prefer a local temp DB
# unless the user explicitly overrides via CBC_DB_PATH.
if _env_db:
    DB_PATH = Path(_env_db).expanduser()
else:
    repo_path_str = str(BASE_DIR)
    if "OneDrive" in repo_path_str or "onedrive" in repo_path_str.lower():
        tmp = os.getenv("TEMP") or os.getenv("TMP") or str(BASE_DIR / "instance")
        DB_PATH = Path(tmp) / "cbc-connect.db"
    else:
        DB_PATH = _default_db
DEMO_WRITE_BLOCKED = False

DEMO_TEACHER = {
    "email": "amina@school.test",
    "name": "Amina Hassan",
    "subject": "Mathematics",
}


# -------------------------------------------------
# DB CONNECTION
# -------------------------------------------------
def get_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    # SQLite can easily hit "database is locked" on Windows if multiple app
    # instances are running or a write is briefly contended. Use a longer timeout
    # plus busy_timeout/WAL to make writes more resilient for teacher workflows.
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA busy_timeout = 30000;")
    except sqlite3.OperationalError:
        # Some PRAGMAs can fail depending on environment; keep the app usable.
        pass
    return conn


def set_demo_write_blocked(blocked):
    global DEMO_WRITE_BLOCKED
    DEMO_WRITE_BLOCKED = blocked


def commit_if_allowed(conn, allow_in_demo=False):
    if DEMO_WRITE_BLOCKED and not allow_in_demo:
        conn.rollback()
        return False

    conn.commit()
    return True


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

    commit_if_allowed(conn, allow_in_demo=True)
    conn.close()


# -------------------------------------------------
# TEACHERS
# -------------------------------------------------
def get_or_create_teacher(email, name, subject, allow_in_demo=False):
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
        commit_if_allowed(conn, allow_in_demo=allow_in_demo)
        teacher_id = cur.lastrowid

    conn.close()
    return teacher_id


# -------------------------------------------------
# CLASSES
# -------------------------------------------------
def seed_default_classes(teacher_id, allow_in_demo=False):
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

    commit_if_allowed(conn, allow_in_demo=allow_in_demo)
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
def seed_default_learners(class_id, allow_in_demo=False):
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

    commit_if_allowed(conn, allow_in_demo=allow_in_demo)
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
    if DEMO_WRITE_BLOCKED:
        return False

    # Retry a couple times on transient SQLite locks (very common on Windows).
    for _ in range(3):
        conn = get_db()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                INSERT INTO observations
                (teacher_id, class_name, learner_id, activity, skill, level, note)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (teacher_id, class_name, learner_id, activity, skill, level, note),
            )
            ok = commit_if_allowed(conn)
            return ok
        except sqlite3.OperationalError as e:
            msg = str(e).lower()
            conn.rollback()
            if "locked" in msg or "busy" in msg:
                # brief backoff and retry
                import time

                time.sleep(0.2)
                continue
            raise
        finally:
            conn.close()

    return False


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

def _apply_observation_filters(base_sql, params, filters):
    if not filters:
        return base_sql, params

    sql = base_sql
    if filters.get("class_id"):
        sql += " AND classes.id = ?"
        params.append(filters["class_id"])
    if filters.get("learner_id"):
        sql += " AND learners.id = ?"
        params.append(filters["learner_id"])
    if filters.get("skill"):
        sql += " AND observations.skill = ?"
        params.append(filters["skill"])
    if filters.get("level"):
        sql += " AND observations.level = ?"
        params.append(filters["level"])
    if filters.get("from_date"):
        sql += " AND date(observations.created_at) >= date(?)"
        params.append(filters["from_date"])
    if filters.get("to_date"):
        sql += " AND date(observations.created_at) <= date(?)"
        params.append(filters["to_date"])

    return sql, params


def get_all_observations(teacher_id, filters=None):
    conn = get_db()
    cur = conn.cursor()

    base_sql = """
        SELECT
            observations.id,
            observations.created_at,
            classes.name AS class_name,
            learners.name AS learner_name,
            learners.id AS learner_id,
            observations.activity,
            observations.skill,
            observations.level,
            observations.note
        FROM observations
        JOIN learners ON observations.learner_id = learners.id
        JOIN classes ON learners.class_id = classes.id
        WHERE observations.teacher_id = ?
    """
    params = [teacher_id]
    sql, params = _apply_observation_filters(base_sql, params, filters)
    sql += " ORDER BY observations.created_at DESC"

    cur.execute(sql, params)
    rows = cur.fetchall()
    conn.close()
    return rows


def get_observation_by_id(teacher_id, observation_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT
            observations.id,
            observations.teacher_id,
            observations.learner_id,
            observations.activity,
            observations.skill,
            observations.level,
            observations.note,
            observations.created_at,
            learners.name AS learner_name,
            classes.name AS class_name
        FROM observations
        JOIN learners ON observations.learner_id = learners.id
        JOIN classes ON learners.class_id = classes.id
        WHERE observations.teacher_id = ?
          AND observations.id = ?
        """,
        (teacher_id, observation_id),
    )
    row = cur.fetchone()
    conn.close()
    return row


def update_observation(teacher_id, observation_id, activity, skill, level, note):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE observations
        SET activity = ?, skill = ?, level = ?, note = ?
        WHERE teacher_id = ? AND id = ?
        """,
        (activity, skill, level, note, teacher_id, observation_id),
    )
    commit_if_allowed(conn)
    conn.close()


def delete_observation(teacher_id, observation_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM observations WHERE teacher_id = ? AND id = ?",
        (teacher_id, observation_id),
    )
    commit_if_allowed(conn)
    conn.close()


def clear_observations_for_teacher(teacher_id, allow_in_demo=False):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM observations WHERE teacher_id = ?", (teacher_id,))
    commit_if_allowed(conn, allow_in_demo=allow_in_demo)
    conn.close()


def get_learner_summary(teacher_id, learner_id, filters=None):
    conn = get_db()
    cur = conn.cursor()

    base_sql = """
        SELECT
            COUNT(*) as total,
            COUNT(DISTINCT skill) as skills,
            SUM(CASE WHEN level = 'Doing well' THEN 1 ELSE 0 END) as doing_well,
            SUM(CASE WHEN level = 'Improving' THEN 1 ELSE 0 END) as improving,
            SUM(CASE WHEN level = 'Needs support' THEN 1 ELSE 0 END) as needs_support
        FROM observations
        JOIN learners ON observations.learner_id = learners.id
        JOIN classes ON learners.class_id = classes.id
        WHERE observations.teacher_id = ?
          AND learners.id = ?
    """
    params = [teacher_id, learner_id]
    sql, params = _apply_observation_filters(base_sql, params, filters)
    cur.execute(sql, params)
    row = cur.fetchone()
    conn.close()
    return {
        "total": row["total"] or 0,
        "skills": row["skills"] or 0,
        "doing_well": row["doing_well"] or 0,
        "improving": row["improving"] or 0,
        "needs_support": row["needs_support"] or 0,
    }




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
            classes.id as class_id,
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


def seed_sample_observations(teacher_id, allow_in_demo=False):
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        "SELECT COUNT(*) FROM observations WHERE teacher_id = ?",
        (teacher_id,)
    )
    count = cur.fetchone()[0]

    if count == 0:
        cur.execute(
            """
            SELECT learners.id, classes.name
            FROM learners
            JOIN classes ON learners.class_id = classes.id
            JOIN teachers ON classes.teacher_id = teachers.id
            WHERE teachers.id = ?
            ORDER BY classes.name, learners.name
            LIMIT 3
            """,
            (teacher_id,)
        )
        learners = cur.fetchall()

        if len(learners) == 3:
            cur.executemany(
                """
                INSERT INTO observations
                (teacher_id, class_name, learner_id, activity, skill, level, note)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        teacher_id,
                        learners[0]["name"],
                        learners[0]["id"],
                        "Group work",
                        "Collaboration",
                        "Doing well",
                        "Contributed ideas confidently during the task.",
                    ),
                    (
                        teacher_id,
                        learners[1]["name"],
                        learners[1]["id"],
                        "Written task",
                        "Critical thinking",
                        "Improving",
                        "Needed one prompt before solving independently.",
                    ),
                    (
                        teacher_id,
                        learners[2]["name"],
                        learners[2]["id"],
                        "Oral response",
                        "Communication",
                        "Doing well",
                        "Explained reasoning clearly to the class.",
                    ),
                ]
            )

    commit_if_allowed(conn, allow_in_demo=allow_in_demo)
    conn.close()


def ensure_demo_data():
    teacher_id = get_or_create_teacher(
        DEMO_TEACHER["email"],
        DEMO_TEACHER["name"],
        DEMO_TEACHER["subject"],
        allow_in_demo=True,
    )
    seed_default_classes(teacher_id, allow_in_demo=True)

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT id FROM classes WHERE teacher_id = ? ORDER BY name",
        (teacher_id,)
    )
    class_ids = [row["id"] for row in cur.fetchall()]
    conn.close()

    for class_id in class_ids:
        seed_default_learners(class_id, allow_in_demo=True)

    seed_sample_observations(teacher_id, allow_in_demo=True)
    return teacher_id
