# Деплой: Firebase в облаке, фронтенд и сервисы команд на VPS

Схема:

```
Google Firebase (облако)                 VPS (Ubuntu, root)
├─ Firestore                             ├─ nginx  :80/:443
├─ Cloud Functions (Python)   ◄──HTTP──► │    / → статика frontend (dist)
├─ Auth (Email/Password)                 ├─ securenotes ×N (Docker) :8001 :8002 …
└─ Scheduler (чекер раундов)             └─ firebase-tools + node (только для деплоя/сборки)
```

Firebase — единственное, что в облаке Google. Всё остальное на VPS.

---

## 0. Предварительно на VPS

```bash
apt update
apt install -y docker.io nginx nodejs npm python3-venv git
systemctl enable --now docker
node -v        # нужен >= 18 (в Ubuntu 24.04 из apt идёт 18.x — ок)
```

## 1. Проект Firebase (один раз, через браузер)

1. console.firebase.google.com → **Add project**.
2. Переключить биллинг на **Blaze** (нужен для планировщика чекера и исходящих HTTP —
   у Blaze есть бесплатный лимит, для учебного турнира счёт близок к нулю).
3. **Authentication → Sign-in method → Email/Password → Enable**.
4. **Project settings → General → Your apps → Web app (</>)** → скопировать `firebaseConfig`
   (apiKey, authDomain, projectId, appId).
5. **Project settings → Service accounts → Generate new private key** → скачать JSON
   (понадобится для seed).

## 2. Задеплоить бэкенд на Firebase (команды с VPS)

```bash
npm install -g firebase-tools
firebase login --no-localhost      # headless VPS: откроет ссылку, вставишь код
cd ~/live-ctf
firebase use --add                 # выбрать свой проект, алиас: default

# venv нужен CLI для сборки Python-функций
cd functions && python3 -m venv venv && . venv/bin/activate \
  && pip install -r requirements.txt && deactivate && cd ..

firebase deploy --only firestore,functions
```

## 3. Наполнить Firestore демо-данными (с VPS, в реальное облако)

```bash
# сервисный ключ из шага 1.5
export GOOGLE_APPLICATION_CREDENTIALS=~/live-ctf/serviceAccount.json
export GOOGLE_CLOUD_PROJECT=<ВАШ-project-id>
# ВАЖНО: НЕ задавать FIRESTORE_EMULATOR_HOST — иначе уйдёт в эмулятор, а не в облако

pip install -r scripts/requirements.txt --break-system-packages
python3 scripts/seed.py --with-users \
  --alpha-url http://<IP-VPS>:8001 \
  --beta-url  http://<IP-VPS>:8002
```

## 4. Сервисы команд (Docker на VPS)

```bash
cd ~/live-ctf
docker build -t securenotes challenges/01-securenotes
docker run -d --restart=always -p 8001:8000 --name alpha securenotes
docker run -d --restart=always -p 8002:8000 --name beta  securenotes
curl http://localhost:8001/health      # ok
```

Открыть порты команд наружу (чтобы соперники и чекер достучались):

```bash
ufw allow 8001/tcp && ufw allow 8002/tcp
```

## 5. Фронтенд на VPS (сборка + nginx)

```bash
cd ~/live-ctf/frontend
cat > .env.local <<ENV
VITE_FIREBASE_API_KEY=<apiKey>
VITE_FIREBASE_AUTH_DOMAIN=<project>.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=<project>
VITE_FIREBASE_APP_ID=<appId>
VITE_USE_EMULATOR=false
ENV
npm install && npm run build          # соберёт dist/
mkdir -p /var/www/live-ctf && cp -r dist/* /var/www/live-ctf/
```

nginx (SPA-fallback на index.html):

```bash
cat > /etc/nginx/sites-available/live-ctf <<'NGINX'
server {
    listen 80;
    server_name _;
    root /var/www/live-ctf;
    index index.html;
    location / { try_files $uri $uri/ /index.html; }
}
NGINX
ln -sf /etc/nginx/sites-available/live-ctf /etc/nginx/sites-enabled/live-ctf
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx
```

Фронтенд открыт на `http://<IP-VPS>/`. Запросы к Firestore/Functions/Auth идут напрямую
из браузера в облако Firebase — проксировать их через nginx не нужно.

## 6. TLS (рекомендуется — иначе Firebase Auth капризничает по http)

```bash
apt install -y certbot python3-certbot-nginx
certbot --nginx -d ctf.example.com      # нужен домен, указывающий на IP VPS
```

Добавь домен в **Firebase → Authentication → Settings → Authorized domains**.

---

## Игровой цикл после деплоя

- Раунды идут сами (запланированная функция каждые 5 мин) либо вручную из «Админ».
- Демо-аккаунты (seed): `admin@live.ctf`, `alpha@live.ctf`, `beta@live.ctf` / `password123`.
- Команды правят свою копию сервиса и перезапускают контейнер:
  `docker restart alpha`.

## Типовые проблемы

- **`firebase deploy` по функциям падает** → проверь, что в `functions/` есть `venv` и что
  выбран Python 3.12-совместимый рантайм (в `firebase.json` уже `python312`).
- **seed ушёл «в никуда»** → снята ли переменная `FIRESTORE_EMULATOR_HOST`? В облаке её быть
  не должно.
- **Auth не пускает** → домен фронтенда добавлен в Authorized domains; при http используй TLS.
- **Чекер не видит сервис команды** → URL должен быть публичным (`http://IP:8001`), порт открыт
  в `ufw` и в firewall провайдера.

---

## Встроенный редактор кода + агент деплоя (страница «Мой код»)

Игрок правит код своего сервиса прямо в браузере и жмёт «Сохранить и задеплоить».
На VPS работает **агент** (по одному на команду), который слушает Firestore и
пересоздаёт контейнер команды, затем прогоняет чекер и пишет результат обратно.

### 1. Инициализировать код команд (один раз)
```bash
cd ~/live-ctf
export GOOGLE_APPLICATION_CREDENTIALS=~/live-ctf/serviceAccount.json
export GOOGLE_CLOUD_PROJECT=ctf-go
unset FIRESTORE_EMULATOR_HOST
pip install -r scripts/requirements.txt --break-system-packages
python3 scripts/set_team_code.py           # зальёт исходный код во все команды
```

### 2. Запустить агентов (по одному на команду, в tmux)
```bash
docker build -t securenotes challenges/01-securenotes   # образ нужен агенту
tmux new -s agents
# внутри tmux — окно на команду (Ctrl+B, C — новое окно):
export GOOGLE_APPLICATION_CREDENTIALS=~/live-ctf/serviceAccount.json
export GOOGLE_CLOUD_PROJECT=ctf-go
python3 scripts/deploy_agent.py --team team-alpha --container alpha --port 8001 --public-host 89.39.121.189
# второе окно:
python3 scripts/deploy_agent.py --team team-beta  --container beta  --port 8002 --public-host 89.39.121.189
```

Теперь на странице «Мой код» кнопка «Сохранить и задеплоить» реально пересоздаёт
сервис команды, а поля «уязвимости N/4» и «SLA» показывают результат чекера.

> Новые функции (`save_and_deploy`, `admin_*`) нужно задеплоить: `firebase deploy --only functions`,
> и сделать их публичными в Cloud Run (как остальные callable — Allow unauthenticated).
