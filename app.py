from flask import Flask, render_template, request, redirect, url_for, session
from db import get_all_observations
from db import verify_password, get_db

from flask import abort
from db import get_all_teachers
from db import get_classes_with_learner_counts_for_teacher
from db import get_principal_teacher_summary
from db import get_principal_dashboard_summary
from db import get_observation_by_id, update_observation
from db import (
    init_db,
    get_or_create_teacher,
    save_observation,
    get_recent_observations,
    get_weekly_summary,
    seed_default_classes,
    get_classes_for_teacher,
    seed_default_learners,
    get_learners_for_class,
    get_learner_with_class,
    get_db,
      soft_delete_observation,
)

from db import (
    get_all_teachers,
    get_teacher_by_id,
    get_classes_for_teacher_readonly,
    get_observations_for_teacher_readonly,
)


app = Flask(__name__)
app.secret_key = "cbc-connect-v2-secret"  # will be replaced later

# -------------------------------------------------
# TEMP teacher account (for flow testing only)
# -------------------------------------------------

# -------------------------------------------------
# ACCESS GUARDS (RBAC)
# -------------------------------------------------
from flask import abort

def require_login():
    if "user_id" not in session:
        return redirect(url_for("login"))

def require_teacher():
    if session.get("role") != "teacher":
        abort(403)

# -------------------------------------------------
# LOGIN
# -------------------------------------------------
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        conn = get_db()
        cur = conn.cursor()

        # Fetch user
        cur.execute(
            "SELECT id, password_hash, role, is_active FROM users WHERE email = ?",
            (email,)
        )
        user = cur.fetchone()
        conn.close()

        if not user or not user["is_active"]:
            return render_template(
                "auth/login.html",
                error="Invalid login details"
            )

        if not verify_password(password, user["password_hash"]):
            return render_template(
                "auth/login.html",
                error="Invalid login details"
            )

        # 🔐 Secure session
        session.clear()
        session["user_id"] = user["id"]
        session["role"] = user["role"]



        # Teacher flow (unchanged behavior)
        if user["role"] == "teacher":
            teacher_id = get_or_create_teacher(
                email,
                "Amina Hassan",
                "Mathematics"
            )

            seed_default_classes(teacher_id)

            session["teacher_id"] = teacher_id
            session["teacher_logged_in"] = True

            return redirect(url_for("dashboard"))

        # Principal not handled yet (Phase 2)
        return render_template(
            "auth/login.html",
            error="Unauthorized role"
        )

    return render_template("auth/login.html")


# -------------------------------------------------
# PRINCIPAL LOGIN (READ-ONLY)
# -------------------------------------------------
@app.route("/principal/login", methods=["GET", "POST"])
def principal_login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        conn = get_db()
        cur = conn.cursor()

        cur.execute(
            "SELECT id, password_hash, role, is_active FROM users WHERE email = ?",
            (email,)
        )
        user = cur.fetchone()
        conn.close()

        if not user or not user["is_active"]:
            return render_template(
                "auth/principal_login.html",
                error="Invalid login details"
            )

        if not verify_password(password, user["password_hash"]):
            return render_template(
                "auth/principal_login.html",
                error="Invalid login details"
            )

        if user["role"] != "principal":
            return render_template(
                "auth/principal_login.html",
                error="Unauthorized access"
            )

        # 🔐 Secure principal session
        session.clear()
        session["user_id"] = user["id"]
        session["role"] = "principal"

        # ✅ Redirect to principal dashboard
        return redirect(url_for("principal_dashboard"))

    return render_template("auth/principal_login.html")

# -------------------------------------------------
# PRINCIPAL HOME (TEMP)
# -------------------------------------------------
@app.route("/principal")
def principal_home():
    if "user_id" not in session:
        return redirect(url_for("principal_login"))

    if session.get("role") != "principal":
        abort(403)

    return "<h3>Principal logged in. Views coming next.</h3>"

# -------------------------------------------------
# PRINCIPAL — TEACHER LIST (READ-ONLY)
# -------------------------------------------------
@app.route("/principal/teachers")
def principal_teachers():
    if "user_id" not in session:
        return redirect(url_for("principal_login"))

    if session.get("role") != "principal":
        abort(403)

    teachers = get_all_teachers()
    return render_template(
        "principal/teachers.html",
        teachers=teachers
    )

# -------------------------------------------------
# PRINCIPAL — TEACHER DRILL-DOWN (READ-ONLY)
# -------------------------------------------------
@app.route("/principal/teacher/<int:teacher_id>")
def principal_teacher_view(teacher_id):
    if "user_id" not in session:
        return redirect(url_for("principal_login"))

    if session.get("role") != "principal":
        abort(403)

    teacher = get_teacher_by_id(teacher_id)
    if not teacher:
        abort(404)

    classes = get_classes_with_learner_counts_for_teacher(teacher_id)

    observations = get_observations_for_teacher_readonly(teacher_id)

    summary = get_principal_teacher_summary(teacher_id)


    return render_template(
        "principal/teacher_view.html",
        teacher=teacher,
        classes=classes,
        observations=observations,
        summary=summary
    )

# -------------------------------------------------
# PRINCIPAL — DASHBOARD
# -------------------------------------------------
@app.route("/principal/dashboard")
def principal_dashboard():
    if "user_id" not in session:
        return redirect(url_for("principal_login"))

    if session.get("role") != "principal":
        abort(403)

    summary = get_principal_dashboard_summary()

    return render_template(
        "principal/dashboard.html",
        summary=summary
    )




