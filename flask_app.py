from flask import Flask, redirect, render_template, request, url_for
from dotenv import load_dotenv
import os
import git
import hmac
import hashlib
from db import db_read, db_write
from auth import login_manager, authenticate, register_user
from flask_login import login_user, logout_user, login_required, current_user
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# Load .env variables
load_dotenv()
W_SECRET = os.getenv("W_SECRET")

# Init flask app
app = Flask(__name__)
app.config["DEBUG"] = True
app.secret_key = "supersecret"

# Init auth
login_manager.init_app(app)
login_manager.login_view = "login"

# DON'T CHANGE
def is_valid_signature(x_hub_signature, data, private_key):
    hash_algorithm, github_signature = x_hub_signature.split('=', 1)
    algorithm = hashlib.__dict__.get(hash_algorithm)
    encoded_key = bytes(private_key, 'latin-1')
    mac = hmac.new(encoded_key, msg=data, digestmod=algorithm)
    return hmac.compare_digest(mac.hexdigest(), github_signature)

# DON'T CHANGE
@app.post('/update_server')
def webhook():
    x_hub_signature = request.headers.get('X-Hub-Signature')
    if is_valid_signature(x_hub_signature, request.data, W_SECRET):
        repo = git.Repo('./mysite')
        origin = repo.remotes.origin
        origin.pull()
        return 'Updated PythonAnywhere successfully', 200
    return 'Unathorized', 401

# Auth routes
@app.route("/login", methods=["GET", "POST"])
def login():
    error = None

    if request.method == "POST":
        user = authenticate(
            request.form["username"],
            request.form["password"]
        )

        if user:
            login_user(user)
            return redirect(url_for("index"))

        error = "Benutzername oder Passwort ist falsch."

    return render_template(
        "auth.html",
        title="In dein Konto einloggen",
        action=url_for("login"),
        button_label="Einloggen",
        error=error,
        footer_text="Noch kein Konto?",
        footer_link_url=url_for("register"),
        footer_link_label="Registrieren"
    )


@app.route("/register", methods=["GET", "POST"])
def register():
    error = None

    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        ok = register_user(username, password)
        if ok:
            return redirect(url_for("login"))

        error = "Benutzername existiert bereits."

    return render_template(
        "auth.html",
        title="Neues Konto erstellen",
        action=url_for("register"),
        button_label="Registrieren",
        error=error,
        footer_text="Du hast bereits ein Konto?",
        footer_link_url=url_for("login"),
        footer_link_label="Einloggen"
    )

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("index"))



# App routes
@app.route("/", methods=["GET"])
@login_required
def index():
    faecher = db_read("""
        SELECT 
            f.id,
            f.fachname,
            s.name AS semester,
            ROUND(AVG(n.notenwert), 2) AS durchschnitt,
            COALESCE(SUM(n.notenwert - 4), 0) AS punkte
        FROM fach f
        JOIN semester s ON f.semester_id = s.id
        LEFT JOIN note n ON n.fach_id = f.id
        WHERE f.schueler_id = %s
        GROUP BY f.id, s.name
        ORDER BY s.id, f.fachname
    """, (current_user.id,))

    return render_template("main_page.html", faecher=faecher)


@app.route("/fach/<int:fach_id>")
@login_required
def fach(fach_id):
    noten = db_read("""
        SELECT titel, notenwert, gewichtung, datum,
               (notenwert - 4) AS punkte
        FROM note
        WHERE fach_id = %s
        ORDER BY datum
    """, (fach_id,))

    fachname = db_read("SELECT fachname FROM fach WHERE id=%s", (fach_id,))[0]["fachname"]

    return render_template("fach.html", noten=noten, fachname=fachname)


@app.route("/note/add", methods=["POST"])
@login_required
def add_note():
    fach_id = request.form["fach_id"]
    titel = request.form["titel"]
    wert = request.form["notenwert"]
    gewichtung = request.form["gewichtung"]
    datum = request.form["datum"]

    db_write("""
        INSERT INTO note (titel, notenwert, gewichtung, datum, fach_id)
        VALUES (%s, %s, %s, %s, %s)
    """, (titel, wert, gewichtung, datum, fach_id))

    return redirect(url_for("fach", fach_id=fach_id))


@app.route("/semester")
@login_required
def semester():
    semester = db_read("""
        SELECT 
            s.id,
            s.name,
            SUM(n.notenwert - 4) AS punkte,
            CASE 
                WHEN SUM(n.notenwert - 4) >= 0 THEN 'Bestanden'
                ELSE 'Nicht bestanden'
            END AS status
        FROM semester s
        JOIN fach f ON f.semester_id = s.id
        LEFT JOIN note n ON n.fach_id = f.id
        WHERE f.schueler_id = %s
        GROUP BY s.id
        ORDER BY s.id
    """, (current_user.id,))

    return render_template("semester.html", semester=semester)

if __name__ == "__main__":
    app.run()
