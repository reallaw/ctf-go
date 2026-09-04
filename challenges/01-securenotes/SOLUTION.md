# SecureNotes — разбор уязвимостей и эталонные фиксы (ПРИВАТНО, для организаторов)

> Не выдавайте игрокам. Здесь перечислены все заложенные дыры и правильные исправления,
> которые закрывают эксплойт, **не ломая** SLA-проверку чекера.

## Уязвимость 1 — SQL-инъекция (`/register`, `/login`, `/search`)
**Где:** f-string прямо в SQL.
**Эксплойт:** `username = "gamemaster' -- "` в `/login` → обход пароля;
`q = "%' UNION SELECT ..."` в `/search` → дамп чужих заметок.
**Фикс:** параметризованные запросы во всех местах:
```python
db.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
db.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
db.execute("SELECT ... FROM notes WHERE title LIKE ?", (f"%{q}%",))
```
Плюс хранить хеш пароля (`werkzeug.security.generate_password_hash`), а не открытый текст.

## Уязвимость 2 — IDOR (`GET /notes/<id>`)
**Где:** заметка отдаётся по id без проверки владельца.
**Эксплойт:** перебор `/notes/1..N` любым залогиненным пользователем → чужой флаг.
**Фикс:** фильтровать по владельцу:
```python
row = db.execute("SELECT id,title,body FROM notes WHERE id=? AND owner=?",
                 (note_id, user)).fetchone()
```
Аналогично убрать `owner` из выдачи `/search` и фильтровать `WHERE owner=?`.

## Уязвимость 3 — Небезопасные токены / захардкоженный секрет
**Где:** `make_token` = `base64(username)` без подписи; `SECRET_KEY` в коде.
**Эксплойт:** `base64("gamemaster")` → токен бота → чтение флага через `/notes/mine`.
**Фикс:** подписанные токены с секретом из окружения:
```python
from itsdangerous import URLSafeTimedSerializer
SECRET_KEY = os.environ["SECRET_KEY"]          # из env, у каждого свой
serializer = URLSafeTimedSerializer(SECRET_KEY)
def make_token(u): return serializer.dumps(u)
def current_user():
    ...
    return serializer.loads(token, max_age=3600)  # исключение → 401
```
Чекер логинится штатно и получает валидный токен, поэтому SLA не ломается.

## Уязвимость 4 — Раскрытие информации (`/debug`, `debug=True`)
**Где:** эндпоинт `/debug` отдаёт секрет и `os.environ`; `app.run(debug=True)`.
**Фикс:** удалить эндпоинт `/debug` полностью; запускать через gunicorn (уже так в
Dockerfile) и никогда не включать `debug=True` в проде.

## Проверка после фиксов
```bash
python checker.py exploit http://localhost:8000   # ожидаем 0/4
python checker.py sla     http://localhost:8000   # ожидаем OK
```
