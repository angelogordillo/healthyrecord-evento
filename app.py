import os
import re
import secrets
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import generate_password_hash, check_password_hash

from db import get_db, init_db, PERSONALITY_DIMENSIONS, PERSONALITY_QUESTIONS

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

ADMIN_USERNAMES = {
    u.strip().lower()
    for u in os.environ.get("ADMIN_USERNAMES", "").split(",")
    if u.strip()
}


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Debes iniciar sesion para ver esa pagina.", "error")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


def get_user_profile_ids(db, user_id):
    interest_ids = {
        r["interest_id"]
        for r in db.execute("SELECT interest_id FROM user_interests WHERE user_id = ?", (user_id,))
    }
    trait_ids = {
        r["trait_id"]
        for r in db.execute("SELECT trait_id FROM user_traits WHERE user_id = ?", (user_id,))
    }
    return interest_ids, trait_ids


def get_personality_scores(db, user_id):
    row = db.execute(
        "SELECT * FROM personality_scores WHERE user_id = ?", (user_id,)
    ).fetchone()
    if not row:
        return None
    return {d: row[d] for d in PERSONALITY_DIMENSIONS}


def personality_similarity(scores_a, scores_b):
    if not scores_a or not scores_b:
        return None
    avg_diff = sum(abs(scores_a[d] - scores_b[d]) for d in PERSONALITY_DIMENSIONS) / len(
        PERSONALITY_DIMENSIONS
    )
    return 100 - avg_diff


def compatibility_score(interests_a, traits_a, interests_b, traits_b,
                         personality_a=None, personality_b=None):
    interest_trait_score = _interest_trait_score(interests_a, traits_a, interests_b, traits_b)
    pers_score = personality_similarity(personality_a, personality_b)

    if interest_trait_score is None and pers_score is None:
        return None
    if pers_score is None:
        return round(interest_trait_score)
    if interest_trait_score is None:
        return round(pers_score)
    return round(0.5 * interest_trait_score + 0.5 * pers_score)


def _interest_trait_score(interests_a, traits_a, interests_b, traits_b):
    set_a = {("i", i) for i in interests_a} | {("t", t) for t in traits_a}
    set_b = {("i", i) for i in interests_b} | {("t", t) for t in traits_b}
    if not set_a or not set_b:
        return None
    shared = len(set_a & set_b)
    total = len(set_a | set_b)
    if total == 0:
        return None
    return 100 * shared / total


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Debes iniciar sesion para ver esa pagina.", "error")
            return redirect(url_for("login"))
        if session.get("username") not in ADMIN_USERNAMES:
            flash("No tienes permiso para ver esa pagina.", "error")
            return redirect(url_for("panel"))
        return view(*args, **kwargs)
    return wrapped


@app.context_processor
def inject_user():
    return {
        "current_user": session.get("full_name"),
        "is_admin": session.get("username") in ADMIN_USERNAMES,
    }


@app.route("/")
def index():
    db = get_db()
    locations = db.execute("SELECT * FROM locations ORDER BY id").fetchall()
    db.close()
    return render_template("index.html", locations=locations)


@app.route("/suscribirse", methods=["POST"])
def subscribe():
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()

    if not name or not email or not EMAIL_RE.match(email):
        flash("Ingresa un nombre y un correo valido.", "error")
        return redirect(url_for("index", _anchor="registro"))

    db = get_db()
    try:
        db.execute("INSERT INTO subscribers (name, email) VALUES (?, ?)", (name, email))
        db.commit()
        flash("Listo, " + name + ". Te avisaremos por correo de las proximas novedades.", "success")
    except Exception:
        flash("Ese correo ya estaba suscrito, pero igual quedas al tanto.", "success")
    finally:
        db.close()

    return redirect(url_for("index", _anchor="registro"))


@app.route("/crear-cuenta", methods=["GET", "POST"])
def signup():
    if request.method == "GET":
        return render_template("signup.html")

    full_name = request.form.get("full_name", "").strip()
    username = request.form.get("username", "").strip().lower()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    if not full_name or not username or not email or not password:
        flash("Completa todos los campos.", "error")
        return render_template("signup.html")
    if not EMAIL_RE.match(email):
        flash("Ingresa un correo valido.", "error")
        return render_template("signup.html")
    if len(password) < 6:
        flash("La contrasena debe tener al menos 6 caracteres.", "error")
        return render_template("signup.html")

    db = get_db()
    existing = db.execute(
        "SELECT id FROM users WHERE username = ? OR email = ?", (username, email)
    ).fetchone()
    if existing:
        db.close()
        flash("Ese usuario o correo ya esta registrado. Intenta iniciar sesion.", "error")
        return render_template("signup.html")

    password_hash = generate_password_hash(password)
    cur = db.execute(
        "INSERT INTO users (full_name, username, email, password_hash) VALUES (?, ?, ?, ?)",
        (full_name, username, email, password_hash),
    )
    db.commit()
    user_id = cur.lastrowid
    db.close()

    session["user_id"] = user_id
    session["full_name"] = full_name
    session["username"] = username
    flash("Cuenta creada. Bienvenido(a), " + full_name + ".", "success")
    return redirect(url_for("panel"))


