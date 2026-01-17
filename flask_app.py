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
from datetime import date

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

# HILFSFUNKTION: Pluspunkte nach Schweizer System berechnen
def berechne_pluspunkte(notenwert):
    """
    Schweizer System (Mathematische Formel):
    1. Runde Note auf halbe Noten (z.B. 5.23 → 5.0)
    2. Wenn Note >= 4: P(g) = g - 4
    3. Wenn Note < 4:  P(g) = 2 * (g - 4)
    """
    # Auf halbe Noten runden (0.5er Schritte)
    gerundete_note = round(notenwert * 2) / 2
    
    if gerundete_note >= 4.0:
        return gerundete_note - 4.0
    else:
        return 2.0 * (gerundete_note - 4.0)

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

# SEMESTER ROUTES
@app.route("/semester/add", methods=["GET", "POST"])
@login_required
def add_semester():
    if request.method == "POST":
        name = request.form["name"]
        
        db_write(
            "INSERT INTO semester (name, user_id) VALUES (%s, %s)",
            (name, current_user.id)
        )
        
        return redirect(url_for("semester_list"))
    
    return render_template("semester_add.html")

@app.route("/semester")
@login_required
def semester_list():
    semester = db_read("""
        SELECT
            s.id,
            s.name,
            COUNT(DISTINCT f.id) AS anzahl_faecher,
            ROUND(AVG(n.notenwert), 2) AS durchschnitt,
            ROUND(SUM(
                CASE 
                    WHEN ROUND(
                        (SUM(n.notenwert * n.gewichtung) / SUM(n.gewichtung)) * 2
                    ) / 2 >= 4.0 
                    THEN ROUND((SUM(n.notenwert * n.gewichtung) / SUM(n.gewichtung)) * 2) / 2 - 4.0
                    ELSE 2.0 * (ROUND((SUM(n.notenwert * n.gewichtung) / SUM(n.gewichtung)) * 2) / 2 - 4.0)
                END
            ), 2) AS pluspunkte
        FROM semester s
        LEFT JOIN fach f ON f.semester_id = s.id
        LEFT JOIN note n ON n.fach_id = f.id
        WHERE s.user_id = %s
        GROUP BY s.id
        ORDER BY s.id DESC
    """, (current_user.id,))

    return render_template("semester.html", semester=semester)

@app.route("/semester/<int:semester_id>")
@login_required
def semester_detail(semester_id):
    # Semester-Info holen
    semester_info = db_read("""
        SELECT id, name FROM semester WHERE id = %s AND user_id = %s
    """, (semester_id, current_user.id), single=True)
    
    if not semester_info:
        return "Semester nicht gefunden", 404
    
    # Fächer in diesem Semester
    faecher = db_read("""
        SELECT
            f.id,
            f.fachname,
            f.lehrer,
            f.fachgewichtung,
            COUNT(n.id) AS anzahl_noten
        FROM fach f
        LEFT JOIN note n ON n.fach_id = f.id
        WHERE f.semester_id = %s
        GROUP BY f.id
        ORDER BY f.fachname
    """, (semester_id,))
    
    # Für jedes Fach: Durchschnitt und Pluspunkte berechnen
    for fach in faecher:
        noten = db_read("""
            SELECT notenwert, gewichtung
            FROM note
            WHERE fach_id = %s
        """, (fach["id"],))
        
        if noten:
            total_gewichtung = sum(n["gewichtung"] for n in noten)
            if total_gewichtung > 0:
                durchschnitt = sum(n["notenwert"] * n["gewichtung"] for n in noten) / total_gewichtung
                fach["durchschnitt"] = round(durchschnitt, 2)
                
                # Runde auf halbe Noten
                gerundet = round(durchschnitt * 2) / 2
                # Berechne Pluspunkte
                if gerundet >= 4.0:
                    pluspunkte = gerundet - 4.0
                else:
                    pluspunkte = 2.0 * (gerundet - 4.0)
                
                fach["pluspunkte"] = round(pluspunkte, 2)
            else:
                fach["durchschnitt"] = None
                fach["pluspunkte"] = None
        else:
            fach["durchschnitt"] = None
            fach["pluspunkte"] = None
    
    return render_template("semester_detail.html", semester=semester_info, faecher=faecher)

# FACH ROUTES
@app.route("/fach/add/<int:semester_id>", methods=["GET", "POST"])
@login_required
def add_fach(semester_id):
    if request.method == "POST":
        fachname = request.form["fachname"]
        lehrer = request.form["lehrer"]
        fachgewichtung = request.form["fachgewichtung"]

        db_write("""
            INSERT INTO fach (fachname, lehrer, fachgewichtung, semester_id, user_id)
            VALUES (%s, %s, %s, %s, %s)
        """, (fachname, lehrer, fachgewichtung, semester_id, current_user.id))

        return redirect(url_for("semester_detail", semester_id=semester_id))
    
    # Semester-Name für die Anzeige holen
    semester_info = db_read(
        "SELECT name FROM semester WHERE id = %s AND user_id = %s",
        (semester_id, current_user.id),
        single=True
    )
    
    if not semester_info:
        return "Semester nicht gefunden", 404
    
    return render_template("fach_add.html", semester_id=semester_id, semester_name=semester_info["name"])

