from flask import Flask, redirect, render_template, request, url_for
from mysql.connector import pooling
from dotenv import load_dotenv
import os
import git

load_dotenv()

DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "database": os.getenv("DB_DATABASE")
}
GIT_REPO = os.getenv("GIT_REPO")

app = Flask(__name__)
app.config["DEBUG"] = True

pool = pooling.MySQLConnectionPool(pool_name="pool", pool_size=5, **DB_CONFIG)

def get_conn():
    return pool.get_connection()


@app.route('/update_server', methods=['POST'])
def webhook():
    if request.method == 'POST':
        repo = git.Repo(GIT_REPO)
        origin = repo.remotes.origin
        origin.pull()
        return 'Updated PythonAnywhere successfully', 200
    return 'Wrong event type', 400

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "GET":
        conn = get_conn()
        try:
            cur = conn.cursor(dictionary=True)
            cur.execute("SELECT id, content, date FROM todos ORDER BY date")
            todos = cur.fetchall()
        finally:
            try:
                cur.close()
            except:
                pass
            conn.close()

        return render_template("main_page.html", todos=todos)

    # POST
    content = request.form["contents"]
    date = request.form["due_at"]
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("INSERT INTO todos (content, `date`) VALUES (%s, %s)", (content, date, ))
        conn.commit()
    finally:
        try:
            cur.close()
        except:
            pass
        conn.close()

    return redirect(url_for("index"))

@app.post("/complete")
def complete():

    # POST
    todo_id = request.form.get("id")
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM todos WHERE id=%s", (todo_id,))
        conn.commit()
    finally:
        try:
            cur.close()
        except:
            pass
        conn.close()

    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run()