# -------------------------------------------------
# DASHBOARD
# -------------------------------------------------
@app.route("/dashboard")
def dashboard():
    if not session.get("teacher_logged_in"):
        return redirect(url_for("login"))

    require_teacher()

    teacher_id = session["teacher_id"]
    summary = get_weekly_summary(teacher_id)
    return render_template("dashboard.html", summary=summary)
# -------------------------------------------------


@app.route("/observations")
def observations():
    # 🔐 Security gate: must be logged-in teacher
    require_teacher()

    teacher_id = session["teacher_id"]

    observations = get_all_observations(teacher_id)

    return render_template(
        "observations.html",
        observations=observations
    )


# -------------------------------------------------
# CLASSES (PHASE B1-B: DB-DRIVEN)
# -------------------------------------------------
@app.route("/classes")
def classes():
    if not session.get("teacher_logged_in"):
        return redirect(url_for("login"))

    require_teacher()   # 👈 ADD THIS LINE

    teacher_id = session.get("teacher_id")
    classes = get_classes_for_teacher(teacher_id)

    return render_template("classes.html", classes=classes)
# -------------------------------------------------

@app.route("/learners")
def learners():
    if not session.get("teacher_logged_in"):
        return redirect(url_for("login"))

    require_teacher()   # 👈 ADD THIS LINE

    class_id = request.args.get("class_id", type=int)
    if not class_id:
        return redirect(url_for("classes"))

    seed_default_learners(class_id)
    learners = get_learners_for_class(class_id)

    return render_template("learners.html", learners=learners)
# -------------------------------------------------

@app.route("/observe", methods=["GET", "POST"])
def observe():
    # 🔐 Security gate: must be logged-in teacher
    require_teacher()

    learner_id = request.args.get("learner_id", type=int)
    class_id = request.args.get("class_id", type=int)

    if not learner_id or not class_id:
        abort(400)

    # Fetch learner + class info
    learner = get_learner_with_class(learner_id)
    if not learner:
        abort(404)

    teacher_id = session["teacher_id"]

    # 🔒 Ownership check:
    # Ensure the learner belongs to a class owned by this teacher
    classes = get_classes_for_teacher(teacher_id)
    allowed_class_ids = {c["id"] for c in classes}

    if learner["class_id"] not in allowed_class_ids:
        abort(403)

    if request.method == "POST":
        activity = request.form.get("activity", "").strip()
        skill = request.form.get("skill", "").strip()
        level = request.form.get("level", "").strip()
        note = request.form.get("note", "").strip()

        # 🔒 Basic validation
        if not activity or not skill or not level:
            return render_template(
                "observe.html",
                learner=learner,
                error="Activity, skill, and level are required."
            )

        save_observation(
            teacher_id=teacher_id,
            class_name=learner["class_name"],
            learner_id=learner["learner_id"],
            activity=activity,
            skill=skill,
            level=level,
            note=note,
        )

        return redirect(
            url_for("learners", class_id=class_id)
        )

    return render_template("observe.html", learner=learner)


# -------------------------------------------------
# RECENT OBSERVATIONS
# -------------------------------------------------
@app.route("/show")
def show():
    if not session.get("teacher_logged_in"):
        return redirect(url_for("login"))

    require_teacher()   # 👈 ADD THIS LINE

    teacher_id = session.get("teacher_id")
    observations = get_recent_observations(teacher_id)

    return render_template("show.html", observations=observations)

# -------------------------------------------------
# EDIT OBSERVATION (TEACHER ONLY)
# -------------------------------------------------
@app.route("/observations/<int:observation_id>/edit", methods=["GET", "POST"])
def edit_observation(observation_id):
    if not session.get("teacher_logged_in"):
        return redirect(url_for("login"))

    require_teacher()

    teacher_id = session["teacher_id"]

    observation = get_observation_by_id(observation_id, teacher_id)
    if not observation:
        abort(404)

    if request.method == "POST":
        activity = request.form.get("activity")
        skill = request.form.get("skill")
        level = request.form.get("level")
        note = request.form.get("note")

        update_observation(
            observation_id,
            teacher_id,
            activity,
            skill,
            level,
            note
        )

        return redirect(url_for("observations"))

    return render_template(
        "edit_observation.html",
        observation=observation
    )

@app.route("/observations/delete/<int:observation_id>", methods=["POST"])
def delete_observation(observation_id):
    if not session.get("teacher_logged_in"):
        return redirect(url_for("login"))

    require_teacher()

    teacher_id = session["teacher_id"]

    observation = get_observation_by_id(observation_id, teacher_id)
    if not observation:
        abort(404)

    soft_delete_observation(observation_id, teacher_id)

    return redirect(url_for("observations"))


# -------------------------------------------------
# WEEKLY SUMMARY
# -------------------------------------------------
@app.route("/week")
def week():
    if not session.get("teacher_logged_in"):
        return redirect(url_for("login"))

    require_teacher()   # 👈 ADD THIS LINE

    teacher_id = session.get("teacher_id")
    summary = get_weekly_summary(teacher_id)

    return render_template("week.html", summary=summary)
# -------------------------------------------------

@app.route("/reports")
def reports():
    if not session.get("teacher_logged_in"):
        return redirect(url_for("login"))

    require_teacher()   # 👈 ADD THIS LINE

    teacher_id = session["teacher_id"]
    observations = get_recent_observations(teacher_id, limit=1000)

    return render_template(
        "reports.html",
        observations=observations
    )



# -------------------------------------------------
# LOGOUT
# -------------------------------------------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# -------------------------------------------------
# APP ENTRY
# -------------------------------------------------
if __name__ == "__main__":
    init_db()
    app.run(debug=True)
