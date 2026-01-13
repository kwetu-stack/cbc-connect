import sqlite3
from pathlib import Path
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "instance" / "cbc.db"


# -------------------------------------------------
# DB CONNECTION
# -------------------------------------------------
def get_db():
    # ensure instance directory exists before creating DB file
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
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

    # -------------------------------------------------
    # SOFT DELETE SUPPORT (PHASE 6C-0)
    # -------------------------------------------------
    cur.execute("PRAGMA table_info(observations)")
    columns = [row["name"] for row in cur.fetchall()]

    if "is_deleted" not in columns:
        cur.execute("""
            ALTER TABLE observations
            ADD COLUMN is_deleted INTEGER DEFAULT 0
        """)

    # -------------------------------
    # USERS TABLE (SECURITY CORE)
    # -------------------------------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('teacher', 'principal')),
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # -------------------------------
    # SEED DATA (AFTER ALL TABLES)
    # -------------------------------
    seed_default_users()
    seed_demo_teachers()
    seed_demo_classes()
    seed_demo_learners()

    conn.commit()
    conn.close()


# -------------------------------------------------
# DEMO DATA — CLASSES (PHASE 3B-2)
# -------------------------------------------------
def seed_demo_classes():
    """
    Seeds Grade 10 senior school classes per teacher.
    CBC-aligned, idempotent, safe to rerun.
    """

    demo_classes = {
        "amina@school.test": [
            ("Grade 10 A", "Mathematics"),
            ("Grade 10 B", "Mathematics"),
        ],
        "brian@school.test": [
            ("Grade 10 C", "English"),
            ("Grade 10 D", "English"),
        ],
        "grace@school.test": [
            ("Grade 10 E", "Biology"),
            ("Grade 10 F", "Biology"),
        ],
        "peter@school.test": [
            ("Grade 10 G", "History"),
            ("Grade 10 H", "History"),
        ],
    }

    conn = get_db()
    cur = conn.cursor()

    for email, classes in demo_classes.items():
        cur.execute("SELECT id FROM teachers WHERE email = ?", (email,))
        teacher = cur.fetchone()

        if not teacher:
            continue

        teacher_id = teacher["id"]

        for class_name, subject in classes:
            cur.execute(
                """
                SELECT id FROM classes
                WHERE teacher_id = ? AND name = ?
                """,
                (teacher_id, class_name)
            )

            if not cur.fetchone():
                cur.execute(
                    """
                    INSERT INTO classes (teacher_id, name, subject)
                    VALUES (?, ?, ?)
                    """,
                    (teacher_id, class_name, subject)
                )


