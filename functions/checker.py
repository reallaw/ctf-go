"""Логика раунда attack-defense: раздача флагов и SLA-проверка сервисов команд.

Каждый раунд для каждой команды:
  1. генерируется уникальный флаг;
  2. чекер кладёт флаг в сервис команды штатным путём (plant) —
     если это удалось, значит сервис принимает данные;
  3. выполняется SLA-проверка (сервис отвечает и корректно работает).

Флаги хранятся в Firestore ТОЛЬКО в виде хеша: сравнение при сдаче идёт по хешу,
чтобы утечка БД не раскрыла действующие флаги. Сам флаг живёт только в памяти
чекера ровно столько, сколько нужно, чтобы посадить его в сервис.

Протокол взаимодействия с сервисом описан в challenges/01-securenotes:
  POST /register {username, password}
  POST /login    {username, password} -> {token}
  POST /notes    {title, body}  (Authorization: Bearer <token>)
  GET  /notes/mine (Authorization: Bearer <token>)
  GET  /health
"""

from __future__ import annotations

import hashlib
import secrets
import time

import requests
from firebase_admin import firestore

# Бот-аккаунт чекера в каждом сервисе. Пароль генерится на раунд, наружу не отдаётся.
CHECKER_USER = "gamemaster"
HTTP_TIMEOUT = 6  # сек на каждый запрос к сервису команды

FLAG_PREFIX = "LIVECTF"


def make_flag() -> str:
    """Флаг вида LIVECTF{hex}. Формат стабилен — команды знают, что сдавать."""
    return f"{FLAG_PREFIX}{{{secrets.token_hex(16)}}}"


def flag_hash(flag: str) -> str:
    return hashlib.sha256(flag.encode()).hexdigest()


def _base_url(service_url: str) -> str:
    return service_url.rstrip("/")


def plant_flag(service_url: str, flag: str) -> bool:
    """Сажает флаг в приватную заметку бота через штатный API сервиса.

    Возвращает True, если сервис принял флаг. Любая сетевая/HTTP ошибка = False.
    """
    base = _base_url(service_url)
    password = secrets.token_hex(12)
    try:
        # register идемпотентно относительно раунда: имя одно, пароль новый.
        requests.post(
            f"{base}/register",
            json={"username": CHECKER_USER, "password": password},
            timeout=HTTP_TIMEOUT,
        )
        login = requests.post(
            f"{base}/login",
            json={"username": CHECKER_USER, "password": password},
            timeout=HTTP_TIMEOUT,
        )
        if login.status_code != 200:
            return False
        token = login.json().get("token")
        if not token:
            return False
        created = requests.post(
            f"{base}/notes",
            json={"title": "round-flag", "body": flag},
            headers={"Authorization": f"Bearer {token}"},
            timeout=HTTP_TIMEOUT,
        )
        return created.status_code in (200, 201)
    except requests.RequestException:
        return False


def check_sla(service_url: str) -> bool:
    """Базовая проверка работоспособности: health + штатный цикл заметки.

    Команда, сломавшая функциональность при «фиксах», теряет SLA-очки —
    это стимулирует чинить уязвимости, не ломая сервис.
    """
    base = _base_url(service_url)
    try:
        health = requests.get(f"{base}/health", timeout=HTTP_TIMEOUT)
        if health.status_code != 200:
            return False

        # Полный штатный цикл случайного пользователя.
        user = f"sla_{secrets.token_hex(4)}"
        pwd = secrets.token_hex(8)
        marker = secrets.token_hex(8)
        requests.post(
            f"{base}/register", json={"username": user, "password": pwd},
            timeout=HTTP_TIMEOUT,
        )
        login = requests.post(
            f"{base}/login", json={"username": user, "password": pwd},
            timeout=HTTP_TIMEOUT,
        )
        if login.status_code != 200:
            return False
        token = login.json().get("token")
        headers = {"Authorization": f"Bearer {token}"}
        requests.post(
            f"{base}/notes", json={"title": "sla", "body": marker},
            headers=headers, timeout=HTTP_TIMEOUT,
        )
        mine = requests.get(f"{base}/notes/mine", headers=headers, timeout=HTTP_TIMEOUT)
        if mine.status_code != 200:
            return False
        # Штатно пользователь должен видеть свою заметку с маркером.
        return marker in mine.text
    except requests.RequestException:
        return False


def run_round(db, comp_id: str, challenge_id: str) -> dict:
    """Проводит один тик раунда по всем командам активного соревнования.

    Возвращает сводку для логов/ответа админ-функции.
    """
    import scoring  # top-level модуль в codebase функций

    comp_ref = db.collection("competitions").document(comp_id)
    comp = comp_ref.get().to_dict() or {}
    round_no = int(comp.get("currentRound", 0)) + 1

    now = int(time.time())
    duration = int(comp.get("roundDurationSec", 300))
    round_id = f"{comp_id}_{round_no}"
    db.collection("rounds").document(round_id).set(
        {"number": round_no, "startedAt": now, "endsAt": now + duration,
         "competitionId": comp_id}
    )

    teams = list(db.collection("teams").stream())
    summary = {"round": round_no, "teams": [], "planted": 0, "slaOk": 0}

    for team_snap in teams:
        team = team_snap.to_dict()
        team_id = team_snap.id
        service_url = team.get("serviceUrl")
        result = {"teamId": team_id, "planted": False, "slaOk": False}

        if service_url:
            flag = make_flag()
            planted = plant_flag(service_url, flag)
            result["planted"] = planted
            if planted:
                summary["planted"] += 1
                db.collection("flags").add(
                    {
                        "valueHash": flag_hash(flag),
                        "victimTeamId": team_id,
                        "round": round_no,
                        "challengeId": challenge_id,
                        "plantedAt": now,
                        "expiresAt": now + duration,
                        "stolen": False,
                    }
                )
            sla_ok = check_sla(service_url)
            result["slaOk"] = sla_ok
            if sla_ok:
                summary["slaOk"] += 1
                scoring.award_sla(db, team_id)

        db.collection("checks").add(
            {"teamId": team_id, "round": round_no, "slaOk": result["slaOk"],
             "planted": result["planted"], "ts": now}
        )
        summary["teams"].append(result)

    comp_ref.update({"currentRound": round_no, "lastRoundAt": now})
    _award_previous_round_defense(db, comp_id, round_no)
    return summary


def _award_previous_round_defense(db, comp_id: str, current_round: int) -> None:
    """Начисляет defense за прошлый раунд командам, чей флаг не украли.

    Флаг прошлого раунда уже истёк — если он не помечен stolen, значит защита
    сработала. Так очки защиты начисляются ретроспективно и один раз.
    """
    import scoring

    prev = current_round - 1
    if prev < 1:
        return
    flags = db.collection("flags").where(
        filter=firestore.FieldFilter("round", "==", prev)
    ).stream()
    for snap in flags:
        f = snap.to_dict()
        if f.get("defenseAwarded"):
            continue
        if not f.get("stolen"):
            scoring.award_defense(db, f["victimTeamId"])
        snap.reference.update({"defenseAwarded": True})
