import os

from flask import (
    Flask,
    flash,
    make_response,
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
    get_learner_summary,
    get_observation_by_id,
    update_observation,
    delete_observation,
    clear_observations_for_teacher,
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
DEMO_BLOCK_WRITES = os.getenv("DEMO_BLOCK_WRITES", "false").lower() == "true"


def is_demo():
    return DEMO_MODE


set_demo_write_blocked(is_demo() and DEMO_BLOCK_WRITES)

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
    return {"demo_mode": is_demo(), "demo_block_writes": DEMO_BLOCK_WRITES}


@app.route("/demo/reset", methods=["POST"])
def demo_reset():
    if not is_demo():
        return redirect(url_for("dashboard"))

    teacher_id = session.get("teacher_id")
    if teacher_id:
        clear_observations_for_teacher(teacher_id, allow_in_demo=True)
        flash("Demo reset: observations cleared.", "info")
    return redirect(request.referrer or url_for("dashboard"))


@app.before_request
def force_demo_user():
    if not is_demo():
        return None

    teacher_id = ensure_demo_data()
    session["teacher_logged_in"] = True
    session["teacher_id"] = teacher_id
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
    filters = {
        "class_id": request.args.get("class_id", type=int),
        "learner_id": request.args.get("learner_id", type=int),
        "skill": request.args.get("skill") or None,
        "level": request.args.get("level") or None,
        "from_date": request.args.get("from") or None,
        "to_date": request.args.get("to") or None,
    }
    observations = get_all_observations(teacher_id, filters=filters)
    classes = get_classes_for_teacher(teacher_id)

    learners = []
    if filters["class_id"]:
        seed_default_learners(filters["class_id"])
        learners = get_learners_for_class(filters["class_id"])

    return render_template(
        "observations.html",
        observations=observations,
        classes=classes,
        learners=learners,
        filters=filters,
    )

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

    return render_template("learners.html", learners=learners, class_id=class_id)


@app.route("/learner/<int:learner_id>")
def learner(learner_id):
    if not session.get("teacher_logged_in"):
        return redirect(url_for("login"))

    teacher_id = session["teacher_id"]
    learner_row = get_learner_with_class(learner_id)
    if not learner_row:
        return redirect(url_for("classes"))

    filters = {
        "class_id": None,
        "learner_id": learner_id,
        "skill": request.args.get("skill") or None,
        "level": request.args.get("level") or None,
        "from_date": request.args.get("from") or None,
        "to_date": request.args.get("to") or None,
    }
    observations = get_all_observations(teacher_id, filters=filters)
    summary = get_learner_summary(teacher_id, learner_id, filters=filters)

    return render_template(
        "learner.html",
        learner=learner_row,
        observations=observations,
        summary=summary,
        filters=filters,
    )

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

        if not activity or not skill or not level:
            flash(
                "Please choose an activity, a skill, and an observation level before saving.",
                "error",
            )
            return render_template(
                "observe.html",
                learner=learner,
                activity=activity,
                skill=skill,
                level=level,
                note=note,
            )

        ok = save_observation(
            teacher_id,
            learner["class_name"],
            learner["learner_id"],
            activity,
            skill,
            level,
            note,
        )
        if not ok:
            flash(
                "Could not save right now (storage busy). If you’re using OneDrive, run with a local DB path (TEMP) and try again.",
                "error",
            )
            return render_template(
                "observe.html",
                learner=learner,
                activity=activity,
                skill=skill,
                level=level,
                note=note,
            )

        class_id = request.args.get("class_id", type=int)
        if not class_id:
            return redirect(url_for("learner", learner_id=learner_id))
        return redirect(url_for("learners", class_id=class_id))

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


@app.route("/export/observations.csv")
def export_observations_csv():
    if not session.get("teacher_logged_in"):
        return redirect(url_for("login"))

    teacher_id = session["teacher_id"]
    filters = {
        "class_id": request.args.get("class_id", type=int),
        "learner_id": request.args.get("learner_id", type=int),
        "skill": request.args.get("skill") or None,
        "level": request.args.get("level") or None,
        "from_date": request.args.get("from") or None,
        "to_date": request.args.get("to") or None,
    }
    rows = get_all_observations(teacher_id, filters=filters)

    lines = ["date,class,learner,activity,skill,level,note"]
    for r in rows:
        def esc(v):
            if v is None:
                v = ""
            v = str(v).replace('\"', '\"\"')
            return f'\"{v}\"'

        def val(key):
            # sqlite3.Row is dict-like but does not implement .get()
            return r[key] if key in r.keys() else None

        lines.append(
            ",".join(
                [
                    esc(val("created_at")),
                    esc(val("class_name")),
                    esc(val("learner_name")),
                    esc(val("activity")),
                    esc(val("skill")),
                    esc(val("level")),
                    esc(val("note")),
                ]
            )
        )

    resp = make_response("\n".join(lines))
    resp.headers["Content-Type"] = "text/csv; charset=utf-8"
    resp.headers["Content-Disposition"] = "attachment; filename=cbc-observations.csv"
    return resp


@app.route("/observations/<int:observation_id>/edit", methods=["GET", "POST"])
def edit_observation(observation_id):
    if not session.get("teacher_logged_in"):
        return redirect(url_for("login"))

    teacher_id = session["teacher_id"]
    obs = get_observation_by_id(teacher_id, observation_id)
    if not obs:
        flash("Observation not found.", "info")
        return redirect(url_for("observations"))

    if request.method == "POST":
        activity = request.form.get("activity")
        skill = request.form.get("skill")
        level = request.form.get("level")
        note = request.form.get("note")

        if not activity or not skill or not level:
            flash(
                "Please choose an activity, a skill, and a level before saving.",
                "error",
            )
            return render_template(
                "edit_observation.html",
                obs=obs,
                activity=activity,
                skill=skill,
                level=level,
                note=note,
            )

        update_observation(teacher_id, observation_id, activity, skill, level, note)
        flash("Observation updated.", "info")
        return redirect(url_for("learner", learner_id=obs["learner_id"]))

    return render_template("edit_observation.html", obs=obs)


@app.route("/observations/<int:observation_id>/delete", methods=["POST"])
def remove_observation(observation_id):
    if not session.get("teacher_logged_in"):
        return redirect(url_for("login"))

    teacher_id = session["teacher_id"]
    obs = get_observation_by_id(teacher_id, observation_id)
    if not obs:
        flash("Observation not found.", "info")
        return redirect(url_for("observations"))

    delete_observation(teacher_id, observation_id)
    flash("Observation deleted.", "info")
    return redirect(url_for("learner", learner_id=obs["learner_id"]))


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
        set_demo_write_blocked(DEMO_BLOCK_WRITES)

    port = int(os.getenv("PORT", "5000"))
    app.run(debug=False, port=port)