# -------------------------------------------------
# DEMO DATA — LEARNERS (PHASE 3B-3)
# -------------------------------------------------
def seed_demo_learners():
    """
    Seeds learners per Grade 10 class.
    Idempotent, deterministic, CBC-aligned.
    """

    # 12 learners per class
    learners_by_class = {
        "Grade 10 A": [
            "Brian Kamau", "Faith Achieng", "John Mwangi", "Sarah Wanjiku",
            "Mark Otieno", "Lucy Njeri", "Daniel Kiptoo", "Mercy Atieno",
            "Kevin Mutua", "Ann Wambui", "Peter Ouma", "Joyce Chebet",
        ],
        "Grade 10 B": [
            "Samuel Kariuki", "Grace Muthoni", "Allan Kiplagat", "Ruth Nyambura",
            "Dennis Onyango", "Emily Wairimu", "Victor Rotich", "Janet Auma",
            "Paul Maina", "Beatrice Wangari", "Caleb Bett", "Ivy Nasimiyu",
        ],
        "Grade 10 C": [
            "Joseph Karanja", "Mary Wambui", "Elijah Kiplangat", "Naomi Atieno",
            "Brian Otieno", "Esther Naliaka", "George Muriuki", "Susan Chepkemoi",
            "Isaac Mutiso", "Lydia Wanjiru", "Michael Odhiambo", "Nancy Jepchirchir",
        ],
        "Grade 10 D": [
            "David Njoroge", "Cynthia Wairimu", "Kelvin Cheruiyot", "Purity Achieng",
            "Timothy Mwangi", "Alice Kendi", "Ronald Barasa", "Hellen Chebet",
            "Patrick Ochieng", "Florence Wambui", "Stephen Rono", "Agnes Nasenya",
        ],
        "Grade 10 E": [
            "Brian Oloo", "Veronica Auma", "Nicholas Kimani", "Sharon Wanjala",
            "James Kiprono", "Brenda Wanjiru", "Eric Mumo", "Joyce Atieno",
            "Felix Kibet", "Linda Muthoni", "Noah Omondi", "Rose Chepkoech",
        ],
        "Grade 10 F": [
            "Alex Mutua", "Mercy Wanjiru", "Calvin Bett", "Faith Chebet",
            "Oscar Onyango", "Dorcas Njeri", "Andrew Kipsang", "Tracy Akinyi",
            "Kennedy Kariuki", "Pauline Wangui", "Victor Kiptoo", "Stella Jepkemoi",
        ],
        "Grade 10 G": [
            "Daniel Kiplimo", "Hannah Chepkirui", "Simon Mwiti", "Rachel Wambui",
            "Martin Odongo", "Lucy Achieng", "Dennis Karanja", "Beatrice Auma",
            "Allan Mutiso", "Nancy Wairimu", "Isaiah Kiprotich", "Jane Chepchirchir",
        ],
        "Grade 10 H": [
            "George Otieno", "Elizabeth Atieno", "Wilson Njoroge", "Joy Damaris",
            "Kevin Kinyua", "Susan Wangari", "Emmanuel Barasa", "Mercy Naliaka",
            "Collins Ouma", "Agnes Muthoni", "Brian Kiplangat", "Eunice Jepkoech",
        ],
    }

    conn = get_db()
    cur = conn.cursor()

    for class_name, learners in learners_by_class.items():
        # Find class id
        cur.execute("SELECT id FROM classes WHERE name = ?", (class_name,))
        class_row = cur.fetchone()
        if not class_row:
            continue

        class_id = class_row["id"]

        for learner_name in learners:
            cur.execute(
                """
                SELECT id FROM learners
                WHERE class_id = ? AND name = ?
                """,
                (class_id, learner_name)
            )
            if not cur.fetchone():
                cur.execute(
                    """
                    INSERT INTO learners (class_id, name)
                    VALUES (?, ?)
                    """,
                    (class_id, learner_name)
                )

    # ❗ No commit / close here (init_db controls lifecycle)


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
# TEACHERS (READ-ONLY — PRINCIPAL)
# -------------------------------------------------
def get_all_teachers():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, name, email, subject
        FROM teachers
        ORDER BY name
    """)

    rows = cur.fetchall()
    conn.close()
    return rows

# -------------------------------------------------
# PRINCIPAL — READ-ONLY HELPERS
# -------------------------------------------------
def get_teacher_by_id(teacher_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, name, email, subject
        FROM teachers
        WHERE id = ?
    """, (teacher_id,))

    row = cur.fetchone()
    conn.close()
    return row

def get_principal_teacher_summary(teacher_id):
    conn = get_db()
    cur = conn.cursor()

    # Total learners across all classes
    cur.execute("""
        SELECT COUNT(learners.id) AS total_learners
        FROM classes
        LEFT JOIN learners ON learners.class_id = classes.id
        WHERE classes.teacher_id = ?
    """, (teacher_id,))
    total_learners = cur.fetchone()["total_learners"]

    # Total observations (all-time)
    cur.execute("""
        SELECT COUNT(*) AS total_observations
        FROM observations
        WHERE teacher_id = ?
    """, (teacher_id,))
    total_observations = cur.fetchone()["total_observations"]

    # Observations in last 7 days
    cur.execute("""
        SELECT COUNT(*) AS observations_last_7_days
        FROM observations
        WHERE teacher_id = ?
          AND date(created_at) >= date('now', '-7 days')
    """, (teacher_id,))
    last_7_days = cur.fetchone()["observations_last_7_days"]

    conn.close()
    return {
        "total_learners": total_learners or 0,
        "total_observations": total_observations or 0,
        "observations_last_7_days": last_7_days or 0,
    }



def get_classes_for_teacher_readonly(teacher_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, name, subject
        FROM classes
        WHERE teacher_id = ?
        ORDER BY name
    """, (teacher_id,))

    rows = cur.fetchall()
    conn.close()
    return rows


def get_observations_for_teacher_readonly(teacher_id, limit=100):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            observations.created_at,
            classes.name AS class_name,
            learners.name AS learner_name,
            observations.activity,
            observations.skill,
            observations.level,
            observations.note
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

# -------------------------------------------------
# OBSERVATIONS — EDIT HELPERS (PHASE 6B)
# -------------------------------------------------

def get_observation_by_id(observation_id, teacher_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            o.id,
            o.activity,
            o.skill,
            o.level,
            o.note,
            l.name AS learner_name,
            c.name AS class_name
        FROM observations o
        JOIN learners l ON o.learner_id = l.id
        JOIN classes c ON l.class_id = c.id
        WHERE o.id = ?
          AND o.teacher_id = ?
          AND o.is_deleted = 0
    """, (observation_id, teacher_id))

    row = cur.fetchone()
    conn.close()
    return row