@app.route("/ingresar", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    username = request.form.get("username", "").strip().lower()
    password = request.form.get("password", "")

    db = get_db()
    user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    db.close()

    if not user or not check_password_hash(user["password_hash"], password):
        flash("Usuario o contrasena incorrectos.", "error")
        return render_template("login.html")

    session["user_id"] = user["id"]
    session["full_name"] = user["full_name"]
    session["username"] = user["username"]
    flash("Hola de nuevo, " + user["full_name"] + ".", "success")
    return redirect(url_for("panel"))


@app.route("/salir")
def logout():
    session.clear()
    flash("Sesion cerrada.", "success")
    return redirect(url_for("index"))


@app.route("/perfil", methods=["GET", "POST"])
@login_required
def profile():
    db = get_db()

    if request.method == "POST":
        interest_ids = [int(i) for i in request.form.getlist("interests")]
        trait_ids = [int(i) for i in request.form.getlist("traits")]

        db.execute("DELETE FROM user_interests WHERE user_id = ?", (session["user_id"],))
        db.execute("DELETE FROM user_traits WHERE user_id = ?", (session["user_id"],))
        db.executemany(
            "INSERT INTO user_interests (user_id, interest_id) VALUES (?, ?)",
            [(session["user_id"], i) for i in interest_ids],
        )
        db.executemany(
            "INSERT INTO user_traits (user_id, trait_id) VALUES (?, ?)",
            [(session["user_id"], t) for t in trait_ids],
        )
        db.commit()
        db.close()
        flash("Tu perfil se actualizo. Ya puedes ver tu afinidad con otros asistentes.", "success")
        return redirect(url_for("profile"))

    all_interests = db.execute("SELECT * FROM interests ORDER BY name").fetchall()
    all_traits = db.execute("SELECT * FROM personality_traits ORDER BY name").fetchall()
    my_interests, my_traits = get_user_profile_ids(db, session["user_id"])
    my_personality = get_personality_scores(db, session["user_id"])
    db.close()

    return render_template(
        "perfil.html",
        all_interests=all_interests,
        all_traits=all_traits,
        my_interests=my_interests,
        my_traits=my_traits,
        my_personality=my_personality,
        dimension_labels={
            "openness": "Apertura a lo nuevo",
            "conscientiousness": "Responsabilidad",
            "extraversion": "Extraversion",
            "agreeableness": "Amabilidad",
            "stability": "Estabilidad emocional",
        },
    )


PERSONALITY_LIKERT = [
    (1, "Muy en desacuerdo"),
    (2, "En desacuerdo"),
    (3, "Neutral"),
    (4, "De acuerdo"),
    (5, "Muy de acuerdo"),
]


@app.route("/perfil/test", methods=["GET", "POST"])
@login_required
def personality_test():
    if request.method == "POST":
        answers = {}
        for q in PERSONALITY_QUESTIONS:
            raw = request.form.get(q["id"])
            if raw not in {"1", "2", "3", "4", "5"}:
                flash("Responde todas las preguntas del test.", "error")
                return redirect(url_for("personality_test"))
            value = int(raw)
            answers[q["id"]] = 6 - value if q["reverse"] else value

        scores = {}
        for dim in PERSONALITY_DIMENSIONS:
            dim_values = [answers[q["id"]] for q in PERSONALITY_QUESTIONS if q["dimension"] == dim]
            scores[dim] = round(100 * (sum(dim_values) / len(dim_values) - 1) / 4, 1)

        db = get_db()
        db.execute(
            """
            INSERT INTO personality_scores
                (user_id, openness, conscientiousness, extraversion, agreeableness, stability, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(user_id) DO UPDATE SET
                openness=excluded.openness,
                conscientiousness=excluded.conscientiousness,
                extraversion=excluded.extraversion,
                agreeableness=excluded.agreeableness,
                stability=excluded.stability,
                updated_at=excluded.updated_at
            """,
            (
                session["user_id"], scores["openness"], scores["conscientiousness"],
                scores["extraversion"], scores["agreeableness"], scores["stability"],
            ),
        )
        db.commit()
        db.close()
        flash("Test completado. Tu perfil avanzado ya esta actualizado.", "success")
        return redirect(url_for("profile"))

    return render_template(
        "perfil_test.html", questions=PERSONALITY_QUESTIONS, likert=PERSONALITY_LIKERT
    )


@app.route("/panel")
@login_required
def panel():
    db = get_db()
    events = db.execute(
        """
        SELECT e.*, l.name AS location_name, l.area AS location_area,
               l.description AS location_description, l.activities AS location_activities,
               l.emoji AS location_emoji
        FROM events e JOIN locations l ON l.id = e.location_id
        ORDER BY e.date_start
        """
    ).fetchall()

    my_interests, my_traits = get_user_profile_ids(db, session["user_id"])
    my_personality = get_personality_scores(db, session["user_id"])

    event_list = []
    for e in events:
        participants = db.execute(
            """
            SELECT u.id, u.full_name FROM event_participants ep
            JOIN users u ON u.id = ep.user_id
            WHERE ep.event_id = ?
            ORDER BY ep.created_at
            """,
            (e["id"],),
        ).fetchall()
        participant_names = []
        matches = []
        for p in participants:
            parts = p["full_name"].split()
            first = parts[0]
            last_initial = (parts[1][0] + ".") if len(parts) > 1 else ""
            display_name = (first + " " + last_initial).strip()
            participant_names.append(display_name)

            if p["id"] != session["user_id"]:
                their_interests, their_traits = get_user_profile_ids(db, p["id"])
                their_personality = get_personality_scores(db, p["id"])
                score = compatibility_score(
                    my_interests, my_traits, their_interests, their_traits,
                    my_personality, their_personality,
                )
                if score is not None:
                    matches.append({"name": display_name, "score": score})

        matches.sort(key=lambda m: m["score"], reverse=True)

        joined = db.execute(
            "SELECT 1 FROM event_participants WHERE event_id = ? AND user_id = ?",
            (e["id"], session["user_id"]),
        ).fetchone()

        event_list.append({
            "row": e,
            "participants": participant_names,
            "spots_left": e["capacity"] - len(participants),
            "joined": bool(joined),
            "matches": matches,
        })

    db.close()
    has_profile = bool(my_interests or my_traits)
    return render_template("panel.html", events=event_list, has_profile=has_profile)


@app.route("/panel/eventos/<int:event_id>/unirse", methods=["POST"])
@login_required
def join_event(event_id):
    db = get_db()
    event = db.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    if not event:
        db.close()
        flash("Ese evento no existe.", "error")
        return redirect(url_for("panel"))

    count = db.execute(
        "SELECT COUNT(*) AS c FROM event_participants WHERE event_id = ?", (event_id,)
    ).fetchone()["c"]

    if count >= event["capacity"]:
        flash("Ese evento ya esta lleno.", "error")
    else:
        try:
            db.execute(
                "INSERT INTO event_participants (event_id, user_id) VALUES (?, ?)",
                (event_id, session["user_id"]),
            )
            db.commit()
            flash("Confirmaste tu asistencia a " + event["title"] + ".", "success")
        except Exception:
            flash("Ya estabas inscrito(a) en ese evento.", "success")

    db.close()
    return redirect(url_for("panel"))


@app.route("/admin")
@admin_required
def admin():
    db = get_db()
    subscribers = db.execute(
        "SELECT name, email, created_at FROM subscribers ORDER BY created_at DESC"
    ).fetchall()
    users = db.execute(
        "SELECT full_name, username, email, created_at FROM users ORDER BY created_at DESC"
    ).fetchall()
    events = db.execute(
        """
        SELECT e.*, l.name AS location_name
        FROM events e JOIN locations l ON l.id = e.location_id
        ORDER BY e.date_start
        """
    ).fetchall()

    event_list = []
    for e in events:
        attendees = db.execute(
            """
            SELECT u.id, u.full_name, u.email, ep.created_at FROM event_participants ep
            JOIN users u ON u.id = ep.user_id
            WHERE ep.event_id = ?
            ORDER BY ep.created_at
            """,
            (e["id"],),
        ).fetchall()

        profiles = {a["id"]: get_user_profile_ids(db, a["id"]) for a in attendees}
        personalities = {a["id"]: get_personality_scores(db, a["id"]) for a in attendees}
        pairs = []
        for i in range(len(attendees)):
            for j in range(i + 1, len(attendees)):
                a, b = attendees[i], attendees[j]
                interests_a, traits_a = profiles[a["id"]]
                interests_b, traits_b = profiles[b["id"]]
                score = compatibility_score(
                    interests_a, traits_a, interests_b, traits_b,
                    personalities[a["id"]], personalities[b["id"]],
                )
                if score is not None:
                    pairs.append({"a": a["full_name"], "b": b["full_name"], "score": score})
        pairs.sort(key=lambda p: p["score"], reverse=True)

        event_list.append({"row": e, "attendees": attendees, "pairs": pairs[:30]})

    db.close()
    return render_template(
        "admin.html", subscribers=subscribers, users=users, events=event_list
    )


init_db()

if __name__ == "__main__":
    app.run(debug=True, port=int(os.environ.get("PORT", 5050)))