@app.route("/fach/<int:fach_id>")
@login_required
def fach(fach_id):
    # Fach-Info holen
    fach_info = db_read("""
        SELECT f.id, f.fachname, f.lehrer, f.fachgewichtung, s.name AS semester_name, f.semester_id
        FROM fach f
        JOIN semester s ON f.semester_id = s.id
        WHERE f.id = %s AND f.user_id = %s
    """, (fach_id, current_user.id), single=True)
    
    if not fach_info:
        return "Fach nicht gefunden", 404
    
    # Noten holen
    noten = db_read("""
        SELECT
            id,
            titel,
            notenwert,
            gewichtung,
            datum,
            ROUND(
                CASE 
                    WHEN ROUND(notenwert * 2) / 2 >= 4.0 THEN ROUND(notenwert * 2) / 2 - 4.0
                    ELSE 2.0 * (ROUND(notenwert * 2) / 2 - 4.0)
                END
            , 2) AS pluspunkte
        FROM note
        WHERE fach_id = %s
        ORDER BY datum DESC
    """, (fach_id,))
    
    # Durchschnitt berechnen (gewichtet)
    if noten:
        total_gewichtung = sum(n["gewichtung"] for n in noten)
        if total_gewichtung > 0:
            durchschnitt = sum(n["notenwert"] * n["gewichtung"] for n in noten) / total_gewichtung
            durchschnitt = round(durchschnitt, 2)
        else:
            durchschnitt = None
        
        total_pluspunkte = sum(n["pluspunkte"] for n in noten)
        total_pluspunkte = round(total_pluspunkte, 2)
    else:
        durchschnitt = None
        total_pluspunkte = 0

    return render_template(
        "fach.html",
        fach=fach_info,
        noten=noten,
        durchschnitt=durchschnitt,
        total_pluspunkte=total_pluspunkte
    )

# NOTEN ROUTES
@app.route("/note/add/<int:fach_id>", methods=["GET", "POST"])
@login_required
def add_note(fach_id):
    if request.method == "POST":
        titel = request.form["titel"]
        notenwert = float(request.form["notenwert"])
        gewichtung = float(request.form["gewichtung"])
        datum = request.form["datum"]

        db_write("""
            INSERT INTO note (titel, notenwert, gewichtung, datum, fach_id)
            VALUES (%s, %s, %s, %s, %s)
        """, (titel, notenwert, gewichtung, datum, fach_id))

        return redirect(url_for("fach", fach_id=fach_id))
    
    # Fach-Info für Anzeige
    fach_info = db_read("""
        SELECT f.fachname, f.semester_id
        FROM fach f
        WHERE f.id = %s AND f.user_id = %s
    """, (fach_id, current_user.id), single=True)
    
    if not fach_info:
        return "Fach nicht gefunden", 404
    
    return render_template("note_add.html", fach_id=fach_id, fachname=fach_info["fachname"])

# HAUPTSEITE - Direkt zur Semester-Übersicht
@app.route("/")
@login_required
def index():
    return redirect(url_for("semester_list"))

# LÖSCHEN-FUNKTIONEN
@app.route("/semester/delete/<int:semester_id>", methods=["POST"])
@login_required
def delete_semester(semester_id):
    # Überprüfen ob das Semester dem User gehört
    semester = db_read(
        "SELECT id FROM semester WHERE id = %s AND user_id = %s",
        (semester_id, current_user.id),
        single=True
    )
    
    if not semester:
        return "Semester nicht gefunden", 404
    
    # Semester löschen (CASCADE löscht automatisch Fächer und Noten)
    db_write("DELETE FROM semester WHERE id = %s", (semester_id,))
    
    return redirect(url_for("semester_list"))

@app.route("/fach/delete/<int:fach_id>", methods=["POST"])
@login_required
def delete_fach(fach_id):
    # Überprüfen ob das Fach dem User gehört
    fach = db_read(
        "SELECT semester_id FROM fach WHERE id = %s AND user_id = %s",
        (fach_id, current_user.id),
        single=True
    )
    
    if not fach:
        return "Fach nicht gefunden", 404
    
    semester_id = fach["semester_id"]
    
    # Fach löschen (CASCADE löscht automatisch Noten)
    db_write("DELETE FROM fach WHERE id = %s", (fach_id,))
    
    return redirect(url_for("semester_detail", semester_id=semester_id))

@app.route("/note/delete/<int:note_id>", methods=["POST"])
@login_required
def delete_note(note_id):
    # Fach-ID holen für Redirect
    note_info = db_read(
        """SELECT n.fach_id 
           FROM note n
           JOIN fach f ON n.fach_id = f.id
           WHERE n.id = %s AND f.user_id = %s""",
        (note_id, current_user.id),
        single=True
    )
    
    if not note_info:
        return "Note nicht gefunden", 404
    
    fach_id = note_info["fach_id"]
    
    # Note löschen
    db_write("DELETE FROM note WHERE id = %s", (note_id,))
    
    return redirect(url_for("fach", fach_id=fach_id))

if __name__ == "__main__":
    app.run()