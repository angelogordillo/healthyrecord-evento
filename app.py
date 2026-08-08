import os
import re
import secrets
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import generate_password_hash, check_password_hash

from db import get_db, init_db

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

    event_list = []
    for e in events:
        participants = db.execute(
            """
            SELECT u.full_name FROM event_participants ep
            JOIN users u ON u.id = ep.user_id
            WHERE ep.event_id = ?
            ORDER BY ep.created_at
            """,
            (e["id"],),
        ).fetchall()
        participant_names = []
        for p in participants:
            parts = p["full_name"].split()
            first = parts[0]
            last_initial = (parts[1][0] + ".") if len(parts) > 1 else ""
            participant_names.append((first + " " + last_initial).strip())

        joined = db.execute(
            "SELECT 1 FROM event_participants WHERE event_id = ? AND user_id = ?",
            (e["id"], session["user_id"]),
        ).fetchone()

        event_list.append({
            "row": e,
            "participants": participant_names,
            "spots_left": e["capacity"] - len(participants),
            "joined": bool(joined),
        })

    db.close()
    return render_template("panel.html", events=event_list)


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
            SELECT u.full_name, u.email, ep.created_at FROM event_participants ep
            JOIN users u ON u.id = ep.user_id
            WHERE ep.event_id = ?
            ORDER BY ep.created_at
            """,
            (e["id"],),
        ).fetchall()
        event_list.append({"row": e, "attendees": attendees})

    db.close()
    return render_template(
        "admin.html", subscribers=subscribers, users=users, events=event_list
    )


init_db()

if __name__ == "__main__":
    app.run(debug=True, port=int(os.environ.get("PORT", 5050)))
