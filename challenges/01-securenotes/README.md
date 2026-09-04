# Задание 01 — SecureNotes (базовый уровень)

Мини-сервис заметок на Flask + SQLite. Пользователи регистрируются, логинятся,
создают приватные заметки и читают свои. Каждый раунд game-master кладёт в сервис
**флаг** в приватную заметку бота `gamemaster`.

## Ваша задача (attack-defense)

1. **Defense.** Найдите уязвимости в этой копии и закройте их, **не сломав API**
   (по нему ходит чекер — сломаете, потеряете SLA-очки).
2. **Attack.** Одновременно эксплуатируйте те же уязвимости в сервисе соперника,
   доставайте его флаг и сдавайте на платформе, пока он не запатчился.

Флаг имеет формат `LIVECTF{...}`.

## Запуск своей копии

```bash
# через Docker (штатно, как в проде)
docker build -t securenotes challenges/01-securenotes
docker run -p 8000:8000 securenotes

# или локально
cd challenges/01-securenotes
pip install -r requirements.txt
python app.py           # http://localhost:8000
```

Затем зарегистрируйте URL своего сервиса на платформе (страница «Мой сервис»).

## API

| Метод | Путь            | Описание                                   |
|-------|-----------------|--------------------------------------------|
| GET   | `/health`       | проверка живости                           |
| POST  | `/register`     | `{username, password}`                     |
| POST  | `/login`        | `{username, password}` → `{token}`         |
| POST  | `/notes`        | `{title, body}` (Bearer) → `{id}`          |
| GET   | `/notes/mine`   | свои заметки (Bearer)                       |
| GET   | `/notes/<id>`   | заметка по id (Bearer)                      |
| GET   | `/search?q=`    | поиск по заголовку (Bearer)                |
| GET   | `/debug`        | служебная информация                       |

## Само-проверка

```bash
python checker.py sla     http://localhost:8000   # SLA должен быть OK
python checker.py exploit http://localhost:8000   # покажет активные уязвимости
```

После правильных фиксов: `exploit` показывает 0/4, а `sla` — OK.

> Подсказки по классам уязвимостей: инъекции, контроль доступа (IDOR),
> криптография/секреты, раскрытие информации. Всего заложено несколько дыр.