def update_observation(observation_id, teacher_id, activity, skill, level, note):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        UPDATE observations
        SET activity = ?,
            skill = ?,
            level = ?,
            note = ?
        WHERE id = ?
          AND teacher_id = ?
          AND is_deleted = 0
    """, (activity, skill, level, note, observation_id, teacher_id))

    conn.commit()
    conn.close()



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
# PRINCIPAL HELPERS (READ-ONLY)
# -------------------------------------------------
def get_classes_with_learner_counts_for_teacher(teacher_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            classes.id,
            classes.name,
            classes.subject,
            COUNT(learners.id) AS learner_count
        FROM classes
        LEFT JOIN learners ON learners.class_id = classes.id
        WHERE classes.teacher_id = ?
        GROUP BY classes.id
        ORDER BY classes.name
    """, (teacher_id,))

    rows = cur.fetchall()
    conn.close()
    return rows
def get_principal_dashboard_summary():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM teachers")
    total_teachers = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM learners")
    total_learners = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM observations")
    total_observations = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*) FROM observations
        WHERE created_at >= datetime('now', '-7 days')
    """)
    observations_last_7_days = cur.fetchone()[0]

    cur.execute("""
        SELECT t.name, COUNT(o.id) AS total
        FROM observations o
        JOIN teachers t ON o.teacher_id = t.id
        WHERE o.created_at >= datetime('now', '-7 days')
        GROUP BY t.id
        ORDER BY total DESC
        LIMIT 1
    """)
    most_active_teacher = cur.fetchone()

    conn.close()

    return {
        "total_teachers": total_teachers,
        "total_learners": total_learners,
        "total_observations": total_observations,
        "observations_last_7_days": observations_last_7_days,
        "most_active_teacher": most_active_teacher
    }




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
            observations.id AS id,
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
          AND observations.is_deleted = 0
        ORDER BY observations.created_at DESC
    """, (teacher_id,))

    rows = cur.fetchall()
    conn.close()
    return rows

def soft_delete_observation(observation_id, teacher_id):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        UPDATE observations
        SET is_deleted = 1
        WHERE id = ?
          AND teacher_id = ?
    """, (observation_id, teacher_id))

    conn.commit()
    conn.close()



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
            learners.id        AS learner_id,
            learners.class_id  AS class_id,
            learners.name      AS learner_name,
            classes.name       AS class_name,
            classes.subject    AS subject
        FROM learners
        JOIN classes ON learners.class_id = classes.id
        WHERE learners.id = ?
        """,
        (learner_id,)
    )

    row = cur.fetchone()
    conn.close()
    return row


# -------------------------------------------------
# SECURITY HELPERS
# -------------------------------------------------
def hash_password(password: str) -> str:
    return generate_password_hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return check_password_hash(password_hash, password)


# -------------------------------------------------
# USER SEEDING (DEMO ONLY)
# -------------------------------------------------
def seed_default_users():
    conn = get_db()
    cur = conn.cursor()

    users = [
        
        {
            "email": "amina@school.test",
            "password": "password123",
            "role": "teacher",
        },
        {
            "email": "principal@school.test",
            "password": "admin123",
            "role": "principal",
        },
    ]

    for user in users:
        cur.execute(
            "SELECT id FROM users WHERE email = ?",
            (user["email"],)
        )
        exists = cur.fetchone()

        if not exists:
            cur.execute(
                """
                INSERT INTO users (email, password_hash, role)
                VALUES (?, ?, ?)
                """,
                (
                    user["email"],
                    hash_password(user["password"]),
                    user["role"],
                )
            )
    conn.commit()
    conn.close()
# -------------------------------------------------
# DEMO DATA — TEACHERS (PHASE 3B-1)
# -------------------------------------------------
def seed_demo_teachers():
    """
    Creates additional demo teachers (users + teachers).
    Idempotent and safe to run multiple times.
    """
    demo_teachers = [
        {
            "email": "brian@school.test",
            "name": "Brian Otieno",
            "subject": "English",
        },
        {
            "email": "grace@school.test",
            "name": "Grace Wanjiku",
            "subject": "Biology",
        },
        {
            "email": "peter@school.test",
            "name": "Peter Mwangi",
            "subject": "History",
        },
    ]

    conn = get_db()
    cur = conn.cursor()

    for t in demo_teachers:
        # 1) Ensure user exists (role=teacher)
        cur.execute("SELECT id FROM users WHERE email = ?", (t["email"],))
        user = cur.fetchone()

        if not user:
            cur.execute(
                """
                INSERT INTO users (email, password_hash, role)
                VALUES (?, ?, 'teacher')
                """,
                (t["email"], hash_password("password123"))
            )

        # 2) Ensure teacher record exists
        cur.execute("SELECT id FROM teachers WHERE email = ?", (t["email"],))
        teacher = cur.fetchone()

        if not teacher:
            cur.execute(
                """
                INSERT INTO teachers (email, name, subject)
                VALUES (?, ?, ?)
                """,
                (t["email"], t["name"], t["subject"])
            )

    conn.commit()
    conn.close()


