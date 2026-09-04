"""SecureNotes — учебный уязвимый сервис заметок (задание 01, базовый уровень).

ВНИМАНИЕ: это НАМЕРЕННО уязвимый код для attack-defense CTF. Задача команды —
найти уязвимости, закрыть их в своей копии и, не сломав функциональность,
атаковать копию соперника. Эталонные исправления — в SOLUTION.md.

API (протокол задания, менять его нельзя — по нему ходит чекер):
  GET  /health                      -> 200 "ok"
  POST /register {username,password} -> 201
  POST /login    {username,password} -> {token}
  POST /notes    {title,body}  (Bearer) -> 201 {id}
  GET  /notes/mine             (Bearer) -> {notes:[...]}
  GET  /notes/<id>             (Bearer) -> {note}
  GET  /search?q=...           (Bearer) -> {notes:[...]}
  GET  /debug                          -> служебная информация
"""

import base64
import os
import sqlite3

from flask import Flask, g, jsonify, request

app = Flask(__name__)

# [УЯЗВИМОСТЬ 3] Секрет захардкожен прямо в коде и одинаков у всех команд.
# Плюс токен ниже вообще не подписывается этим секретом.
SECRET_KEY = "supersecret123"

DB_PATH = os.environ.get("SECURENOTES_DB", "/tmp/securenotes.db")


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner TEXT NOT NULL,
            title TEXT NOT NULL,
            body TEXT NOT NULL
        );
        """
    )
    db.commit()
    db.close()


# --------------------------------------------------------------------------- #
# Аутентификация                                                              #
# --------------------------------------------------------------------------- #
def make_token(username: str) -> str:
    # [УЯЗВИМОСТЬ 3] Токен = base64(username), без подписи. Кто угодно может
    # сгенерировать токен любого пользователя (включая gamemaster).
    return base64.urlsafe_b64encode(username.encode()).decode()


def current_user():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth[len("Bearer "):]
    try:
        return base64.urlsafe_b64decode(token.encode()).decode()
    except Exception:
        return None


# --------------------------------------------------------------------------- #
# Эндпоинты                                                                    #
# --------------------------------------------------------------------------- #
@app.route("/health")
def health():
    return "ok", 200


@app.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "")
    password = data.get("password", "")
    if not username or not password:
        return jsonify({"error": "username и password обязательны"}), 400
    db = get_db()
    try:
        # [УЯЗВИМОСТЬ 1] Пароль в открытом виде + строковая интерполяция в SQL.
        db.execute(
            f"INSERT INTO users (username, password) VALUES ('{username}', '{password}')"
        )
        db.commit()
    except sqlite3.IntegrityError:
        # Позволяем «перерегистрацию» с новым паролем (нужно чекеру раунда).
        db.execute(
            f"UPDATE users SET password='{password}' WHERE username='{username}'"
        )
        db.commit()
    return jsonify({"ok": True}), 201


@app.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "")
    password = data.get("password", "")
    db = get_db()
    # [УЯЗВИМОСТЬ 1] Классическая SQL-инъекция: ' OR '1'='1 обходит проверку.
    row = db.execute(
        f"SELECT * FROM users WHERE username='{username}' AND password='{password}'"
    ).fetchone()
    if row is None:
        return jsonify({"error": "неверные учётные данные"}), 401
    return jsonify({"token": make_token(row["username"])}), 200


@app.route("/notes", methods=["POST"])
def create_note():
    user = current_user()
    if not user:
        return jsonify({"error": "unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    title = data.get("title", "")
    body = data.get("body", "")
    db = get_db()
    cur = db.execute(
        "INSERT INTO notes (owner, title, body) VALUES (?, ?, ?)",
        (user, title, body),
    )
    db.commit()
    return jsonify({"id": cur.lastrowid}), 201


@app.route("/notes/mine")
def my_notes():
    user = current_user()
    if not user:
        return jsonify({"error": "unauthorized"}), 401
    db = get_db()
    rows = db.execute(
        "SELECT id, title, body FROM notes WHERE owner = ?", (user,)
    ).fetchall()
    return jsonify({"notes": [dict(r) for r in rows]}), 200


@app.route("/notes/<int:note_id>")
def get_note(note_id):
    user = current_user()
    if not user:
        return jsonify({"error": "unauthorized"}), 401
    db = get_db()
    # [УЯЗВИМОСТЬ 2] IDOR: заметка отдаётся по id без проверки владельца.
    row = db.execute(
        "SELECT id, owner, title, body FROM notes WHERE id = ?", (note_id,)
    ).fetchone()
    if row is None:
        return jsonify({"error": "not found"}), 404
    return jsonify({"note": dict(row)}), 200


@app.route("/search")
def search():
    user = current_user()
    if not user:
        return jsonify({"error": "unauthorized"}), 401
    q = request.args.get("q", "")
    db = get_db()
    # [УЯЗВИМОСТЬ 1] Ещё одна SQL-инъекция + отсутствует фильтр по владельцу.
    rows = db.execute(
        f"SELECT id, owner, title, body FROM notes WHERE title LIKE '%{q}%'"
    ).fetchall()
    return jsonify({"notes": [dict(r) for r in rows]}), 200


@app.route("/debug")
def debug():
    # [УЯЗВИМОСТЬ 4] Утечка служебной информации: секрет, переменные окружения,
    # путь к БД. Такого эндпоинта в проде быть не должно.
    return jsonify(
        {
            "secret_key": SECRET_KEY,
            "db_path": DB_PATH,
            "env": dict(os.environ),
        }
    ), 200


init_db()

if __name__ == "__main__":
    # [УЯЗВИМОСТЬ 4] debug=True раскрывает интерактивную консоль при ошибке.
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8000")), debug=True)
