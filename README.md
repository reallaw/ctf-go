# live-ctf — Attack/Defense CTF платформа

«Живой» attack-defense CTF на Google Firebase. Командам выдаётся одинаковый уязвимый
Python-сервис: они ищут и чинят дыры в своей копии и одновременно атакуют копию соперника,
пока тот не запатчился. Платформа раздаёт/принимает флаги и в реальном времени считает
очки **атаки / защиты / SLA**.

## Как устроено

```
┌─────────────┐   callable    ┌──────────────────┐   HTTP    ┌───────────────────┐
│ React (SPA) │ ────────────► │  Cloud Functions │ ────────► │ Сервисы команд    │
│  Hosting    │ ◄──realtime── │  (Python)        │  plant/   │ (Flask, у команд) │
└─────────────┘   Firestore   │  submit_flag     │  SLA      └───────────────────┘
                              │  register_service│
                              │  admin_start_round│
                              │  scheduled checker│
                              └────────┬─────────┘
                                       │ Admin SDK
                                  ┌────▼─────┐
                                  │ Firestore│  teams / competitions / rounds
                                  │          │  flags / submissions / checks
                                  └──────────┘
```

- **Флаги** хранятся только как SHA-256 — утечка БД не раскроет действующие флаги.
- **Запись очков/флагов/сабмитов** идёт только через Cloud Functions; правила Firestore
  запрещают клиенту писать в эти коллекции напрямую.
- Сами сервисы команд Firebase не хостит — команды поднимают их сами (Docker/Cloud Run/
  ngrok) и регистрируют URL; чекер (Cloud Function) ходит к ним по этому URL.

## Компоненты

| Каталог                     | Что это                                             |
|-----------------------------|-----------------------------------------------------|
| `frontend/`                 | React + Vite SPA (табло, кабинет, сдача флагов, админка) |
| `functions/`                | Cloud Functions на Python (чекер, submit_flag, ...) |
| `challenges/01-securenotes/`| Первое задание: уязвимый Flask-сервис + эталонный чекер |
| `scripts/seed.py`           | Демо-соревнование и команды                          |

## Быстрый старт (локально, через эмулятор)

Нужны: Node 18+, Python 3.12, `firebase-tools` (`npm i -g firebase-tools`), Docker (опц.).

### 1. Поднять уязвимые сервисы двух команд
```bash
docker build -t securenotes challenges/01-securenotes
docker run -d -p 8001:8000 --name alpha securenotes
docker run -d -p 8002:8000 --name beta  securenotes
# или без Docker: PORT=8001 python challenges/01-securenotes/app.py
```

### 2. Запустить эмуляторы Firebase
```bash
cd functions && python -m venv venv && . venv/bin/activate && pip install -r requirements.txt && cd ..
firebase emulators:start
```

### 3. Заполнить демо-данные
```bash
export FIRESTORE_EMULATOR_HOST=localhost:8080
export FIREBASE_AUTH_EMULATOR_HOST=localhost:9099
export GOOGLE_CLOUD_PROJECT=live-ctf-demo
pip install -r scripts/requirements.txt
python scripts/seed.py --with-users --alpha-url http://host.docker.internal:8001 --beta-url http://host.docker.internal:8002
```
> В Linux вместо `host.docker.internal` укажите IP хоста или запускайте сервис без Docker
> и используйте `http://localhost:8001`.

### 4. Запустить фронтенд
```bash
cd frontend
cp .env.example .env.local     # VITE_USE_EMULATOR=true уже стоит
npm install && npm run dev      # http://localhost:5173
```
Демо-аккаунты (пароль `password123`): `admin@live.ctf`, `alpha@live.ctf`, `beta@live.ctf`.

## Игровой цикл

1. **Админ** («Админ» → «Запустить раунд») или запланированная функция каждые 5 минут:
   генерирует флаг для каждой команды, сажает его в её сервис, проверяет SLA.
2. **Команда** правит свою копию, чинит уязвимости (см. задание), перезапускает сервис.
3. **Атака:** эксплуатирует дыру в сервисе соперника, достаёт его флаг, сдаёт в «Кабинете».
4. **Очки:** атака за сданный флаг, защита за раунд без утечки, SLA за живой сервис —
   всё видно на «Табло» в реальном времени.

## Проверка (end-to-end)

```bash
# уязвимость подтверждается
python challenges/01-securenotes/checker.py exploit http://localhost:8001   # 4/4
python challenges/01-securenotes/checker.py sla     http://localhost:8001   # OK
# после фиксов (см. challenges/01-securenotes/SOLUTION.md) — 0/4 и SLA OK
```

## Деплой в облако

```bash
cd frontend && npm run build && cd ..
firebase deploy   # hosting + functions + firestore rules/indexes
```
Перед деплоем задайте секреты сервисов и настоящий Firebase-конфиг в `frontend/.env.local`,
а `VITE_USE_EMULATOR` уберите/поставьте `false`.
