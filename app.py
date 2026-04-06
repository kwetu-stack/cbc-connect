import os

from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from db import get_all_observations

from db import (
    ensure_demo_data,
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
    set_demo_write_blocked,
)

app = Flask(__name__)
app.secret_key = "cbc-connect-v2-secret"  # will be replaced later
app.config["DEBUG"] = False

DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() == "true"


def is_demo():
    return DEMO_MODE


set_demo_write_blocked(is_demo())

# -------------------------------------------------
# TEMP teacher account (for flow testing only)
# -------------------------------------------------
TEACHER = {
    "email": "amina@school.test",
    "password": "password123",
    "name": "Amina Hassan",
    "subject": "Mathematics",
}


@app.context_processor
def inject_demo_mode():
    return {"demo_mode": is_demo()}


@app.before_request
def force_demo_user():
    if not is_demo():
        return None

    teacher_id = ensure_demo_data()
    session["teacher_logged_in"] = True
    session["teacher_id"] = teacher_id
    return None


@app.before_request
def block_post_in_demo():
    if is_demo() and request.method == "POST":
        flash("Demo Mode: Action simulated successfully.", "info")
        return redirect(request.referrer or url_for("dashboard"))

    return None

# -------------------------------------------------
# LOGIN
# -------------------------------------------------
@app.route("/", methods=["GET", "POST"])
def login():
    if is_demo():
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")

        if email == TEACHER["email"] and password == TEACHER["password"]:
            teacher_id = get_or_create_teacher(
                TEACHER["email"],
                TEACHER["name"],
                TEACHER["subject"],
            )

            # 🔑 PHASE B1: seed classes for this teacher
            seed_default_classes(teacher_id)

            session["teacher_logged_in"] = True
            session["teacher_id"] = teacher_id

            return redirect(url_for("dashboard"))

        return render_template("auth/login.html", error="Invalid login details")

    return render_template("auth/login.html")

# -------------------------------------------------
# DASHBOARD
# -------------------------------------------------
@app.route("/dashboard")
def dashboard():
    if not session.get("teacher_logged_in"):
        return redirect(url_for("login"))

    teacher_id = session["teacher_id"]
    summary = get_weekly_summary(teacher_id)

    return render_template("dashboard.html", summary=summary)

@app.route("/observations")
def observations():
    if not session.get("teacher_logged_in"):
        return redirect(url_for("login"))

    teacher_id = session["teacher_id"]
    observations = get_all_observations(teacher_id)

    return render_template("observations.html", observations=observations)

# -------------------------------------------------
# CLASSES (PHASE B1-B: DB-DRIVEN)
# -------------------------------------------------
@app.route("/classes")
def classes():
    if not session.get("teacher_logged_in"):
        return redirect(url_for("login"))

    teacher_id = session.get("teacher_id")
    classes = get_classes_for_teacher(teacher_id)

    return render_template("classes.html", classes=classes)

@app.route("/learners")
def learners():
    if not session.get("teacher_logged_in"):
        return redirect(url_for("login"))

    class_id = request.args.get("class_id", type=int)
    if not class_id:
        return redirect(url_for("classes"))

    seed_default_learners(class_id)
    learners = get_learners_for_class(class_id)

    return render_template("learners.html", learners=learners)

@app.route("/observe", methods=["GET", "POST"])
def observe():
    if not session.get("teacher_logged_in"):
        return redirect(url_for("login"))

    learner_id = request.args.get("learner_id", type=int)
    if not learner_id:
        return redirect(url_for("classes"))

    learner = get_learner_with_class(learner_id)
    if not learner:
        return redirect(url_for("classes"))

    if request.method == "POST":
        teacher_id = session["teacher_id"]

        activity = request.form.get("activity")
        skill = request.form.get("skill")
        level = request.form.get("level")
        note = request.form.get("note")

        save_observation(
            teacher_id,
            learner["class_name"],
            learner["learner_id"],
            activity,
            skill,
            level,
            note,
        )

        return redirect(url_for("learners", class_id=request.args.get("class_id")))

    return render_template("observe.html", learner=learner)

# -------------------------------------------------
# RECENT OBSERVATIONS
# -------------------------------------------------
@app.route("/show")
def show():
    if not session.get("teacher_logged_in"):
        return redirect(url_for("login"))

    teacher_id = session.get("teacher_id")
    observations = get_recent_observations(teacher_id)

    return render_template("show.html", observations=observations)

# -------------------------------------------------
# WEEKLY SUMMARY
# -------------------------------------------------
@app.route("/week")
def week():
    if not session.get("teacher_logged_in"):
        return redirect(url_for("login"))

    teacher_id = session.get("teacher_id")
    summary = get_weekly_summary(teacher_id)

    return render_template("week.html", summary=summary)

@app.route("/reports")
@app.route("/reports/")
def reports():
    if not session.get("teacher_logged_in"):
        return redirect(url_for("login"))

    teacher_id = session["teacher_id"]

    observations = get_all_observations(teacher_id)

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
    if is_demo():
        ensure_demo_data()
        set_demo_write_blocked(True)

    app.run(debug=False)
